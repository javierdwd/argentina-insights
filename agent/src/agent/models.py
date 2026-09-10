"""Model role factory.

Resolves model IDs from environment variables so node code never
hard-codes a model name. Swap models in .env without touching graph logic.

Roles:
    fast    — cheap, low-latency (classify / routing)
    default — main workhorse (tools, generateUI, most nodes)
    strong  — reserved for HITL / multi-step flows (PRD cases 10-13)
"""

import os
from typing import Literal

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


def get_model(role: ModelRole = "default") -> ChatOpenAI:
    """Return a ChatOpenAI instance for the given role.

    Reads model IDs from MODEL_FAST / MODEL_DEFAULT / MODEL_STRONG env vars.
    Falls back to sensible defaults when the variable is not set.
    """
    model_id = os.getenv(_ENV_KEYS[role], _DEFAULTS[role])
    return ChatOpenAI(model=model_id)
