import { useEffect, useState, useMemo } from "react";
import { Link, createFileRoute } from "@tanstack/react-router";
import {
  Building2,
  Users,
  Calendar,
  Clock,
  Activity,
  UserPlus,
  CheckCircle,
  AlertTriangle,
  Stethoscope,
  CalendarOff,
  UserCheck,
} from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { AestheticDatePicker } from "@/components/AestheticDatePicker";
import { ScheduleChatBot } from "@/components/chatbot/ScheduleChatBot";
import { Badge, Button, GlassCard, Skeleton } from "@/components/ui-kit";
import { api, type HospitalStats, type DoctorProfile } from "@/lib/api";

export const Route = createFileRoute("/hospital-owner/dashboard")({
  component: HospitalOwnerDashboard,
});

function HospitalOwnerDashboard() {
  return (
    <RoleGuard role="hospital_owner">
      <AppShell>
        <DashboardContent />
        <ScheduleChatBot />
      </AppShell>
    </RoleGuard>
  );
}

function DashboardContent() {
  const [stats, setStats] = useState<HospitalStats | null>(null);
  const [doctors, setDoctors] = useState<DoctorProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDoctorId, setSelectedDoctorId] = useState<string>("all");
  const [selectedDate, setSelectedDate] = useState<string>(() =>
    new Date().toISOString().slice(0, 10),
  );

  useEffect(() => {
    async function loadData() {
      try {
        const [statsData, doctorsData] = await Promise.all([
          api.getHospitalStatsOwner(),
          api.listOwnerDoctors(),
        ]);
        setStats(statsData);
        setDoctors(doctorsData);
      } catch (err) {
        console.error("Failed to load hospital owner data", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const activeDoctor = useMemo(() => {
    if (selectedDoctorId === "all") return null;
    return doctors.find((d) => d.profile_id === selectedDoctorId) || null;
  }, [doctors, selectedDoctorId]);

  // Display doctors based on filter selection
  const displayedDoctors = useMemo(() => {
    if (!activeDoctor) return doctors;
    return [activeDoctor];
  }, [doctors, activeDoctor]);

  // Collect off-dates for date picker strip
  const offDatesForPicker = useMemo(() => {
    if (activeDoctor) {
      return activeDoctor.unavailable_dates || [];
    }
    const dates = new Set<string>();
    doctors.forEach((d) => {
      (d.unavailable_dates || []).forEach((dt) => dates.add(dt));
    });
    return Array.from(dates);
  }, [doctors, activeDoctor]);

  // Breakdown for selected date
  const unavailableDoctorsCount = useMemo(() => {
    return displayedDoctors.filter((d) => (d.unavailable_dates || []).includes(selectedDate)).length;
  }, [displayedDoctors, selectedDate]);

  const availableDoctorsCount = displayedDoctors.length - unavailableDoctorsCount;

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-glass-border pb-6">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-cyan">
            Hospital Management
          </span>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">
            {loading ? "Hospital Dashboard" : stats?.hospital_name || "Hospital Dashboard"}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Overview of doctors, appointment bookings, and clinic operational status.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link to="/hospital-owner/doctors">
            <Button variant="primary" size="sm">
              <Users className="size-4" /> Manage Doctors
            </Button>
          </Link>
        </div>
      </div>

      {/* Hospital Status Banner */}
      {stats && (
        <GlassCard className="flex flex-col sm:flex-row items-center justify-between gap-4 border-cyan/20 bg-cyan/5">
          <div className="flex items-center gap-3">
            <Building2 className="size-8 text-cyan" />
            <div>
              <h3 className="font-semibold text-foreground">{stats.hospital_name}</h3>
              <p className="text-xs text-muted-foreground">Tenant ID: {stats.hospital_id}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {stats.is_active ? (
              <Badge tone="success">
                <CheckCircle className="size-3 mr-1 inline" /> Operational
              </Badge>
            ) : (
              <Badge tone="danger">
                <AlertTriangle className="size-3 mr-1 inline" /> Suspended
              </Badge>
            )}
            {stats.is_approved ? (
              <Badge tone="cyan">Live on Platform</Badge>
            ) : (
              <Badge tone="muted">Pending Admin Approval</Badge>
            )}
          </div>
        </GlassCard>
      )}

      {/* Stats Cards Grid */}
      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
        </div>
      ) : stats ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <GlassCard className="space-y-2">
            <div className="flex items-center justify-between text-muted-foreground">
              <span className="text-xs font-medium uppercase tracking-wider">Total Doctors</span>
              <Users className="size-4 text-cyan" />
            </div>
            <div className="text-2xl font-bold text-foreground">{stats.total_doctors}</div>
            <Badge tone="success">{stats.active_doctors} Active</Badge>
          </GlassCard>

          <GlassCard className="space-y-2">
            <div className="flex items-center justify-between text-muted-foreground">
              <span className="text-xs font-medium uppercase tracking-wider">Today's Visits</span>
              <Clock className="size-4 text-indigo" />
            </div>
            <div className="text-2xl font-bold text-foreground">{stats.todays_appointments}</div>
            <span className="text-xs text-muted-foreground">Scheduled for today</span>
          </GlassCard>

          <GlassCard className="space-y-2">
            <div className="flex items-center justify-between text-muted-foreground">
              <span className="text-xs font-medium uppercase tracking-wider">Upcoming Visits</span>
              <Calendar className="size-4 text-cyan" />
            </div>
            <div className="text-2xl font-bold text-foreground">{stats.upcoming_appointments}</div>
            <span className="text-xs text-muted-foreground">Future bookings</span>
          </GlassCard>

          <GlassCard className="space-y-2">
            <div className="flex items-center justify-between text-muted-foreground">
              <span className="text-xs font-medium uppercase tracking-wider">Total Bookings</span>
              <Activity className="size-4 text-success" />
            </div>
            <div className="text-2xl font-bold text-foreground">{stats.total_appointments}</div>
            <span className="text-xs text-muted-foreground">All-time count</span>
          </GlassCard>
        </div>
      ) : null}

      {/* Date-Wise Doctor Availability & Schedule Section */}
      <GlassCard className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-glass-border pb-4">
          <div>
            <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
              <Calendar className="size-5 text-cyan" /> Doctor Off-Day & Schedule Analyzer
            </h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Inspect individual doctor off-days, date-wise availability rosters, and schedule status.
            </p>
          </div>

          {/* Doctor Filter Selector */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground font-medium">Select Doctor:</span>
              <select
                className="rounded-xl border border-input bg-secondary/40 px-3 py-1.5 text-xs text-foreground focus:border-cyan/60 focus:outline-none"
                value={selectedDoctorId}
                onChange={(e) => setSelectedDoctorId(e.target.value)}
              >
                <option value="all">All Doctors Staff ({doctors.length})</option>
                {doctors.map((d) => (
                  <option key={d.profile_id} value={d.profile_id}>
                    {d.name || "Doctor"} — {d.specialization}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <Badge tone="success">{availableDoctorsCount} Available</Badge>
              {unavailableDoctorsCount > 0 ? (
                <Badge tone="danger">{unavailableDoctorsCount} Marked Off</Badge>
              ) : (
                <Badge tone="muted">0 Off-Days</Badge>
              )}
            </div>
          </div>
        </div>

        {/* Date Picker Component */}
        <AestheticDatePicker
          selectedDate={selectedDate}
          onDateChange={(newDate) => setSelectedDate(newDate)}
          unavailableDates={offDatesForPicker}
          label={activeDoctor ? `${activeDoctor.name || "Doctor"}'s Schedule` : "Staff Schedule Date"}
        />

        {/* Doctor Availability List for Selected Date */}
        {loading ? (
          <Skeleton className="h-40" />
        ) : displayedDoctors.length === 0 ? (
          <div className="py-8 text-center text-xs text-muted-foreground">
            No doctors provisioned for this clinic yet.
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Individual Doctor Off-Day Breakdown ({selectedDate})
              </h3>
              {activeDoctor && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs h-7 py-0.5"
                  onClick={() => setSelectedDoctorId("all")}
                >
                  Clear Doctor Filter (Show All)
                </Button>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {displayedDoctors.map((d) => {
                const isOff = (d.unavailable_dates || []).includes(selectedDate);
                const hasOffDays = (d.unavailable_dates || []).length > 0;

                return (
                  <div
                    key={d.profile_id}
                    className={`rounded-2xl border p-4 transition-all space-y-3 ${
                      isOff
                        ? "border-destructive/40 bg-destructive/5 hover:border-destructive/60"
                        : "border-glass-border bg-card/60 hover:border-cyan/50"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-3">
                        <span
                          className={`flex size-10 items-center justify-center rounded-xl ${
                            isOff
                              ? "bg-destructive/20 text-destructive"
                              : "bg-cyan/15 text-cyan"
                          }`}
                        >
                          {isOff ? (
                            <CalendarOff className="size-5" />
                          ) : (
                            <Stethoscope className="size-5" />
                          )}
                        </span>
                        <div>
                          <h4 className="font-bold text-sm text-foreground">{d.name || "Doctor"}</h4>
                          <span className="text-xs text-cyan font-medium">{d.specialization}</span>
                        </div>
                      </div>

                      {isOff ? (
                        <Badge tone="danger">OFF-DAY ({selectedDate})</Badge>
                      ) : d.is_active ? (
                        <Badge tone="success">Available</Badge>
                      ) : (
                        <Badge tone="muted">Deactivated</Badge>
                      )}
                    </div>

                    {/* Individual Off-Days List per Doctor */}
                    <div className="rounded-xl border border-glass-border/40 bg-secondary/20 p-2.5 text-xs space-y-1.5">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="font-semibold text-foreground">Doctor's Individual Off-Days:</span>
                        <span className="text-muted-foreground font-mono">
                          {(d.unavailable_dates || []).length} Total
                        </span>
                      </div>
                      {hasOffDays ? (
                        <div className="flex flex-wrap gap-1 pt-0.5">
                          {(d.unavailable_dates || []).map((dt) => (
                            <span
                              key={dt}
                              className={`px-2 py-0.5 rounded-md text-[10px] font-medium border ${
                                dt === selectedDate
                                  ? "bg-destructive text-destructive-foreground border-destructive font-bold"
                                  : "bg-destructive/15 text-destructive border-destructive/30"
                              }`}
                            >
                              Off: {dt}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <p className="text-[11px] text-muted-foreground italic">
                          No off-days marked by this doctor.
                        </p>
                      )}
                    </div>

                    <div className="pt-1 text-xs text-muted-foreground space-y-1">
                      <p>
                        <span className="font-medium text-foreground">Fee:</span> {d.consultation_fee}
                      </p>
                      {isOff ? (
                        <p className="text-destructive font-medium bg-destructive/10 p-2 rounded-lg border border-destructive/20 mt-1">
                          ⚠️ Marked unavailable on {selectedDate} in physician portal. Patient booking is disabled.
                        </p>
                      ) : (
                        <p className="text-foreground/80">
                          🟢 Open for consultation bookings on {selectedDate}.
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </GlassCard>

      {/* Quick Action Navigation */}
      <GlassCard className="space-y-4">
        <h2 className="text-lg font-semibold text-foreground">Clinic Administration</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Link to="/hospital-owner/doctors" className="block">
            <div className="p-4 rounded-2xl border border-glass-border bg-secondary/20 hover:border-cyan/50 hover:bg-secondary/40 transition-all cursor-pointer">
              <div className="flex items-center gap-3">
                <span className="flex size-10 items-center justify-center rounded-xl bg-cyan/15 text-cyan">
                  <Users className="size-5" />
                </span>
                <div>
                  <h3 className="font-medium text-foreground">Doctor Management</h3>
                  <p className="text-xs text-muted-foreground">
                    Add new doctors, set consultation fees, and toggle active status.
                  </p>
                </div>
              </div>
            </div>
          </Link>

          <div className="p-4 rounded-2xl border border-glass-border bg-secondary/20 opacity-70">
            <div className="flex items-center gap-3">
              <span className="flex size-10 items-center justify-center rounded-xl bg-indigo/15 text-indigo">
                <Building2 className="size-5" />
              </span>
              <div>
                <h3 className="font-medium text-foreground">Hospital Profile</h3>
                <p className="text-xs text-muted-foreground">Managed by Platform Super Admin.</p>
              </div>
            </div>
          </div>
        </div>
      </GlassCard>
    </div>
  );
}
