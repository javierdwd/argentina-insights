# Argentina Insights

Agent-driven web app for Argentine public data. Ask in natural language; the agent fetches from [ArgentinaDatos](https://argentinadatos.com/docs/) and **composes a UI** from a fixed design system.

### Core Objective: The Hybrid UI (The Bridge)
This is not a static dashboard, and it's not a standard chat-only interface. The fundamental objective of this project is to allow the user to control the application in two intersecting ways:
1. **Declarative (Natural Language):** Typing in the chat to fetch data, generate charts, or modify the view (e.g., *"Compare inflation with UVA over the last year"*).
2. **Imperative (Traditional UI):** Clicking filters, selecting data points on a chart, or using dropdowns rendered on the screen.

**The magic is in the bridge between the two:** Interacting with the UI (like clicking a peak in a chart) should feed context back into the chat, and typing in the chat should seamlessly mutate the state of the UI components on the main canvas. This is why components are rendered in a dedicated stage (left) rather than inline within the chat stream (right) — it creates a persistent, interactive workspace rather than an ephemeral message history.

---

Two domains, one API:

- **Finance / macro** — FX, inflation, UVA, country risk, time deposits, FCI, REM, mortgages, remittances, fees
- **Politics / transparency** — deputies, senators, commissions, votes, official travel/missions, government confidence

The product goal is to **cross, compare, and explain** (e.g. a time deposit vs REM inflation; a legislator's commissions and trips on one timeline).

Product requirements: [`docs/PRD.md`](docs/PRD.md) · Use cases: [`docs/use-cases.md`](docs/use-cases.md) · UX interaction: [`docs/ux-interaction.md`](docs/ux-interaction.md)

---

## Stack

| Layer | What |
| --- | --- |
| **Frontend** | Next.js 16 · React 19 · TypeScript · Tailwind 4 · shadcn/ui · CopilotKit 1.71 (**v2 API**) · Zod 4 |
| **Agent** | FastAPI 0.141 · LangGraph 1.2 · LangChain 1.4 · CopilotKit Python 0.1.96 |
| **State** | LangGraph `MemorySaver` (in-memory checkpointer — swap for Postgres later) |
| **Data** | [ArgentinaDatos API](https://api.argentinadatos.com) |
| **Tracing** | LangSmith (optional — enable with `LANGSMITH_API_KEY`) |
| **Package managers** | `pnpm` (frontend) · `uv` (agent) |

## How it is built

```
Browser (CopilotKit provider)
    │  GET /api/copilotkit/info   ← Runtime discovery (Next.js)
    ▼
Next.js  /api/copilotkit   (CopilotRuntime + LangGraphHttpAgent)
    │  POST /argentina_insights   ← AG-UI
    ▼
FastAPI  GET /health
         POST /argentina_insights  →  LangGraph
                                         │
                                         ├─ classify node   (MODEL_FAST)
                                         └─ respond node    (MODEL_DEFAULT)
                                                 │
                                                 └─ UITree JSON
                                                         │
                                                         ▼
                                                Zod → registry → DynamicRenderer
```

### Model roles

Swap model IDs in `agent/.env` without touching code:

| Variable | Default | Used by |
| --- | --- | --- |
| `MODEL_FAST` | `gpt-5-nano` | classify / routing nodes |
| `MODEL_DEFAULT` | `gpt-5-mini` | tools, `generateUI`, most nodes |
| `MODEL_STRONG` | `gpt-5-mini` | reserved for HITL / multi-step (PRD cases 10–13) |

## Repo layout

```
argentina-insights/
├── README.md
├── .gitignore
├── docs/
│   ├── PRD.md
│   └── use-cases.md
├── agent/                         # Python — uv
│   ├── pyproject.toml
│   ├── .env                       # local secrets (gitignored)
│   ├── .env.example               # committed template
│   ├── argentina-datos/
│   │   └── openapi.json
│   └── src/agent/
│       ├── app.py                 # FastAPI: /health + AG-UI agent
│       ├── graph.py               # LangGraph: classify → respond
│       ├── state.py               # AgentState (MessagesState + query_type)
│       ├── models.py              # get_model(role) factory
│       └── tools/                 # stub — ArgentinaDatos tools go here
└── frontend/                      # TypeScript — pnpm
    ├── package.json
    ├── .env                       # local env (gitignored)
    ├── .env.example               # committed template
    └── src/
        ├── app/
        │   ├── api/copilotkit/[...slug]/route.ts  # CopilotRuntime proxy
        │   ├── layout.tsx         # root layout + Providers
        │   ├── page.tsx           # home: sample Metric tree
        │   └── providers.tsx      # CopilotKit v2 provider (client)
        ├── components/
        │   ├── registry/
        │   │   ├── DynamicRenderer.tsx
        │   │   └── Metric.tsx
        │   └── ui/                # shadcn primitives
        └── lib/
            ├── uitree.ts          # Zod UITree schema (Metric only)
            └── utils.ts           # shadcn cn() helper
```

## Getting started

### Prerequisites

- Python ≥ 3.14
- Node ≥ 22
- [`uv`](https://docs.astral.sh/uv/) and `pnpm` installed globally

### 1. Clone and configure env

```bash
# Agent
cp agent/.env.example agent/.env
# Fill in: OPENAI_API_KEY (required), LANGSMITH_API_KEY (optional)

# Frontend
cp frontend/.env.example frontend/.env
# NEXT_PUBLIC_COPILOTKIT_RUNTIME_URL=/api/copilotkit
# AGENT_URL=http://127.0.0.1:8000/argentina_insights
```

### 2. Install dependencies

```bash
# Agent
cd agent && uv sync

# Frontend (from repo root)
cd frontend && pnpm install
```

### 3. Run

```bash
# Agent (port 8000)
cd agent && uv run uvicorn agent.app:app --reload --port 8000

# Frontend (port 3000) — separate terminal
cd frontend && pnpm dev
```

Open [http://localhost:3000](http://localhost:3000) — you should see a **Blue Dollar Metric card** rendered by `DynamicRenderer`.

Health check: `curl http://localhost:8000/health` → `{"status":"ok"}`

### LangSmith (optional)

1. Sign up at [smith.langchain.com](https://smith.langchain.com) (free Developer plan — 5 k traces/month)
2. Create an API key
3. Add it to `agent/.env`:
   ```
   LANGSMITH_TRACING=true
   LANGSMITH_API_KEY=lsv2_...
   ```
4. Every LangGraph run will appear under the `argentina-insights` project

---

## What this scaffold does NOT include yet

- Real ArgentinaDatos tool calls / compact endpoint catalog
- Full widget set (Chart/ECharts, Timeline, HITL forms)
- Cmd+K command bar
- Postgres checkpointer, Docker, auth
- PRD flows 10–13 (multi-step, HITL, alerts)
