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
- Interaction model (command-only default, query registry + compact summaries backlog): [`ux-interaction.md`](ux-interaction.md).

### 2.2 Generative UI

The agent returns a **UI tree**, not markup. The client validates it (Zod) and renders only components in the registry. “Layout” is one use of that tree (containers), not the whole system — see §5.

Composition rules live in the agent prompt (e.g. two widgets → flex; more than three → grid). Containers already own responsive behavior.

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
- ~~Compact catalog format for the LLM (derived from the OpenAPI).~~ **Decided:** compact in-memory catalog derived from `openapi.json` at startup; domain-filtered subset injected into the system prompt each turn; single `fetch_argentinadatos` tool. No RAG, no per-endpoint tools. See `agent/src/agent/catalog.py` and `agent/src/agent/tools/fetch.py`.

## 5. Generative UI — abstraction & charts

### 5.1 Abstract UI tree (not layout-only)

The generative UI pipeline must stay **abstract**: the agent may emit dashboards, single widgets, HITL forms, banners, steppers, or follow-ups — not only page layouts.

```
Agent → UITree (JSON) → Zod → Registry → <DynamicRenderer />
```

`DynamicRenderer` does not know about layouts or charts. It only:

1. Validates the node against the schema for its `type`
2. Looks up the component in the registry
3. Renders `props` and recurses into `children`

Node shape (conceptual):

```ts
type UINode = {
  type: string; // registry key
  props?: Record<string, unknown>;
  children?: UINode[];
};
```

Layers in the registry (same node model, different roles):

| Layer | Role | Examples |
|-------|------|----------|
| **Containers** | composition | `Grid`, `Flex`, `Stack`, `Tabs` |
| **Widgets** | data + presentation | `Metric`, `Chart`, `Timeline`, `Table` |
| **Chrome** | system UI (not the “dashboard”) | `Banner`, `Stepper`, `InterruptForm`, `FollowUps` |

A “layout” is a tree whose root is a container. A lone `Chart` or an `InterruptForm` from LangGraph are valid trees with no grid.

Preferred naming in docs/code: **UI tree** / `ViewTree`, tool name `generateUI` (or equivalent) — not layout-centric names. `DynamicRenderer` can keep its name (already generic).

### 5.2 Chart libraries (schema-driven)

Charts must be driven by a **declarative, Zod-validated props object** inside a registered `Chart` widget. The model must not invent nested React chart components or CSS.

Fit for this pattern:

| Priority | Library | Why |
|----------|---------|-----|
| **1st** | **Apache ECharts** (`echarts-for-react`) | Chart config is a pure JSON `option` — closest to Zod → render. Line, dual-axis, area, bar, tooltip, zoom. |
| **2nd** | **Recharts** | Common in React generative UI. Agent emits `{ kind, series, xKey, yKeys, … }`; **our** `Chart` widget maps to `<LineChart>` / `<BarChart>`. LLM never builds the component tree. |
| **3rd** | **Nivo** | Props-first / near-JSON API, well typed; more verbose and visually opinionated. |

Avoid for this pattern: **Visx / raw D3** (too low-level), **Plotly** (config-object but heavy for MVP). **Tremor / shadcn charts** are fine only if the design system already uses them — they wrap Recharts and do not change the schema story.

Example agent payload for a chart node (whitelist fields only):

```ts
{
  type: "Chart",
  props: {
    kind: "line", // | "bar" | "area" | "dualAxis"
    xKey: "fecha",
    series: [
      { key: "mep", label: "MEP", color: "accent" },
      { key: "blue", label: "Blue" }
    ],
    data: [/* or dataRef into client store */]
  }
}
```

The chart library is an implementation detail of `Chart`. Covers expected use cases: FX/FCI time series, inflation vs confidence (dual-axis), investment-simulator projections.

**Default pick:** ECharts for strongest JSON/schema fit; Recharts if we prefer a lighter React-native ecosystem and keep mapping inside the widget.
