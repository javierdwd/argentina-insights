"""Idle-thread eviction for the in-memory LangGraph checkpointer."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from agent.checkpointer import ActivityMemorySaver


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


def test_tracks_creation_and_latest_activity() -> None:
    started_at = datetime(2026, 9, 16, 8, 0, tzinfo=UTC)
    clock = MutableClock(started_at)
    saver = ActivityMemorySaver(clock=clock)
    config = {"configurable": {"thread_id": "thread-1"}}

    saver.get_tuple(config)
    clock.advance(timedelta(minutes=4))
    saver.get_tuple(config)

    activity = saver.activity_snapshot()["thread-1"]
    assert activity.created_at == started_at
    assert activity.last_activity_at == started_at + timedelta(minutes=4)


def test_purges_only_threads_idle_for_ten_minutes() -> None:
    clock = MutableClock(datetime(2026, 9, 16, 8, 0, tzinfo=UTC))
    saver = ActivityMemorySaver(clock=clock)
    stale = {"configurable": {"thread_id": "stale"}}
    active = {"configurable": {"thread_id": "active"}}

    saver.get_tuple(stale)
    clock.advance(timedelta(minutes=9))
    saver.get_tuple(active)
    clock.advance(timedelta(minutes=2))

    assert saver.purge_inactive(timedelta(minutes=10)) == ["stale"]
    assert set(saver.activity_snapshot()) == {"active"}


def test_explicit_delete_removes_activity_record() -> None:
    saver = ActivityMemorySaver()
    config = {"configurable": {"thread_id": "thread-1"}}
    saver.get_tuple(config)

    saver.delete_thread("thread-1")

    assert saver.activity_snapshot() == {}
