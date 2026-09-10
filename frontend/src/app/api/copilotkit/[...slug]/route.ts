/**
 * CopilotKit Runtime endpoint (Next.js App Router).
 *
 * Chrome / the frontend call GET /api/copilotkit/info here.
 * This Runtime proxies agent runs to the Python AG-UI endpoint via
 * HttpAgent — do not point the browser at FastAPI directly.
 */

import { HttpAgent } from "@ag-ui/client";
import {
  CopilotRuntime,
  createCopilotRuntimeHandler,
} from "@copilotkit/runtime/v2";

const AGENT_URL =
  process.env.AGENT_URL ?? "http://127.0.0.1:8000/argentina_insights";

const runtime = new CopilotRuntime({
  agents: {
    argentina_insights: new HttpAgent({
      url: AGENT_URL,
    }),
  },
});

const handler = createCopilotRuntimeHandler({
  runtime,
  basePath: "/api/copilotkit",
});

export const GET = handler;
export const POST = handler;
export const OPTIONS = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
