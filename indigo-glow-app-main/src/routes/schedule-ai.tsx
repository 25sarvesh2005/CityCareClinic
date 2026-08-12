import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { ScheduleChatBot } from "@/components/chatbot/ScheduleChatBot";

export const Route = createFileRoute("/schedule-ai")({
  head: () => ({
    meta: [
      { title: "Schedule AI Workspace — CityCare Clinic" },
      { name: "description", content: "Intelligent full-window schedule assistant with Gemini function calling." },
      { property: "og:title", content: "Schedule AI Workspace — CityCare Clinic" },
      {
        property: "og:description",
        content: "Intelligent full-window schedule assistant with Gemini function calling.",
      },
    ],
  }),
  component: () => (
    <RoleGuard role={["doctor", "hospital_owner"]}>
      <AppShell>
        <ScheduleChatBot />
      </AppShell>
    </RoleGuard>
  ),
});
