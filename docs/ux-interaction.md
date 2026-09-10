# UX interaction model

Decisions and backlog for how the user talks to the agent. Complements [`PRD.md`](PRD.md) §2.1–2.2.

## Decision (default)

**Command bar is the only primary input.** What the user types there starts an agent turn; the **generative stage** (`DynamicRenderer` + registry) is the primary output.

| Surface | Role |
| --- | --- |
| Command bar (`Cmd + K`) | Query / action entry |
| Stage | Rendered UITree (metrics, charts, forms, …) |
| Thread (CopilotKit / LangGraph) | Under the hood for history, HITL, resume — not the main UI |

This is **not** a chat-first product. A persistent global chat (sidebar of bubbles) is out of scope for the default UX. It may exist later as a debug / “explain in prose” mode only.

## Why

- Matches PRD: natural-language entry + generative UI, not “generic chatbot with links.”
- Keeps the first viewport brand + command + stage (Cold bulletin shell).
- Agent work shows up as composed views, not markdown transcripts.

## Optimization backlog (not built yet)

Worth implementing once the command bar is wired to the agent:

### 1. Query registry (user asks)

A compact, visible log of what the user asked — not a full chat transcript.

- One row per turn: timestamp, query text, status (running / done / failed).
- Click a row to re-run or restore that turn’s stage tree if checkpointed.
- Keep it short (e.g. last N queries or session-scoped); expand to full history later if needed.

### 2. Compact LLM / agent result summary

Alongside (or under) each registry row, a **one-line compact** of what came back — not the raw model dump.

Examples:

- `Blue dollar · 1.250,50 ARS/USD · +1,8%`
- `3 metrics · MEP vs blue · last 30d`
- `Interrupt: adjust horizon`

Source of truth for the compact should prefer structured agent output (UITree / tool results), with a short model summary only if needed. Avoid storing full token streams in the UI layer.

### 3. Related (already in PRD)

- Contextual follow-up chips from what’s on screen.
- Stepper / node status while the graph runs.
- HITL interrupt forms in the stage (not in a chat bubble).

## Options considered

| Option | Verdict |
| --- | --- |
| Command only → stage | **Default** |
| Command → global chat + widgets | Rejected as default; feels like chatbot-with-charts |
| Command + query registry + compact summaries | **Desired optimization** after wire-up |
| Hidden thread, no visible history | Acceptable for first agent wire-up; add registry soon after |

## Implementation notes (when we build it)

- Keep registry state client-side first (session); persist with thread/checkpoint IDs when MemorySaver / Postgres lands.
- Schema idea (sketch): `{ id, query, compact, uiTreeRef?, threadId, createdAt, status }`.
- Command bar submit → append registry row → agent run → update row compact + swap stage tree.
