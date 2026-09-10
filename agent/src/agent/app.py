"""FastAPI application.

Endpoints:
    GET  /health                          — liveness check
    POST /argentina_insights              — AG-UI LangGraph agent (CopilotKit)
    GET  /argentina_insights/health       — agent health (from ag-ui-langgraph)
"""

import os
from contextlib import asynccontextmanager

from ag_ui_langgraph import add_langgraph_fastapi_endpoint
from copilotkit import LangGraphAGUIAgent
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env before importing modules that read env vars at definition time.
load_dotenv()

from .graph import graph  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    yield


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
