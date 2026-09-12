"""Match queries against a compact id+label directory via the fast model.

Used for legislator names and law titles: order, typos, and commas are
language problems, not string-filter problems. The model sees lines of
``id\\tlabel`` and returns matching ids.

Prompt shape (cache-friendly):
  1. system — fixed instructions
  2. human  — the full directory (stable until the upstream list refreshes)
  3. human  — the query / queries (varies every call)

OpenAI prompt caching keys off a shared prefix. Keeping the directory in
message 2 and the query last means repeat searches reuse the cached
catalog tokens. ``prompt_cache_key`` routes related calls to the same
cache shard.
"""

from __future__ import annotations

import hashlib
from typing import Sequence

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ..models import get_model

_SYSTEM = """\
You match user queries against a directory.

Each directory line is `id<TAB>label`. A query matches a line if it refers \
to the same thing — typos, accents, given/family-name order, and extra \
filler words do not matter.

Return only ids that appear in the directory. Prefer the best matches; \
skip queries that match nobody. Never invent an id. If nothing matches, \
return an empty list.
"""


class DirectoryMatch(BaseModel):
    ids: list[str] = Field(default_factory=list)


def _cache_key(kind: str, catalog: str) -> str:
    digest = hashlib.md5(catalog.encode()).hexdigest()[:12]
    return f"{kind}-{digest}"


async def match_directory(
    *,
    kind: str,
    lines: Sequence[str],
    queries: Sequence[str],
    by_id: dict[str, dict],
) -> list[dict]:
    """Return rows from *by_id* whose ids the fast model picked for *queries*."""
    clean = [str(q).strip() for q in queries if str(q).strip()]
    if not clean:
        return list(by_id.values())
    if not lines:
        return []

    catalog = "\n".join(lines)
    llm = get_model("fast").with_structured_output(
        DirectoryMatch, method="function_calling"
    )
    result: DirectoryMatch = await llm.ainvoke(
        [
            SystemMessage(content=_SYSTEM),
            # Stable prefix → OpenAI prompt cache on repeat searches.
            HumanMessage(content=f"Directory ({kind}):\n{catalog}"),
            HumanMessage(
                content="Queries:\n" + "\n".join(f"- {q}" for q in clean)
            ),
        ],
        config={"metadata": {"emit-messages": False}},
        prompt_cache_key=_cache_key(kind, catalog),
    )

    matched: list[dict] = []
    seen: set[str] = set()
    for rid in result.ids:
        key = str(rid).strip()
        row = by_id.get(key)
        if row is None or key in seen:
            continue
        seen.add(key)
        matched.append(row)
    return matched
