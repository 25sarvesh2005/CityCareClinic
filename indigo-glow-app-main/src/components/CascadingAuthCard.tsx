import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Sparkles, ArrowRight, ArrowLeft, UserPlus } from "lucide-react";
import { Button, Field } from "./ui-kit";
import { useToast } from "./Toaster";
import { api, ApiError } from "@/lib/api";
import { homeForRole, saveSession } from "@/lib/auth";
import { cn } from "@/lib/utils";

interface CascadingAuthCardProps {
  initialTab?: "login" | "signup";
  onClose?: () => void;
}

export function CascadingAuthCard({ initialTab = "login", onClose }: CascadingAuthCardProps) {
  const navigate = useNavigate();
  const toast = useToast();

  const [activeTab, setActiveTab] = useState<"login" | "signup">(initialTab);

  // Login form state
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  // Signup form state
  const [signupName, setSignupName] = useState("");
  const [signupEmail, setSignupEmail] = useState("");
  const [signupPassword, setSignupPassword] = useState("");

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  async function handleLoginSubmit(e: React.FormEvent) {
    e.preventDefault();
    const nextErr: Record<string, string> = {};
    if (!loginEmail.includes("@")) nextErr["email"] = "Enter a valid email address.";
    if (!loginPassword) nextErr["password"] = "Password is required.";
    setErrors(nextErr);
    if (Object.keys(nextErr).length) return;

    setBusy(true);
    try {
      const res = await api.login({ email: loginEmail.trim(), password: loginPassword.trim() });
      saveSession(res.access_token, res.name, res.role, res.email);
      toast.success("Welcome back!", res.name);
      navigate({ to: homeForRole(res.role), replace: true });
    } catch (err) {
      const e2 = err as ApiError;
      if (e2.status === 401) {
        setErrors({
          email: "Invalid email address or password.",
          password: "Check your password.",
        });
      } else if (e2.status === 422) {
        setErrors({ email: e2.message });
      }
      toast.error(e2.status === 401 ? "Invalid email or password" : "Couldn't sign in", e2.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleSignupSubmit(e: React.FormEvent) {
    e.preventDefault();
    const nextErr: Record<string, string> = {};
    if (signupName.trim().length < 2) nextErr["name"] = "Full name must be at least 2 characters.";
    if (!signupEmail.includes("@")) nextErr["email"] = "Enter a valid email address.";
    if (signupPassword.length < 6) nextErr["password"] = "Password must be at least 6 characters.";
    setErrors(nextErr);
    if (Object.keys(nextErr).length) return;

    setBusy(true);
    try {
      const cleanEmail = signupEmail.trim();
      const cleanPassword = signupPassword.trim();

      await api.signup({
        name: signupName.trim(),
        email: cleanEmail,
        password: cleanPassword,
      });

      const loginRes = await api.login({
        email: cleanEmail,
        password: cleanPassword,
      });

      saveSession(
        loginRes.access_token,
        loginRes.name,
        loginRes.role,
        loginRes.email || cleanEmail,
      );
      toast.success("Welcome to CityCare!", `Account created for ${loginRes.name}`);
      navigate({ to: homeForRole(loginRes.role), replace: true });
    } catch (err) {
      const e2 = err as ApiError;
      if (e2.status === 409) setErrors({ email: "An account with this email already exists." });
      else if (e2.status === 422) setErrors({ email: e2.message });
      else toast.error("Couldn't create account", e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative w-full max-w-md animate-cascade-in">
      <div className="glass relative overflow-hidden rounded-3xl border border-glass-border bg-card/95 p-6 shadow-2xl backdrop-blur-xl glow-indigo">
        {/* Glow accent band */}
        <div className="absolute -top-12 -left-12 size-36 rounded-full bg-gradient-to-br from-indigo/30 to-cyan/30 blur-2xl pointer-events-none" />

        {/* Top Header Controls */}
        <div className="flex items-center justify-between pb-4 border-b border-glass-border">
          <div className="flex items-center gap-1 rounded-2xl bg-secondary/80 p-1">
            <button
              type="button"
              onClick={() => {
                setActiveTab("login");
                setErrors({});
              }}
              className={cn(
                "flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold transition-all duration-200",
                activeTab === "login"
                  ? "bg-gradient-to-r from-indigo to-cyan text-cyan-foreground shadow-md scale-[1.02]"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Sparkles className="size-3.5" /> Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setActiveTab("signup");
                setErrors({});
              }}
              className={cn(
                "flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold transition-all duration-200",
                activeTab === "signup"
                  ? "bg-gradient-to-r from-indigo to-cyan text-cyan-foreground shadow-md scale-[1.02]"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <UserPlus className="size-3.5" /> Register
            </button>
          </div>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="group flex items-center gap-1.5 rounded-xl border border-glass-border bg-secondary/60 px-3 py-1.5 text-xs font-semibold text-muted-foreground transition-all duration-200 hover:bg-secondary hover:text-foreground hover:scale-105 active:scale-95 shadow-sm"
              title="Go back"
            >
              <ArrowLeft className="size-3.5 transition-transform duration-200 group-hover:-translate-x-0.5" />
              <span>Go Back</span>
            </button>
          )}
        </div>

        {/* STANDARD CLEAN LOGIN FORM */}
        {activeTab === "login" && (
          <div className="mt-5 space-y-4">
            <div>
              <h2 className="text-xl font-semibold tracking-tight text-foreground">Welcome Back</h2>
              <p className="text-xs text-muted-foreground mt-1">
                Log in to access your appointments or dashboard.
              </p>
            </div>

            <form onSubmit={handleLoginSubmit} className="space-y-3">
              <Field
                label="Email Address"
                type="email"
                placeholder="name@email.com"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                {...(errors["email"] ? { error: errors["email"] } : {})}
              />

              <Field
                label="Password"
                type="password"
                placeholder="••••••••"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                {...(errors["password"] ? { error: errors["password"] } : {})}
              />

              <Button type="submit" className="w-full mt-2" disabled={busy}>
                {busy ? (
                  "Signing in…"
                ) : (
                  <span className="flex items-center gap-2">
                    Log In
                    <ArrowRight className="size-4" />
                  </span>
                )}
              </Button>
            </form>
          </div>
        )}

        {/* SIGNUP FORM */}
        {activeTab === "signup" && (
          <div className="mt-5 space-y-4">
            <div>
              <h2 className="text-xl font-semibold tracking-tight text-foreground">
                Create Patient Account
              </h2>
              <p className="text-xs text-muted-foreground mt-1">
                Register once to book consultation slots.
              </p>
            </div>

            <form onSubmit={handleSignupSubmit} className="space-y-3">
              <Field
                label="Full Name"
                placeholder="Rahul Sharma"
                value={signupName}
                onChange={(e) => setSignupName(e.target.value)}
                {...(errors["name"] ? { error: errors["name"] } : {})}
              />

              <Field
                label="Email Address"
                type="email"
                placeholder="rahul.sharma@email.com"
                value={signupEmail}
                onChange={(e) => setSignupEmail(e.target.value)}
                {...(errors["email"] ? { error: errors["email"] } : {})}
              />

              <Field
                label="Password"
                type="password"
                placeholder="At least 6 characters"
                value={signupPassword}
                onChange={(e) => setSignupPassword(e.target.value)}
                {...(errors["password"] ? { error: errors["password"] } : {})}
              />

              <Button type="submit" className="w-full mt-2" disabled={busy}>
                {busy ? (
                  "Creating account…"
                ) : (
                  <span className="flex items-center gap-2">
                    Create & Sign In
                    <ArrowRight className="size-4" />
                  </span>
                )}
              </Button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
