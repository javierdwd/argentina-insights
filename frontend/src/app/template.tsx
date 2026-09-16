import type { ReactNode } from "react";

export default function RouteTemplate({ children }: { children: ReactNode }) {
  return (
    <div className="route-transition flex min-h-0 flex-1 flex-col">
      {children}
    </div>
  );
}
