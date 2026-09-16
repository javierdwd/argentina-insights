"use client";

import type { ReactNode } from "react";
import { CopilotKitProvider } from "@copilotkit/react-core/v2";

interface ProvidersProps {
  children: ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  const runtimeUrl =
    process.env.NEXT_PUBLIC_COPILOTKIT_RUNTIME_URL ?? "/api/copilotkit";

  return (
    <CopilotKitProvider runtimeUrl={runtimeUrl} agentId="argentina_insights">
      {children}
    </CopilotKitProvider>
  );
}
