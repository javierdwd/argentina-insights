# Argentina Insights — Product Requirements (starting draft)

See [`README.md`](../README.md) for the product pitch, stack, and repo layout.

## 1. What this is not

- A professional market terminal.
- A generic chatbot with links.
- A CMS where an admin lays out pages.
- An app that lets the model invent React components or CSS.

## 2. Required characteristics

### 2.1 Natural-language entry

- A central **command bar** (`Cmd + K`) is the main entry point for queries and actions.
- The UI suggests **contextual follow-ups** from what is on screen (e.g. after a FX series or a rate, offer a comparison or a projection).

### 2.2 Generative UI

The agent returns a **layout tree**, not markup. The client validates it (Zod) and renders only components in the registry (wrappers such as `GridWrapper` / `FlexWrapper`, widgets such as `MetricWidget` / `ChartWidget`).

Composition rules live in the agent prompt (e.g. two widgets → flex; more than three → grid). Wrappers already own responsive behavior.

### 2.3 Stateful agent

Some jobs need branching, parallelism, durable state, and human-in-the-loop — not a single tool call.

The UI must know **which graph node is running** (steppers / contextual loaders) and use **checkpoints** so the user can pause, go back, change a variable, and resume.

Candidate flows:

1. **Legislative audit** — resolve a deputy/senator → fetch commissions and trips in parallel → render a timeline (and related widgets).
2. **Investment simulator** — gather rates, REM, FCI, inflation, UVA → draft conservative/moderate/aggressive scenarios → **interrupt** for user parameter tweaks → final projection.
3. **Macro monitor** — periodic/conditional rules (e.g. time-deposit TEA vs REM inflation) → persist alert state → inject banners into the UI.
4. **UVA mortgage evaluator** — route the question → RAG on bank rules **and** API (UVA + REM) in parallel → amortization math → branch on installment/income risk → interactive amortization table.

## 3. Legislative travel — data constraint

ArgentinaDatos does **not** expose ticket/airfare prices, nor a “trip cost at booking time.”

What exists:

- **Senate international trips / deputy official missions:** dates (when parsed), destination, and optional **viáticos** (`viaticosUsd` / `viaticosEuro` / `viaticosArs`).
- **National trips (senate and deputies):** origin, destination, year/month. No exact date, no amount.

**Out of scope:** quoting, converting, or reconstructing travel ticket values in pesos or dollars. Do not invent missing costs. Viáticos may be shown as declared when present. National trips are routes and periods only.

## 4. Open questions

- Primary user: retail saver, civic/journalist, both, or power-user analyst.
- MVP: one end-to-end flow + command bar + schema renderer, vs. a broader first cut.
- Compact catalog format for the LLM (derived from the OpenAPI).
