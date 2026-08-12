import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { PatientPrescriptionChatBot } from "@/components/chatbot/PatientPrescriptionChatBot";

export const Route = createFileRoute("/prescription-ai")({
  head: () => ({
    meta: [
      { title: "Prescription AI Workspace — CityCare Clinic" },
      { name: "description", content: "Intelligent full-window prescription assistant with Gemini medical AI." },
      { property: "og:title", content: "Prescription AI Workspace — CityCare Clinic" },
      {
        property: "og:description",
        content: "Intelligent full-window prescription assistant with Gemini medical AI.",
      },
    ],
  }),
  component: () => (
    <RoleGuard role={["patient", "super_admin"]}>
      <AppShell>
        <PatientPrescriptionChatBot />
      </AppShell>
    </RoleGuard>
  ),
});
