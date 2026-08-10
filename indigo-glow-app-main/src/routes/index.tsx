import { useState, useEffect } from "react";
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import {
  Building2,
  CheckCircle2,
  Clock,
  ShieldCheck,
  Stethoscope,
  Users,
  Activity,
  ArrowRight,
  Heart,
  Sparkles,
} from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { Badge, Button, GlassCard } from "@/components/ui-kit";
import { CascadingAuthCard } from "@/components/CascadingAuthCard";
import { useSession } from "@/lib/auth";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "CityCare Platform — Multi-Tenant Healthcare & Clinic Bookings" },
      {
        name: "description",
        content:
          "Discover top hospitals, browse specialist doctors, and book instant appointment slots across accredited healthcare clinics.",
      },
      { property: "og:title", content: "CityCare Platform — Multi-Tenant Healthcare" },
      {
        property: "og:description",
        content: "Book clinic appointments with verified specialist doctors across hospitals.",
      },
    ],
  }),
  component: LandingRoute,
});

function LandingRoute() {
  return <LandingPage />;
}

export function LandingPage({ defaultAuthTab }: { defaultAuthTab?: "login" | "signup" | null }) {
  const { user } = useSession();
  const navigate = useNavigate();
  const [authSheet, setAuthSheet] = useState<"login" | "signup" | null>(defaultAuthTab ?? null);

  useEffect(() => {
    if (defaultAuthTab) {
      setAuthSheet(defaultAuthTab);
    }
  }, [defaultAuthTab]);

  function triggerAuthSheet(mode: "login" | "signup") {
    setAuthSheet(mode);
  }

  function closeAuthSheet() {
    setAuthSheet(null);
  }

  return (
    <AppShell onOpenAuth={(mode) => triggerAuthSheet(mode)}>
      <section className="grid items-center gap-10 py-6 lg:grid-cols-[1.1fr_1fr] min-h-[520px]">
        {/* Left Side: Hero Title & CTA */}
        <div className="animate-rise space-y-6">
          <Badge tone="cyan">Multi-Tenant Healthcare Platform</Badge>
          <h1 className="text-4xl leading-[1.05] font-bold tracking-tight text-balance sm:text-6xl text-foreground">
            Healthcare across top clinics,{" "}
            <span className="bg-gradient-to-r from-indigo via-cyan to-teal-400 bg-clip-text text-transparent">
              booked in seconds
            </span>
          </h1>
          <p className="max-w-lg text-base text-muted-foreground">
            Find accredited hospitals, select verified specialist doctors, and reserve digital
            consultation slots in advance.
          </p>

          {/* Direct CTA Action Button */}
          <div className="flex items-center gap-3 pt-2">
            <Link to="/hospitals">
              <Button variant="primary" size="md">
                Browse Hospitals & Clinics <ArrowRight className="size-4 ml-1" />
              </Button>
            </Link>
          </div>

          <dl className="grid max-w-md grid-cols-3 gap-4 pt-2">
            {[
              { icon: Building2, label: "Hospitals", value: "Verified" },
              { icon: Stethoscope, label: "Specialists", value: "Multi-Specialty" },
              { icon: ShieldCheck, label: "Reservations", value: "Instant" },
            ].map(({ icon: Icon, label, value }) => (
              <div key={label} className="glass rounded-2xl px-3 py-3">
                <Icon className="size-4 text-cyan" />
                <dd className="mt-2 text-base font-bold text-foreground">{value}</dd>
                <dt className="text-[11px] text-muted-foreground">{label}</dt>
              </div>
            ))}
          </dl>
        </div>

        {/* Right Side: Animated Card OR Auth Sheet */}
        <div className="relative flex justify-center items-center w-full min-h-[460px]">
          {authSheet ? (
            <div className="w-full flex justify-center">
              <CascadingAuthCard initialTab={authSheet} onClose={closeAuthSheet} />
            </div>
          ) : (
            <GlassCard className="w-full animate-throw-up glow-indigo lift space-y-6">
              <div className="flex items-center gap-4">
                <span className="flex size-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo to-cyan shadow-md">
                  <Building2 className="size-7 text-cyan-foreground" />
                </span>
                <div>
                  <h2 className="text-xl font-bold tracking-tight text-foreground">
                    CityCare Healthcare
                  </h2>
                  <p className="text-sm font-medium text-cyan">Integrated Platform</p>
                  <p className="text-xs text-muted-foreground">Tenant Hospital & Clinic Network</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-2xl border border-glass-border p-3 bg-secondary/30">
                  <p className="text-[11px] text-muted-foreground">Accredited Clinics</p>
                  <p className="mt-1 font-semibold text-foreground">Active Across Cities</p>
                </div>
                <div className="rounded-2xl border border-glass-border p-3 bg-secondary/30">
                  <p className="text-[11px] text-muted-foreground">Digital Queue</p>
                  <p className="mt-1 font-semibold text-foreground">Zero Line Waiting</p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-muted-foreground">Available Specialties:</span>
                {["General Physician", "Cardiology", "Dermatology", "Pediatrics"].map((spec) => (
                  <Badge key={spec} tone="indigo">
                    {spec}
                  </Badge>
                ))}
              </div>

              {!user && (
                <div className="border-t border-glass-border pt-4">
                  <Button
                    onClick={() => triggerAuthSheet("login")}
                    className="w-full gap-2 text-xs font-semibold"
                    variant="primary"
                  >
                    Sign In to Access Platform
                    <ArrowRight className="size-4" />
                  </Button>
                </div>
              )}
            </GlassCard>
          )}
        </div>
      </section>

      <Sections triggerAuthSheet={triggerAuthSheet} user={user} />
    </AppShell>
  );
}

const STEPS = [
  {
    icon: Building2,
    title: "1. Select Hospital",
    body: "Browse verified hospital tenants by city and explore available medical departments.",
  },
  {
    icon: Stethoscope,
    title: "2. Pick Specialist",
    body: "Select an active doctor profile based on specialization, fees, and consultation hours.",
  },
  {
    icon: Clock,
    title: "3. Choose Slot",
    body: "Pick a digital consultation slot for today or up to 7 days in advance.",
  },
  {
    icon: CheckCircle2,
    title: "4. Walk-in Confirmed",
    body: "Log symptoms ahead of time and walk into your consultation with zero waiting.",
  },
];

const SPECIALTIES = [
  {
    title: "General Medicine",
    desc: "Routine checkups, fever, cold, and preventive health screenings.",
  },
  {
    title: "Cardiology",
    desc: "Heart health evaluations, blood pressure monitoring, and cardiovascular care.",
  },
  {
    title: "Dermatology",
    desc: "Skin consultations, allergic treatment, and medical dermatology.",
  },
  {
    title: "Pediatrics",
    desc: "Child healthcare, vaccination advice, and pediatric consultation.",
  },
  { title: "Orthopedics", desc: "Joint pain, bone fracture recovery, and musculoskeletal care." },
  { title: "Neurology", desc: "Nerve health, migraine management, and neurological evaluations." },
];

const FAQS = [
  {
    q: "How do I book an appointment at a clinic?",
    a: "Log in to your account, click 'Browse Hospitals', choose a clinic and doctor, then pick an unbooked slot.",
  },
  {
    q: "Can I book appointments at multiple hospitals?",
    a: "Yes! CityCare is a multi-tenant platform. Patients can book with specialists at different hospitals from a single account.",
  },
  {
    q: "How do hospital owners list their doctors?",
    a: "Hospital owners receive an owner account from the Super Admin and manage their doctor staff directly from their owner dashboard.",
  },
  {
    q: "Can I cancel an appointment if my plans change?",
    a: "Yes, you can cancel any active booking from your patient dashboard. The slot immediately becomes available for other patients.",
  },
];

function Sections({
  triggerAuthSheet,
  user,
}: {
  triggerAuthSheet: (mode: "login" | "signup") => void;
  user: any;
}) {
  return (
    <>
      {/* How It Works */}
      <section className="border-t border-glass-border py-16">
        <h2 className="text-2xl font-bold tracking-tight sm:text-3xl text-foreground">
          How the Platform Works
        </h2>
        <p className="mt-2 max-w-lg text-sm text-muted-foreground">
          Four seamless steps from hospital discovery to appointment confirmation.
        </p>
        <ol className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map(({ icon: Icon, title, body }) => (
            <li key={title}>
              <GlassCard className="lift h-full space-y-3">
                <span className="flex size-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo to-cyan text-cyan-foreground">
                  <Icon className="size-5" />
                </span>
                <h3 className="text-base font-semibold text-foreground">{title}</h3>
                <p className="text-sm text-muted-foreground">{body}</p>
              </GlassCard>
            </li>
          ))}
        </ol>
      </section>

      {/* Medical Specialties */}
      <section className="border-t border-glass-border py-16">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl text-foreground">
              Medical Specialties
            </h2>
            <p className="mt-2 max-w-lg text-sm text-muted-foreground">
              Consult with board-certified specialists across various medical disciplines.
            </p>
          </div>
          <Link to="/hospitals">
            <Button variant="primary" size="sm">
              Browse Hospitals & Clinics <ArrowRight className="size-4 ml-1" />
            </Button>
          </Link>
        </div>

        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {SPECIALTIES.map((spec) => (
            <GlassCard key={spec.title} className="lift space-y-2">
              <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
                <Heart className="size-4 text-cyan" /> {spec.title}
              </h3>
              <p className="text-sm text-muted-foreground">{spec.desc}</p>
            </GlassCard>
          ))}
        </div>
      </section>

      {/* FAQs */}
      <section className="border-t border-glass-border py-16">
        <h2 className="text-2xl font-bold tracking-tight sm:text-3xl text-foreground">
          Frequently Asked Questions
        </h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          {FAQS.map((f) => (
            <GlassCard key={f.q} className="lift space-y-2">
              <h3 className="text-sm font-semibold text-foreground">{f.q}</h3>
              <p className="text-sm text-muted-foreground">{f.a}</p>
            </GlassCard>
          ))}
        </div>
      </section>
    </>
  );
}
