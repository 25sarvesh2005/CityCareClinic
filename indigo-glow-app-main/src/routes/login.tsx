import { useEffect } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { homeForRole, useSession } from "@/lib/auth";
import { LandingPage } from "./index";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Log in — CityCare Clinic" },
      { name: "description", content: "Sign in to manage your appointments at CityCare Clinic." },
      { property: "og:title", content: "Log in — CityCare Clinic" },
      {
        property: "og:description",
        content: "Sign in to manage your appointments at CityCare Clinic.",
      },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const { user } = useSession();
  const navigate = useNavigate();

  useEffect(() => {
    if (user) {
      navigate({ to: homeForRole(user.role), replace: true });
    }
  }, [user, navigate]);

  return <LandingPage defaultAuthTab="login" />;
}
