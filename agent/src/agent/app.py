"""FastAPI application.

Endpoints:
    GET  /health                          — liveness check
    GET  /api/data                        — catalog-gated proxy bridge (no LLM)
    POST /argentina_insights              — AG-UI LangGraph agent (CopilotKit)
    GET  /argentina_insights/health       — agent health (from ag-ui-langgraph)
"""

import asyncio
import os
from contextlib import asynccontextmanager
from contextlib import suppress
from datetime import timedelta
from typing import Any

from ag_ui_langgraph import add_langgraph_fastapi_endpoint
from copilotkit import LangGraphAGUIAgent
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

# Load .env before importing modules that read env vars at definition time.
load_dotenv()

from . import proxy  # noqa: E402
from .catalog import catalog  # noqa: E402
from .checkpointer import ActivityMemorySaver  # noqa: E402
from .graph import graph  # noqa: E402


_CLEANUP_INTERVAL = timedelta(minutes=15)
_THREAD_MAX_IDLE = timedelta(minutes=10)


async def _cleanup_inactive_threads(checkpointer: ActivityMemorySaver) -> None:
    """Periodically release checkpoints for conversations that went idle."""
    while True:
        await asyncio.sleep(_CLEANUP_INTERVAL.total_seconds())
        checkpointer.purge_inactive(_THREAD_MAX_IDLE)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    checkpointer = graph.checkpointer
    if not isinstance(checkpointer, ActivityMemorySaver):
        raise RuntimeError("Graph must use ActivityMemorySaver")

    cleanup_task = asyncio.create_task(
        _cleanup_inactive_threads(checkpointer),
        name="inactive-thread-cleanup",
    )
    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task


app = FastAPI(
    title="Argentina Insights Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGIN", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    """Liveness check."""
    return {"status": "ok"}


@app.get("/api/data")
async def api_data(
    request: Request,
    path: str = Query(..., description="Catalog path template or filled path"),
) -> Any:
    """Thin HTTP bridge to ``proxy.resolve`` — same allowlist as the fetch tool.

    Used by the Next.js ``/api/data`` route so destinations can load series
    without a chat turn. Browser must not call this URL directly in prod;
    go through the Next proxy.
    """
    matched = catalog.match(path)
    if matched is None:
        raise HTTPException(status_code=404, detail=f"Path not in catalog: {path}")
    op, from_path = matched

    params: dict[str, Any] = {**from_path}
    for key, value in request.query_params.multi_items():
        if key == "path":
            continue
        params[key] = value

    try:
        return await proxy.resolve(op.path, params)
    except proxy.NoMatch as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except proxy.ProxyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except proxy.UpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ── CopilotKit / AG-UI ────────────────────────────────────────────────────────
# The Next.js CopilotRuntime proxies here via LangGraphAGUIAgent.
# Do NOT point the browser CopilotKit provider at this URL directly —
# Chrome GETs /info, which is a Runtime concern, not an AG-UI agent concern.

agent = LangGraphAGUIAgent(
    name="argentina_insights",
    description=(
        "Argentine financial and political data assistant. "
        "Fetches from ArgentinaDatos and composes a UI tree."
    ),
    graph=graph,
)

add_langgraph_fastapi_endpoint(app, agent, "/argentina_insights")
