"""Model role factory.

Resolves model IDs from environment variables so node code never
hard-codes a model name. Swap models in .env without touching graph logic.

Roles:
    fast    — cheap, low-latency (classify)
    default — compose_ui (widget tree + user-facing brief)
    strong  — respond / tool routing (what to fetch next)
"""

from __future__ import annotations

import os
import re
from typing import Any, Literal

from langchain_openai import ChatOpenAI

ModelRole = Literal["fast", "default", "strong"]

_DEFAULTS: dict[ModelRole, str] = {
    "fast": "gpt-5-nano",
    "default": "gpt-5-mini",
    "strong": "gpt-5-mini",
}

_ENV_KEYS: dict[ModelRole, str] = {
    "fast": "MODEL_FAST",
    "default": "MODEL_DEFAULT",
    "strong": "MODEL_STRONG",
}

# GPT-5 (and o-series) models spend internal "thinking" tokens before the
# visible response, scaled by reasoning_effort. The OpenAI API default is
# "medium" when unset, which is overkill for tasks like "pick one endpoint
# from this catalog and fill its params" — that's pattern-matching, not
# multi-step reasoning — and was adding tens of seconds of latency per call.
# minimal/low keep the model decisive without the extra thinking budget.
_REASONING_DEFAULTS: dict[ModelRole, str] = {
    "fast": "minimal",
    "default": "low",
    # Tool routing between hops — medium added tens of seconds of thinking
    # before the next fetch_argentinadatos call.
    "strong": "low",
}

_REASONING_ENV_KEYS: dict[ModelRole, str] = {
    "fast": "REASONING_FAST",
    "default": "REASONING_DEFAULT",
    "strong": "REASONING_STRONG",
}

# reasoning_effort is only valid for reasoning-family models (gpt-5*, o1, o3,
# o4...). Sending it to a non-reasoning model (e.g. gpt-4o-mini, if someone
# points MODEL_DEFAULT there) is a 400 from the API, so only pass it through
# when the configured model id actually looks like a reasoning model.
_REASONING_MODEL_RE = re.compile(r"^(gpt-5|o1|o3|o4)")

# GPT-5.2 / GPT-5.4 dropped ``minimal`` in favour of ``none``. The original
# gpt-5 / gpt-5-mini / gpt-5-nano still require ``minimal``. Ids look like
# ``gpt-5.4`` or ``gpt-5.4-mini`` (dot after 5), vs ``gpt-5-mini`` (hyphen).
_NO_MINIMAL_RE = re.compile(r"^gpt-5\.\d")

# Summaries are the ChatGPT-like "Pensando…" text. Only the respond hop
# (strong) is user-facing; classify/compose stay silent so widget JSON and
# ui/data labels never leak into the thread.
_SUMMARY_ROLES: frozenset[ModelRole] = frozenset({"strong"})
_SUMMARY_OFF = frozenset({"", "off", "none", "false", "0"})


def _reasoning_effort(model_id: str, requested: str) -> str:
    """Coerce effort to a value this model actually accepts."""
    if requested == "minimal" and _NO_MINIMAL_RE.match(model_id):
        return "none"
    if requested == "none" and not _NO_MINIMAL_RE.match(model_id):
        return "minimal"
    return requested


def _reasoning_summary() -> str | None:
    """Responses-API summary mode, or None to omit the field.

    Default is off: ``auto`` is the detailed essay ChatGPT does *not* show
    in the thread. Tool lines + ``Pensando…`` are the abbreviated UX.
    Set ``REASONING_SUMMARY=concise`` to opt into a model-written blurb.
    """
    raw = os.getenv("REASONING_SUMMARY", "off").strip().lower()
    if raw in _SUMMARY_OFF:
        return None
    if raw in {"auto", "concise", "detailed"}:
        return raw
    return None


def chat_kwargs(role: ModelRole = "default") -> dict[str, Any]:
    """Kwargs for ``ChatOpenAI`` for this role (no network)."""
    model_id = os.getenv(_ENV_KEYS[role], _DEFAULTS[role])
    kwargs: dict[str, Any] = {"model": model_id}
    if not _REASONING_MODEL_RE.match(model_id):
        return kwargs

    effort = _reasoning_effort(
        model_id,
        os.getenv(_REASONING_ENV_KEYS[role], _REASONING_DEFAULTS[role]),
    )
    # Responses API is required for (a) gpt-5.4 tools+effort and (b) streamed
    # reasoning summaries that CopilotKit renders as role=reasoning.
    kwargs["use_responses_api"] = True
    kwargs["output_version"] = "responses/v1"
    reasoning: dict[str, Any] = {"effort": effort}
    if (
        role in _SUMMARY_ROLES
        and effort not in {"none", "minimal"}
        and (summary := _reasoning_summary())
    ):
        reasoning["summary"] = summary
    kwargs["reasoning"] = reasoning
    return kwargs


def get_model(role: ModelRole = "default") -> ChatOpenAI:
    """Return a ChatOpenAI instance for the given role.

    Reads model IDs from MODEL_FAST / MODEL_DEFAULT / MODEL_STRONG env vars
    (falls back to sensible defaults), and reasoning effort from
    REASONING_FAST / REASONING_DEFAULT / REASONING_STRONG (falls back to
    minimal/low/low) when the model is a reasoning-family model.
    """
    return ChatOpenAI(**chat_kwargs(role))
