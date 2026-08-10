import { useEffect } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { homeForRole, useSession } from "@/lib/auth";
import { LandingPage } from "./index";

export const Route = createFileRoute("/signup")({
  head: () => ({
    meta: [
      { title: "Create account — CityCare Clinic" },
      {
        name: "description",
        content: "Register for an account to book consultations at CityCare Clinic.",
      },
      { property: "og:title", content: "Create account — CityCare Clinic" },
      {
        property: "og:description",
        content: "Register for an account to book consultations at CityCare Clinic.",
      },
    ],
  }),
  component: SignupPage,
});

function SignupPage() {
  const { user } = useSession();
  const navigate = useNavigate();

  useEffect(() => {
    if (user) {
      navigate({ to: homeForRole(user.role), replace: true });
    }
  }, [user, navigate]);

  return <LandingPage defaultAuthTab="signup" />;
}
