import type { Metadata } from "next";
import { AgentStage } from "@/components/shell/AgentStage";

export const metadata: Metadata = {
  title: "Conversación · Argentina Insights",
};

export default function ChatPage() {
  return <AgentStage />;
}
