# Use Cases

Ordered from simple (single endpoint, single widget) to complex (multi-step, stateful, human-in-the-loop). See [`docs/PRD.md`](PRD.md) for the underlying requirements and [`agent/argentina-datos/openapi.json`](../agent/argentina-datos/openapi.json) for the data source.

Each entry: example prompt → endpoints involved → flow → UI output.

---

## 1. Current FX quote

**Prompt:** "What's the blue dollar rate right now?"

- **Endpoints:** `GET /v1/cotizaciones/dolares/{casa}`
- **Flow:** single fetch, no agent state.
- **Output:** one `MetricWidget` (compra/venta, fecha).

## 2. FX historical series

**Prompt:** "Show me the MEP dollar's evolution this year."

- **Endpoints:** `GET /v1/cotizaciones/dolares/{casa}` (filtered client- or agent-side by date range)
- **Flow:** single fetch.
- **Output:** one `ChartWidget` (line, time series).

## 3. Inflation snapshot

**Prompt:** "What was last month's inflation?"

- **Endpoints:** `GET /v1/finanzas/indices/inflacion` (last item) or `inflacionInteranual`
- **Flow:** single fetch.
- **Output:** one `MetricWidget`.

## 4. Compare FX casas side by side

**Prompt:** "Compare oficial, blue, and MEP."

- **Endpoints:** `GET /v1/cotizaciones/dolares/{casa}` × 3 (parallel)
- **Flow:** parallel fetch, no branching.
- **Output:** `FlexWrapper` (3 widgets) or `GridWrapper` if more casas are added → `MetricWidget` each.

## 5. Time deposit vs inflation (real yield)

**Prompt:** "Does a time deposit beat inflation today?"

- **Endpoints:** `GET /v1/finanzas/tasas/plazoFijo`, `GET /v1/finanzas/indices/inflacionInteranual`
- **Flow:** parallel fetch + one derived calculation (TNA/TEA vs year-over-year inflation). No interrupt needed.
- **Output:** `GridWrapper` with two `MetricWidget`s and a computed delta/verdict widget.

## 6. FCI fund lookup

**Prompt:** "Tell me the historical returns of the Delta Pesos fund."

- **Endpoints:** `GET /v1/finanzas/fci/fondos/{nombre}`, `GET /v1/finanzas/fci/fondos/{nombre}/historico`
- **Flow:** sequential fetch (resolve fund name → fetch history).
- **Output:** `MetricWidget` (current) + `ChartWidget` (historical).

## 7. Remittance/fee comparison

**Prompt:** "Which platform charges the lowest fee to receive payments from the US?"

- **Endpoints:** `GET /v1/finanzas/remesas`, `GET /v1/finanzas/cobros/comisiones`
- **Flow:** parallel fetch + client-side ranking (cheapest first).
- **Output:** a table-like widget (list ranked by cost) — first candidate for a dedicated `ComparisonTable` widget.

## 8. Legislator profile

**Prompt:** "Tell me about senator X: which commissions is she on, and what trips has she taken?"

- **Endpoints:** `GET /v1/senado/senadores/{id}/comisiones`, `GET /v1/senado/senadores/{id}/viajes` (national + international)
- **Flow:** resolve legislator → fetch commissions and trips in parallel → merge into one structure.
- **Output:** `MetricWidget` (basic info) + a timeline/list widget with routes, dates, and declared viáticos where present (no ticket-price conversion; see PRD §3).

## 9. Government confidence vs macro context

**Prompt:** "How has government confidence been trending lately, and what's happening with inflation in parallel?"

- **Endpoints:** `GET /v1/politica/indices/confianza-gobierno`, `GET /v1/finanzas/indices/inflacionInteranual`
- **Flow:** parallel fetch across domains (politics + macro), no shared entity resolution needed, just a shared time axis.
- **Output:** two `ChartWidget`s in a `GridWrapper` sharing a time range, or one dual-axis chart if the widget supports it.

## 10. Legislative audit (full)

**Prompt:** "Audit deputy Y: commissions, trips, and official missions over the last 2 years."

- **Endpoints:** `GET /v1/diputados/diputados/{id}/comisiones`, `.../viajes`, `.../misiones` (parallel)
- **Flow (LangGraph):** resolve entity → parallel fetch of 3 sources → cross-reference/dedupe by date → consolidate into one timeline component. No human-in-the-loop, but multi-node enough to benefit from graph state (useful to show a stepper: "resolving legislator" → "fetching records" → "building timeline").
- **Output:** one composite timeline widget, possibly with tabs (comisiones / viajes / misiones).

## 11. Investment simulator (human-in-the-loop)

**Prompt:** "I want to invest ARS 2,000,000 for 6 months, show me scenarios."

- **Endpoints:** `GET /v1/finanzas/tasas/plazoFijo`, `GET /v1/finanzas/rem`, `GET /v1/finanzas/fci/*`, `GET /v1/finanzas/indices/inflacion*`, `GET /v1/finanzas/indices/uva`
- **Flow (LangGraph):** parallel data collection → build conservative/moderate/aggressive scenarios → **interrupt** for the user to adjust amount/horizon/risk → resume → final projection + rebalancing suggestion.
- **Output:** scenario comparison widgets pre-interrupt, then an updated projection widget post-resume. UI shows which graph node is active (loader/stepper) and lets the user edit parameters inline.

## 12. Macro alert monitor (cyclic, persistent)

**Prompt (implicit, not necessarily typed):** "Alert me if a time deposit stops beating expected inflation."

- **Endpoints:** `GET /v1/finanzas/tasas/plazoFijo`, `GET /v1/finanzas/rem` (periodic polling)
- **Flow (LangGraph):** cyclic fetch → evaluate condition (TEA vs REM-projected inflation) → persist alert state via checkpointer → on state change, inject a banner/notification into the UI without an explicit user query.
- **Output:** a banner/alert component injected contextually, plus the underlying comparison widget if the user opens it.

## 13. UVA mortgage evaluator (RAG + API, risk branch)

**Prompt:** "With a $2,500,000 income and a $50,000,000 loan over 20 years, is a UVA mortgage a good idea for me?"

- **Endpoints:** `GET /v1/finanzas/creditos/hipotecariosUva`, `GET /v1/finanzas/indices/uva`, `GET /v1/finanzas/rem` + RAG over bank eligibility/terms (not in ArgentinaDatos; separate knowledge source).
- **Flow (LangGraph):** route the query → RAG (bank rules) and API (UVA + REM) in parallel → amortization calculation node → conditional branch on installment/income ratio (risk flag) → render.
- **Output:** interactive amortization table widget, with a risk banner if the installment/income ratio crosses a threshold.

---

## Notes

- Cases 1–9 need no LangGraph: a single frontend tool call (fetch + optional client-side math) is enough.
- Cases 10–13 justify LangGraph: parallel branches, multi-source consolidation, persisted/cyclic state, or human-in-the-loop.
- Case 8 and 10 must follow the travel data constraint in [`docs/PRD.md`](PRD.md#3-legislative-travel--data-constraint): routes, dates, and declared viáticos only — no ticket-price quoting.
- None of these assume new widgets beyond `MetricWidget` / `ChartWidget` except where noted (case 7's ranked list, case 10's timeline, case 13's amortization table) — those are candidates for the next widgets added to the component registry.
