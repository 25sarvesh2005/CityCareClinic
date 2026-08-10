import { useEffect, useState } from "react";
import { Link, createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  Calendar,
  Clock,
  MapPin,
  Phone,
  Search,
  ChevronRight,
  AlertCircle,
  AlertTriangle,
  XCircle,
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
        const list = await api.browseHospitals(cityFilter);
        setHospitals(list);
      } catch (err) {
        console.error(err);
      } finally {
        setLoadingHospitals(false);
      }
    }
    load();
  }, [cityFilter]);

  const apptQuery = useQuery({
    queryKey: ["my-appointments"],
    queryFn: api.myAppointments,
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

  return (
    <AppShell>
      <div className="animate-rise space-y-8">
        {/* Top Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-glass-border pb-6">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-cyan">
              Patient Hub
            </span>
            <h1 className="text-3xl font-bold tracking-tight text-foreground">
              My Appointments & Clinics
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Book specialist consultations across accredited hospital tenants and manage your
              visits.
            </p>
          </div>
          <Link to="/hospitals">
            <Button variant="primary" size="sm">
              <Building2 className="size-4" /> Browse All Clinics
            </Button>
          </Link>
        </div>

        <div className="grid gap-8 lg:grid-cols-[1.3fr_1fr]">
          {/* Left Column: My Booked Appointments */}
          <div className="space-y-4">
            <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
              <Calendar className="size-5 text-cyan" /> My Booked Appointments
            </h2>

            {apptQuery.isLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-28" />
                <Skeleton className="h-28" />
              </div>
            ) : apptQuery.isError ? (
              <GlassCard className="text-center py-6">
                <p className="text-sm text-destructive font-medium">
                  {(apptQuery.error as ApiError).message}
                </p>
              </GlassCard>
            ) : (apptQuery.data ?? []).length === 0 ? (
              <GlassCard className="text-center py-10 space-y-3">
                <Calendar className="mx-auto size-10 text-muted-foreground/50" />
                <h3 className="text-base font-semibold text-foreground">No Booked Appointments</h3>
                <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                  You haven't reserved any consultation slots yet. Explore our verified hospital
                  network to book a doctor.
                </p>
                <Link to="/hospitals">
                  <Button variant="outline" size="sm">
                    Find a Specialist <ChevronRight className="size-4 ml-1" />
                  </Button>
                </Link>
              </GlassCard>
            ) : (
              <div className="space-y-4">
                {(apptQuery.data ?? []).map((a) => (
                  <GlassCard key={a.appointment_id} className="lift space-y-3">
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
                        {a.is_cancelled ? "Cancelled" : "Active Booking"}
                      </Badge>
                    </div>

                    <div className="text-xs text-muted-foreground space-y-1 bg-secondary/30 p-3 rounded-xl border border-glass-border">
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
                              Find Clinic to Reschedule{" "}
                              <ChevronRight className="size-3.5 ml-1" />
                            </Button>
                          </Link>
                        </div>
                      </div>
                    ) : (
                      <div className="pt-1 flex justify-end">
                        <Button variant="danger" size="sm" onClick={() => setPendingCancel(a)}>
                          Cancel Appointment
                        </Button>
                      </div>
                    )}
                  </GlassCard>
                ))}
              </div>
            )}
          </div>

          {/* Right Column: Fast Hospital Discovery Widget */}
          <div className="space-y-4">
            <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
              <Building2 className="size-5 text-indigo" /> Browse Clinics Nearby
            </h2>

            <GlassCard className="space-y-4">
              <div className="relative">
                <Search className="absolute left-3.5 top-3 size-4 text-muted-foreground" />
                <input
                  className="w-full rounded-full border border-input bg-secondary/40 pl-10 pr-4 py-2 text-xs text-foreground focus:border-cyan/60 focus:outline-none"
                  placeholder="Filter clinics by city..."
                  value={cityFilter}
                  onChange={(e) => setCityFilter(e.target.value)}
                />
              </div>

              {loadingHospitals ? (
                <Skeleton className="h-40" />
              ) : hospitals.length === 0 ? (
                <div className="text-center py-6 text-xs text-muted-foreground">
                  No active clinics found.
                </div>
              ) : (
                <div className="space-y-3">
                  {hospitals.slice(0, 3).map((h) => (
                    <div
                      key={h.hospital_id}
                      className="p-3 rounded-xl border border-glass-border bg-card/60 hover:border-cyan/50 transition-all space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <h4 className="font-semibold text-sm text-foreground">{h.name}</h4>
                        <span className="text-[10px] text-cyan font-medium flex items-center gap-1">
                          <MapPin className="size-3" /> {h.city}
                        </span>
                      </div>
                      <p className="text-[11px] text-muted-foreground line-clamp-1">{h.address}</p>
                      <div className="pt-1 flex justify-end">
                        <Link
                          to="/hospital-doctors"
                          search={{ hospital_id: h.hospital_id, hospital_name: h.name }}
                        >
                          <Button variant="outline" size="sm" className="text-xs py-1 px-3">
                            View Doctors <ChevronRight className="size-3 ml-1" />
                          </Button>
                        </Link>
                      </div>
                    </div>
                  ))}
                  {hospitals.length > 3 && (
                    <div className="pt-2 text-center">
                      <Link
                        to="/hospitals"
                        className="text-xs text-cyan font-medium hover:underline"
                      >
                        View All {hospitals.length} Clinics →
                      </Link>
                    </div>
                  )}
                </div>
              )}
            </GlassCard>
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
