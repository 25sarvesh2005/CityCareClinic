import { useEffect, useState } from "react";
import { Link, createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  Calendar,
  Clock,
  FileText,
  MapPin,
  Pill,
  Search,
  ChevronRight,
  AlertTriangle,
  Stethoscope,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { Badge, Button, ConfirmDialog, GlassCard, Skeleton } from "@/components/ui-kit";
import { useToast } from "@/components/Toaster";
import { api, ApiError, SYMPTOM_LABELS, type Appointment, type Hospital } from "@/lib/api";

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "Patient Dashboard — CityCare Platform" },
      { name: "description", content: "Manage your booked appointments and discover clinics." },
      { property: "og:title", content: "Patient Dashboard — CityCare Platform" },
    ],
  }),
  component: () => (
    <RoleGuard role="patient">
      <PatientDashboard />
    </RoleGuard>
  ),
});

function formatSlotDisplay(slot: string) {
  if (!slot) return "";
  const parts = slot.split(":");
  if (parts.length < 2) return slot;
  let h = parseInt(parts[0] ?? "0", 10);
  const mStr = parts[1] ?? "00";
  const ampm = h >= 12 ? "PM" : "AM";
  if (h > 12) h -= 12;
  if (h === 0) h = 12;
  return `${h}:${mStr} ${ampm}`;
}

function DashboardStatCard({
  icon: Icon,
  label,
  value,
  detail,
  tone = "cyan",
}: {
  icon: LucideIcon;
  label: string;
  value: string | number;
  detail: string;
  tone?: "cyan" | "indigo" | "success";
}) {
  return (
    <div className="rounded-2xl border border-glass-border bg-card/75 p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            {label}
          </p>
          <p className="mt-2 text-2xl font-bold tracking-tight text-foreground">{value}</p>
          <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
        </div>
        <span
          className={`flex size-10 shrink-0 items-center justify-center rounded-xl border ${
            tone === "indigo"
              ? "border-indigo/15 bg-indigo/10 text-indigo"
              : tone === "success"
                ? "border-success/15 bg-success/10 text-success"
                : "border-cyan/15 bg-cyan/10 text-cyan"
          }`}
        >
          <Icon className="size-5" />
        </span>
      </div>
    </div>
  );
}

function PatientDashboard() {
  const toast = useToast();
  const qc = useQueryClient();

  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [loadingHospitals, setLoadingHospitals] = useState(true);
  const [cityFilter, setCityFilter] = useState("");
  const [pendingCancel, setPendingCancel] = useState<Appointment | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await api.browseHospitals();
        setHospitals(res);
      } catch (err: unknown) {
        toast.error("Failed to load clinics", (err as ApiError).message);
      } finally {
        setLoadingHospitals(false);
      }
    }
    load();
  }, [toast]);

  const apptQuery = useQuery({
    queryKey: ["my-appointments"],
    queryFn: api.myAppointments,
    retry: false,
  });

  const prescriptionsQuery = useQuery({
    queryKey: ["my-prescriptions"],
    queryFn: api.myPrescriptions,
    retry: false,
  });

  const cancel = useMutation({
    mutationFn: (id: string) => api.cancelAppointment(id),
    onSuccess: () => {
      toast.info("Appointment cancelled", "The slot has been freed for other patients.");
      setPendingCancel(null);
      qc.invalidateQueries({ queryKey: ["my-appointments"] });
    },
    onError: (err) => toast.error("Couldn't cancel appointment", (err as ApiError).message),
  });

  const appointments = apptQuery.data ?? [];
  const prescriptions = prescriptionsQuery.data ?? [];
  const activeAppointments = appointments.filter(
    (a) => !a.is_cancelled && a.status !== "completed" && a.status !== "rejected",
  ).length;
  const completedVisits = appointments.filter((a) => a.status === "completed").length;
  const latestPrescription = prescriptions[0];

  return (
    <AppShell>
      <div className="animate-rise space-y-7">
        {/* Top Header */}
        <div className="flex flex-col justify-between gap-4 rounded-2xl border border-glass-border bg-card/80 p-5 shadow-sm sm:flex-row sm:items-center">
          <div>
            <span className="inline-flex rounded-lg border border-cyan/15 bg-cyan/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider text-cyan">
              Patient workspace
            </span>
            <h1 className="mt-3 text-3xl font-bold tracking-tight text-foreground">
              My care dashboard
            </h1>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
              Track consultations, prescriptions, and nearby CityCare clinics from one focused
              patient view.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/prescription-ai">
              <Button variant="primary" size="sm" className="bg-gradient-to-r from-cyan to-indigo text-white shadow-sm border-none gap-1.5">
                <Sparkles className="size-4 text-cyan-200" /> Prescription AI Workspace
              </Button>
            </Link>
            <Link to="/hospitals">
              <Button variant="outline" size="sm">
                <Building2 className="size-4" /> Browse clinics
              </Button>
            </Link>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          <DashboardStatCard
            icon={Calendar}
            label="Active bookings"
            value={activeAppointments}
            detail={`${completedVisits} completed visit${completedVisits === 1 ? "" : "s"}`}
            tone="cyan"
          />
          <DashboardStatCard
            icon={FileText}
            label="Prescriptions"
            value={prescriptions.length}
            detail={latestPrescription ? `Latest: ${latestPrescription.date}` : "No records yet"}
            tone="indigo"
          />
          <DashboardStatCard
            icon={Stethoscope}
            label="Clinic network"
            value={loadingHospitals ? "..." : hospitals.length}
            detail={cityFilter ? `Filtered by ${cityFilter}` : "Available clinics"}
            tone="success"
          />
        </div>

        <div className="grid gap-6 lg:grid-cols-[1.35fr_1fr]">
          {/* Left Column: My Booked Appointments */}
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="flex items-center gap-2 text-lg font-bold text-foreground">
                <Calendar className="size-5 text-cyan" /> Booked appointments
              </h2>
              <Badge tone="muted">{appointments.length} total</Badge>
            </div>

            {apptQuery.isLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-28" />
                <Skeleton className="h-28" />
              </div>
            ) : apptQuery.isError ? (
              <GlassCard className="py-6 text-center">
                <p className="text-sm text-destructive font-medium">
                  {(apptQuery.error as ApiError).message}
                </p>
              </GlassCard>
            ) : appointments.length === 0 ? (
              <GlassCard className="space-y-3 py-10 text-center">
                <Calendar className="mx-auto size-10 text-muted-foreground/50" />
                <h3 className="text-base font-semibold text-foreground">No appointments yet</h3>
                <p className="mx-auto max-w-sm text-xs text-muted-foreground">
                  Explore the CityCare clinic network and reserve a consultation slot with a
                  specialist.
                </p>
                <Link to="/hospitals">
                  <Button variant="outline" size="sm">
                    Find a specialist <ChevronRight className="ml-1 size-4" />
                  </Button>
                </Link>
              </GlassCard>
            ) : (
              <div className="space-y-3">
                {appointments.map((a) => (
                  <GlassCard key={a.appointment_id} className="lift space-y-4 border-border/60">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2 text-sm font-bold text-foreground">
                          <Clock className="size-4 text-cyan" />
                          <span>
                            {a.date} · {formatSlotDisplay(a.slot)}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-muted-foreground">
                          Patient:{" "}
                          <span className="font-medium text-foreground">{a.patient_name}</span>
                        </p>
                      </div>
                      <Badge tone={a.is_cancelled ? "danger" : "success"}>
                        {a.is_cancelled ? "Cancelled" : "Active booking"}
                      </Badge>
                    </div>

                    <div className="space-y-1 rounded-xl border border-glass-border bg-muted/35 p-3 text-xs text-muted-foreground">
                      <p>
                        <span className="font-medium text-foreground">Symptoms:</span>{" "}
                        {a.symptoms.map((s) => SYMPTOM_LABELS[s]).join(", ")}
                      </p>
                      <p>
                        <span className="font-medium text-foreground">Temp:</span> {a.temperature}°F
                      </p>
                      <p className="italic text-foreground/90 mt-1">"{a.reason}"</p>
                    </div>

                    {a.is_cancelled ? (
                      <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-3.5 space-y-2 text-xs">
                        <div className="flex items-center gap-2 text-destructive font-bold">
                          <AlertTriangle className="size-4 shrink-0" />
                          <span>Appointment Cancelled</span>
                        </div>
                        <p className="text-muted-foreground">
                          {a.cancellation_reason ||
                            "This appointment has been cancelled. Please select another available date to consult with your doctor."}
                        </p>
                        <div className="pt-1">
                          <Link to="/hospitals">
                            <Button variant="primary" size="sm" className="text-xs h-8 py-1 px-3">
                              Reschedule <ChevronRight className="ml-1 size-3.5" />
                            </Button>
                          </Link>
                        </div>
                      </div>
                    ) : (
                      <div className="pt-1 flex flex-wrap items-center justify-between gap-2 border-t border-glass-border/40">
                        <div className="flex items-center gap-2 text-xs">
                          <span className="text-muted-foreground font-medium">Status:</span>
                          {a.status === "pending" && <Badge tone="warning">Pending Approval</Badge>}
                          {a.status === "accepted" && <Badge tone="cyan">Accepted</Badge>}
                          {a.status === "completed" && <Badge tone="success">Completed</Badge>}
                          {a.status === "rejected" && <Badge tone="danger">Declined</Badge>}
                          {(!a.status || a.status === "active") && (
                            <Badge tone="success">Active</Badge>
                          )}
                        </div>

                        <div className="flex items-center gap-2">
                          {(a.pdf_url || a.prescription_id || a.status === "completed") && (
                            <Button
                              variant="cyan"
                              size="sm"
                              onClick={() =>
                                window.open(api.getPdfUrl(a.pdf_url, a.prescription_id), "_blank")
                              }
                            >
                              Download prescription
                            </Button>
                          )}
                          {a.status !== "completed" && (
                            <Button variant="danger" size="sm" onClick={() => setPendingCancel(a)}>
                              Cancel Appointment
                            </Button>
                          )}
                        </div>
                      </div>
                    )}
                  </GlassCard>
                ))}
              </div>
            )}
          </div>

          {/* Right Column: My Prescriptions & Fast Clinic Discovery */}
          <div className="space-y-6">
            {/* My Prescriptions Widget */}
            <div className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <h2 className="flex items-center gap-2 text-lg font-bold text-foreground">
                  <FileText className="size-5 text-indigo" /> Prescriptions
                </h2>
                <Badge tone="muted">{prescriptions.length} records</Badge>
              </div>

              <GlassCard className="space-y-3 border-border/60">
                {prescriptionsQuery.isLoading ? (
                  <Skeleton className="h-24" />
                ) : prescriptions.length === 0 ? (
                  <p className="py-4 text-center text-xs text-muted-foreground">
                    No medical prescriptions issued yet. Prescriptions will appear here after your
                    doctor accepts and completes your consultation.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {prescriptions.map((rx) => (
                      <div
                        key={rx.prescription_id}
                        className="space-y-3 rounded-xl border border-glass-border/70 bg-background/45 p-4 text-xs transition-all hover:border-cyan/45"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="min-w-0">
                            <span className="block truncate text-sm font-bold text-foreground">
                              {rx.diagnosis}
                            </span>
                            <p className="text-[11px] text-muted-foreground">
                              {rx.doctor_name} · {rx.date}
                            </p>
                          </div>
                          <Badge tone="success">PDF ready</Badge>
                        </div>

                        <div className="flex flex-wrap gap-1.5">
                          {rx.medications.map((m, idx) => (
                            <span
                              key={idx}
                              className="inline-flex items-center gap-1.5 rounded-lg border border-cyan/15 bg-cyan/10 px-2.5 py-1 text-[11px] font-medium text-foreground"
                            >
                              <Pill className="size-3 text-cyan" />
                              {m.medicine_name} ({m.dosage})
                            </span>
                          ))}
                        </div>

                        {rx.notes && (
                          <p className="rounded-lg border border-glass-border/50 bg-muted/35 p-2.5 text-[11px] leading-relaxed text-foreground/80">
                            <span className="font-semibold text-foreground">Doctor note:</span>{" "}
                            {rx.notes}
                          </p>
                        )}

                        <div className="flex justify-end pt-1">
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-xs py-1 px-3"
                            onClick={() =>
                              window.open(api.getPdfUrl(rx.pdf_url, rx.prescription_id), "_blank")
                            }
                          >
                            View PDF
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </GlassCard>
            </div>

            {/* Fast Hospital Discovery Widget */}
            <div className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <h2 className="flex items-center gap-2 text-lg font-bold text-foreground">
                  <Building2 className="size-5 text-cyan" /> Nearby clinics
                </h2>
                <Badge tone="muted">
                  {loadingHospitals ? "Loading" : `${hospitals.length} found`}
                </Badge>
              </div>

              <GlassCard className="space-y-4 border-border/60">
                <div className="relative">
                  <Search className="absolute left-3.5 top-3 size-4 text-muted-foreground" />
                  <input
                    className="w-full rounded-xl border border-input bg-background/60 py-2 pl-10 pr-4 text-xs text-foreground transition-colors placeholder:text-muted-foreground/60 focus:border-cyan/60 focus:outline-none focus:ring-2 focus:ring-ring/30"
                    placeholder="Filter clinics by city..."
                    value={cityFilter}
                    onChange={(e) => setCityFilter(e.target.value)}
                  />
                </div>

                {loadingHospitals ? (
                  <Skeleton className="h-40" />
                ) : hospitals.length === 0 ? (
                  <div className="py-6 text-center text-xs text-muted-foreground">
                    No active clinics found.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {hospitals.slice(0, 3).map((h) => (
                      <div
                        key={h.hospital_id}
                        className="space-y-2 rounded-xl border border-glass-border/70 bg-background/45 p-3.5 transition-all hover:border-cyan/45"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <h4 className="truncate text-sm font-semibold text-foreground">
                            {h.name}
                          </h4>
                          <span className="flex shrink-0 items-center gap-1 text-[10px] font-medium text-cyan">
                            <MapPin className="size-3" /> {h.city}
                          </span>
                        </div>
                        <p className="line-clamp-1 text-[11px] text-muted-foreground">
                          {h.address}
                        </p>
                        <div className="flex justify-end pt-1">
                          <Link
                            to="/hospital-doctors"
                            search={{ hospital_id: h.hospital_id, hospital_name: h.name }}
                          >
                            <Button variant="outline" size="sm" className="text-xs py-1 px-3">
                              View doctors <ChevronRight className="ml-1 size-3" />
                            </Button>
                          </Link>
                        </div>
                      </div>
                    ))}
                    {hospitals.length > 3 && (
                      <div className="pt-2 text-center">
                        <Link
                          to="/hospitals"
                          className="text-xs font-medium text-cyan hover:underline"
                        >
                          View all {hospitals.length} clinics
                        </Link>
                      </div>
                    )}
                  </div>
                )}
              </GlassCard>
            </div>
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={pendingCancel !== null}
        title="Cancel this appointment?"
        description="This action will release the slot immediately for other patients. The appointment record will remain in your history as cancelled."
        confirmLabel="Yes, Cancel Slot"
        busy={cancel.isPending}
        onConfirm={() => pendingCancel && cancel.mutate(pendingCancel.appointment_id)}
        onCancel={() => setPendingCancel(null)}
      />
    </AppShell>
  );
}
