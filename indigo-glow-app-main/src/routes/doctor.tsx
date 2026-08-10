import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CalendarDays,
  CalendarOff,
  CheckCircle2,
  Clock,
  Filter,
  Stethoscope,
  Thermometer,
  UserCheck,
  Users,
  XCircle,
} from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { AestheticDatePicker } from "@/components/AestheticDatePicker";
import { ScheduleChatBot } from "@/components/chatbot/ScheduleChatBot";
import { useToast } from "@/components/Toaster";
import { Badge, Button, GlassCard, Skeleton } from "@/components/ui-kit";
import { api, ApiError, SYMPTOM_LABELS, type DoctorScheduleEntry } from "@/lib/api";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/doctor")({
  head: () => ({
    meta: [
      { title: "Doctor Dashboard — CityCare Clinic" },
      { name: "description", content: "Interactive patient timeline & schedule management." },
      { property: "og:title", content: "Doctor Dashboard — CityCare Clinic" },
      {
        property: "og:description",
        content: "Interactive patient timeline & schedule management.",
      },
    ],
  }),
  component: () => (
    <RoleGuard role="doctor">
      <DoctorDashboard />
    </RoleGuard>
  ),
});

const MASTER_CLINIC_SLOTS = [
  { slot: "10:00", session: "Morning" },
  { slot: "10:30", session: "Morning" },
  { slot: "11:00", session: "Morning" },
  { slot: "11:30", session: "Morning" },
  { slot: "12:00", session: "Morning" },
  { slot: "12:30", session: "Morning" },
  { slot: "17:00", session: "Evening" },
  { slot: "17:30", session: "Evening" },
  { slot: "18:00", session: "Evening" },
  { slot: "18:30", session: "Evening" },
  { slot: "19:00", session: "Evening" },
  { slot: "19:30", session: "Evening" },
] as const;

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

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function tomorrowISO() {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
}

function DoctorDashboard() {
  const [date, setDate] = useState(todayISO());
  const [filterMode, setFilterMode] = useState<"all" | "booked" | "free">("all");
  const toast = useToast();
  const queryClient = useQueryClient();

  const statsQuery = useQuery({
    queryKey: ["doctor-stats"],
    queryFn: api.doctorStats,
    retry: false,
  });

  const scheduleQuery = useQuery({
    queryKey: ["doctor-schedule", date],
    queryFn: () => api.doctorSchedule(date),
    retry: false,
  });

  const unavailabilityQuery = useQuery({
    queryKey: ["doctor-unavailability"],
    queryFn: api.getDoctorUnavailability,
    retry: false,
  });

  const isDayUnavailable = useMemo(() => {
    if (scheduleQuery.data?.is_unavailable) return true;
    return unavailabilityQuery.data?.unavailable_dates?.includes(date) ?? false;
  }, [scheduleQuery.data, unavailabilityQuery.data, date]);

  const toggleUnavailabilityMutation = useMutation({
    mutationFn: (is_unavailable: boolean) =>
      api.toggleDoctorUnavailability({ date, is_unavailable }),
    onSuccess: (res) => {
      toast.success(res.message);
      queryClient.invalidateQueries({ queryKey: ["doctor-schedule", date] });
      queryClient.invalidateQueries({ queryKey: ["doctor-unavailability"] });
    },
    onError: (err: any) => {
      toast.error(err?.message || "Failed to update availability status");
    },
  });

  const stats = statsQuery.data;
  const scheduleData = scheduleQuery.data;

  // Map appointment details to master 12-slot timeline (1 patient per slot)
  const timelineSlots = useMemo(() => {
    const apptsBySlot = new Map<string, DoctorScheduleEntry[]>();
    (scheduleData?.schedule ?? []).forEach((appt) => {
      const list = apptsBySlot.get(appt.slot) || [];
      list.push(appt);
      apptsBySlot.set(appt.slot, list);
    });

    return MASTER_CLINIC_SLOTS.map((item) => {
      const appointments = apptsBySlot.get(item.slot) || [];
      const activeCount = appointments.filter((a) => !a.is_cancelled).length;
      const isFilled = activeCount >= 1;
      return {
        slot: item.slot,
        session: item.session,
        appointments,
        activeCount,
        isFilled,
      };
    });
  }, [scheduleData]);

  const activeBookedCount = useMemo(() => {
    return timelineSlots.reduce((acc, s) => acc + s.activeCount, 0);
  }, [timelineSlots]);

  const filteredTimeline = useMemo(() => {
    if (filterMode === "booked") {
      return timelineSlots.filter((s) => s.appointments.length > 0);
    }
    if (filterMode === "free") {
      return timelineSlots.filter((s) => !s.isFilled);
    }
    return timelineSlots;
  }, [timelineSlots, filterMode]);

  return (
    <AppShell>
      <div className="animate-rise space-y-8">
        {/* Header Bar */}
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <Badge tone="indigo">Doctor Portal</Badge>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight">
              Patient Consultation Timeline
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Dr. Meera Kulkarni · General Physician
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
            <Button
              variant={isDayUnavailable ? "outline" : "secondary"}
              size="sm"
              disabled={toggleUnavailabilityMutation.isPending}
              onClick={() => {
                if (!isDayUnavailable && activeBookedCount > 0) {
                  if (
                    !window.confirm(
                      `Marking ${date} as unavailable will cancel ${activeBookedCount} active appointment(s) and notify patient(s) to reschedule. Continue?`,
                    )
                  ) {
                    return;
                  }
                }
                toggleUnavailabilityMutation.mutate(!isDayUnavailable);
              }}
              className={cn(
                "text-xs gap-1.5 h-9",
                isDayUnavailable
                  ? "border-destructive text-destructive hover:bg-destructive/10"
                  : "bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 border border-amber-500/30",
              )}
            >
              <CalendarOff className="size-4" />
              {isDayUnavailable ? "Mark Day Available" : "Mark Day Unavailable (Off)"}
            </Button>
            <AestheticDatePicker
              selectedDate={date}
              onDateChange={(newDate) => setDate(newDate)}
              label="Schedule Date Filter"
            />
          </div>
        </header>

        {/* Unavailability Notice Banner if Day is Marked Unavailable */}
        {isDayUnavailable && (
          <div className="rounded-2xl border border-destructive/40 bg-destructive/10 p-4 flex flex-wrap items-center justify-between gap-4 text-xs font-medium text-destructive animate-fade-in">
            <div className="flex items-center gap-3">
              <AlertTriangle className="size-5 shrink-0" />
              <div>
                <span className="font-bold block text-sm">
                  Doctor Off-Day / Unavailable ({date})
                </span>
                <span className="text-muted-foreground">
                  You are marked as unavailable on this date. Patient booking for {date} is
                  disabled, and existing bookings have been auto-cancelled with reschedule
                  notifications.
                </span>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="border-destructive/50 text-destructive hover:bg-destructive/20 text-xs"
              onClick={() => toggleUnavailabilityMutation.mutate(false)}
            >
              Re-enable Booking
            </Button>
          </div>
        )}

        {/* Doctor Stats Cards */}
        <div className="grid gap-4 sm:grid-cols-3">
          {[
            {
              icon: Users,
              label: "Total Registered Patients",
              value: statsQuery.isLoading ? "..." : (stats?.total_registered_patients ?? 0),
            },
            {
              icon: CalendarDays,
              label: "Today's Active Visits",
              value: statsQuery.isLoading ? "..." : (stats?.todays_visit_count ?? 0),
            },
            {
              icon: Clock,
              label: "Upcoming Visits",
              value: statsQuery.isLoading ? "..." : (stats?.upcoming_visit_count ?? 0),
            },
          ].map(({ icon: Icon, label, value }) => (
            <GlassCard key={label} className="lift py-5">
              <Icon className="size-5 text-cyan" />
              <p className="mt-3 text-3xl font-semibold text-foreground">{value}</p>
              <p className="text-xs text-muted-foreground">{label}</p>
            </GlassCard>
          ))}
        </div>

        {/* Interactive Patient Timeline per Slot */}
        <GlassCard className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-glass-border pb-4">
            <div>
              <h2 className="flex items-center gap-2 text-base font-semibold text-foreground">
                <Stethoscope className="size-4 text-cyan" /> Slot-by-Slot Timeline ({date})
              </h2>
              <p className="text-xs text-muted-foreground">
                {activeBookedCount} of 12 slots booked ({Math.round((activeBookedCount / 12) * 100)}
                % capacity)
              </p>
            </div>

            {/* Timeline Filter Controls */}
            <div className="flex items-center gap-1 rounded-xl border border-glass-border bg-secondary/30 p-1 text-xs">
              <button
                type="button"
                onClick={() => setFilterMode("all")}
                className={cn(
                  "rounded-lg px-3 py-1.5 font-medium transition-all",
                  filterMode === "all"
                    ? "bg-gradient-to-r from-indigo to-cyan text-cyan-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                All Slots (12)
              </button>
              <button
                type="button"
                onClick={() => setFilterMode("booked")}
                className={cn(
                  "rounded-lg px-3 py-1.5 font-medium transition-all",
                  filterMode === "booked"
                    ? "bg-gradient-to-r from-indigo to-cyan text-cyan-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                Booked Only ({scheduleData?.total_appointments ?? 0})
              </button>
              <button
                type="button"
                onClick={() => setFilterMode("free")}
                className={cn(
                  "rounded-lg px-3 py-1.5 font-medium transition-all",
                  filterMode === "free"
                    ? "bg-gradient-to-r from-indigo to-cyan text-cyan-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                Open Slots ({12 - (scheduleData?.total_appointments ?? 0)})
              </button>
            </div>
          </div>

          {/* Capacity Bar */}
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary/50">
            <div
              className="h-full bg-gradient-to-r from-indigo to-cyan transition-all duration-500"
              style={{ width: `${(activeBookedCount / 12) * 100}%` }}
            />
          </div>

          {/* Timeline Nodes List */}
          {scheduleQuery.isLoading ? (
            <div className="space-y-4 py-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-full" />
              ))}
            </div>
          ) : scheduleQuery.isError ? (
            <p className="py-6 text-center text-sm text-destructive">
              {(scheduleQuery.error as ApiError).message}
            </p>
          ) : filteredTimeline.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No slots match the selected filter.
            </p>
          ) : (
            <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-glass-border">
              {filteredTimeline.map(({ slot, session, appointments, activeCount, isFilled }) => {
                const hasAppointments = appointments.length > 0;

                return (
                  <div key={slot} className="relative group">
                    {/* Timeline Node Icon/Dot */}
                    <div
                      className={cn(
                        "absolute -left-6 top-3 size-5 rounded-full border-2 flex items-center justify-center transition-all bg-background",
                        isFilled
                          ? "border-destructive bg-destructive/20 shadow-[0_0_12px_rgba(239,68,68,0.5)]"
                          : activeCount > 0
                            ? "border-cyan bg-cyan/20 shadow-[0_0_12px_rgba(34,211,238,0.5)]"
                            : "border-glass-border bg-secondary/40",
                      )}
                    >
                      <div
                        className={cn(
                          "size-2 rounded-full",
                          isFilled
                            ? "bg-destructive"
                            : activeCount > 0
                              ? "bg-cyan"
                              : "bg-muted-foreground/30",
                        )}
                      />
                    </div>

                    {/* Timeline Card */}
                    <div
                      className={cn(
                        "rounded-2xl border p-4 transition-all duration-200",
                        isFilled
                          ? "border-destructive/40 bg-glass hover:border-destructive/60"
                          : activeCount > 0
                            ? "border-glass-border bg-glass hover:border-cyan/50 hover:shadow-md"
                            : "border-glass-border/40 bg-secondary/20 hover:border-glass-border",
                      )}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <span className="rounded-xl border border-glass-border bg-card px-3 py-1 text-xs font-semibold text-cyan">
                            {formatSlotDisplay(slot)}
                          </span>
                          <span className="text-[11px] text-muted-foreground font-medium uppercase">
                            {session} Session
                          </span>
                        </div>

                        {/* Status Tag */}
                        {isFilled ? (
                          <Badge tone="danger">
                            <XCircle className="size-3 mr-1" /> Filled ({activeCount}/1 Patient)
                          </Badge>
                        ) : activeCount > 0 ? (
                          <Badge tone="success">
                            <CheckCircle2 className="size-3 mr-1" /> {activeCount}/1 Patient Booked
                          </Badge>
                        ) : (
                          <Badge tone="muted">Open Slot (0/1)</Badge>
                        )}
                      </div>

                      {/* Patient List Content for this slot */}
                      {hasAppointments ? (
                        <div className="mt-4 space-y-3">
                          {appointments.map((appointment) => (
                            <div
                              key={appointment.appointment_id}
                              className={cn(
                                "rounded-xl border p-3 text-xs space-y-2 transition-all",
                                appointment.is_cancelled
                                  ? "border-destructive/30 bg-destructive/5 opacity-70"
                                  : "border-glass-border/60 bg-card/60",
                              )}
                            >
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <p
                                  className={cn(
                                    "font-semibold text-foreground text-sm",
                                    appointment.is_cancelled &&
                                      "line-through text-muted-foreground",
                                  )}
                                >
                                  Patient: {appointment.patient_name}
                                </p>
                                <div className="flex items-center gap-2">
                                  <span className="flex items-center gap-1 rounded-full border border-glass-border bg-secondary/60 px-2 py-0.5 text-[11px] text-foreground font-medium">
                                    <Thermometer className="size-3 text-cyan" />
                                    {appointment.temperature}°F
                                  </span>
                                  {appointment.is_cancelled ? (
                                    <Badge tone="danger">Cancelled</Badge>
                                  ) : (
                                    <Badge tone="success">Active</Badge>
                                  )}
                                </div>
                              </div>

                              {/* Reported Symptoms */}
                              <div className="flex flex-wrap items-center gap-1.5">
                                <span className="text-muted-foreground">Symptoms:</span>
                                {appointment.symptoms.map((sym) => (
                                  <span
                                    key={sym}
                                    className="rounded-md bg-indigo/15 px-2 py-0.5 text-[11px] font-medium text-indigo"
                                  >
                                    {SYMPTOM_LABELS[sym] || sym}
                                  </span>
                                ))}
                              </div>

                              {/* Stated Reason */}
                              <p className="text-foreground/80 italic bg-background/50 rounded-lg p-2 border border-glass-border/40">
                                "{appointment.reason}"
                              </p>

                              {/* Cancellation Reason Notice */}
                              {appointment.is_cancelled && appointment.cancellation_reason && (
                                <p className="text-[11px] text-destructive bg-destructive/10 rounded-lg p-2 border border-destructive/20 font-medium">
                                  ⚠️ {appointment.cancellation_reason}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="mt-2 text-xs text-muted-foreground/60 italic">
                          No patients registered for this slot yet. Available for online booking
                          (0/1).
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </GlassCard>
      </div>
      <ScheduleChatBot />
    </AppShell>
  );
}
