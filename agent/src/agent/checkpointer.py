"""In-memory LangGraph checkpoints with idle-thread eviction."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Any, Callable, Sequence

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ThreadActivity:
    """Creation and most recent checkpoint activity for one graph thread."""

    created_at: datetime
    last_activity_at: datetime


class ActivityMemorySaver(MemorySaver):
    """MemorySaver that tracks activity and can evict idle threads."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        super().__init__()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._activity: dict[str, ThreadActivity] = {}
        self._activity_lock = RLock()

    @staticmethod
    def _thread_id(config: RunnableConfig) -> str | None:
        thread_id = config.get("configurable", {}).get("thread_id")
        return str(thread_id) if thread_id is not None else None

    def _touch(self, config: RunnableConfig) -> None:
        thread_id = self._thread_id(config)
        if thread_id is None:
            return

        now = self._clock()
        with self._activity_lock:
            previous = self._activity.get(thread_id)
            self._activity[thread_id] = ThreadActivity(
                created_at=previous.created_at if previous else now,
                last_activity_at=now,
            )

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        self._touch(config)
        return super().get_tuple(config)

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        self._touch(config)
        return super().put(config, checkpoint, metadata, new_versions)

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        self._touch(config)
        return super().put_writes(config, writes, task_id, task_path)

    def activity_snapshot(self) -> dict[str, ThreadActivity]:
        """Return a copy suitable for diagnostics without exposing mutation."""
        with self._activity_lock:
            return dict(self._activity)

    def delete_thread(self, thread_id: str) -> None:
        with self._activity_lock:
            super().delete_thread(thread_id)
            self._activity.pop(thread_id, None)

    def purge_inactive(self, max_idle: timedelta) -> list[str]:
        """Delete threads whose most recent activity is older than max_idle."""
        cutoff = self._clock() - max_idle
        removed: list[str] = []

        # Keep the check and deletion atomic relative to activity updates.
        with self._activity_lock:
            stale_ids = [
                thread_id
                for thread_id, activity in self._activity.items()
                if activity.last_activity_at <= cutoff
            ]
            for thread_id in stale_ids:
                super().delete_thread(thread_id)
                self._activity.pop(thread_id, None)
                removed.append(thread_id)

        if removed:
            logger.info("Purged %d inactive graph threads", len(removed))
        return removed
