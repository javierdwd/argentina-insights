"use client";

import type { ReactNode } from "react";
import { CopilotKit } from "@copilotkit/react-core/v2";

interface ProvidersProps {
  children: ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  const runtimeUrl =
    process.env.NEXT_PUBLIC_COPILOTKIT_RUNTIME_URL ?? "/api/copilotkit";

  return (
    <CopilotKit runtimeUrl={runtimeUrl} agentId="argentina_insights">
      {children}
    </CopilotKit>
  );
}
