"""Match queries against a short candidate list via an LLM pick.

Used after vector retrieval for legislator names and law titles: the model
sees only top-k ``id\\tlabel`` lines (never the full catalog) and returns
matching ids.
"""

from __future__ import annotations

import hashlib
from typing import Sequence

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ..models import ModelRole, get_model

_SYSTEM = """\
You match user queries against a short candidate list (already retrieved).

Each line is `id<TAB>label`. A query matches a line if it refers to the \
same thing — typos, accents, given/family-name order, and extra filler \
words do not matter.

For named laws/bills: if a label clearly contains the name the user gave \
(e.g. query "joaquin" and a label with "LEY JOAQUÍN"), that id MUST be \
returned. Prefer 1 best match; return a few only when several candidates \
are truly ambiguous. Do not return the whole list.

If NONE of the candidate labels clearly refers to the named law (shared \
distinctive tokens like a proper name), return an empty list — never pick \
a vaguely related title just to return something.

Return only ids that appear in the list. Never invent an id. If none of \
the candidates is clearly the same entity, return an empty list.
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
    role: ModelRole = "default",
) -> list[dict]:
    """Return rows from *by_id* whose ids the model picked for *queries*."""
    clean = [str(q).strip() for q in queries if str(q).strip()]
    if not clean:
        return list(by_id.values())
    if not lines:
        return []

    catalog = "\n".join(lines)
    llm = get_model(role).with_structured_output(
        DirectoryMatch, method="function_calling"
    )
    result: DirectoryMatch = await llm.ainvoke(
        [
            SystemMessage(content=_SYSTEM),
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
