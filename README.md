# Argentina Insights

Agent-driven web app for Argentine public data. Ask in natural language; the agent fetches from [ArgentinaDatos](https://argentinadatos.com/docs/) and **composes a UI** from a fixed design system — not a static dashboard, and not chat-only markdown.

Two domains, one API:

- **Finance / macro** — FX, inflation, UVA, country risk, time deposits, FCI, REM, mortgages, remittances, fees
- **Politics / transparency** — deputies, senators, commissions, votes, official travel/missions, government confidence

The product goal is to **cross, compare, and explain** (e.g. a time deposit vs REM inflation; a legislator’s commissions and trips on one timeline).

Product requirements: [`docs/PRD.md`](docs/PRD.md).

## Stack

- **React + TypeScript** — UI
- **Zod** — layout tree schema / validation
- **CopilotKit** — frontend tools, generative UI integration
- **LangGraph** — multi-step agent orchestration, checkpoints, human-in-the-loop
- **ArgentinaDatos API** — data source (`https://api.argentinadatos.com`)

## How it is built

| Layer                  | Approach                                                                                                                                 |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| UI                     | React + TypeScript. Schema-driven layout (Zod tree → component registry → `<DynamicRenderer />`). The model does not write React or CSS. |
| Agent (frontend tools) | CopilotKit (`useFrontendTool`, e.g. `generateLayout`) returns JSON that matches the layout schema.                                       |
| Agent (multi-step)     | LangGraph for branching, parallelism, checkpoints, and human-in-the-loop.                                                                |
| Data                   | ArgentinaDatos (`https://api.argentinadatos.com`). Spec: [`agent/argentina-datos/openapi.json`](agent/argentina-datos/openapi.json).     |

The OpenAPI file is ~50k tokens — too large to inject on every model turn. The agent should use a compact endpoint catalog (name, path, params, description), not the full spec.

## Repo

```
argentina-insights/
├── README.md
├── docs/
│   ├── PRD.md
└── agent/
    └── argentina-datos/
        └── openapi.json
```

This repo is still a spec/scaffold. There is no app to run yet.
