import { useEffect, useState } from "react";
import { Link, useNavigate, useSearch, createFileRoute } from "@tanstack/react-router";
import {
  Stethoscope,
  Calendar,
  Clock,
  ArrowLeft,
  CheckCircle,
  HeartPulse,
  AlertTriangle,
} from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { useToast } from "@/components/Toaster";
import { AestheticDatePicker } from "@/components/AestheticDatePicker";
import { RoleGuard } from "@/components/RoleGuard";
import { Badge, Button, Field, GlassCard, Skeleton } from "@/components/ui-kit";
import { api, SYMPTOMS, SYMPTOM_LABELS, type DoctorProfile, type Symptom } from "@/lib/api";
import { useSession } from "@/lib/auth";
import {
  TEMPERATURE_LIMITS,
  convertTemperatureInput,
  isTemperatureInRange,
  toFahrenheit,
  type TemperatureUnit,
} from "@/lib/temperature";

export const Route = createFileRoute("/hospital-doctors")({
  validateSearch: (search: Record<string, unknown>) => ({
    hospital_id: (search["hospital_id"] as string) || "",
    hospital_name: (search["hospital_name"] as string) || "Hospital",
  }),
  component: () => (
    <RoleGuard role="patient">
      <HospitalDoctorsPage />
    </RoleGuard>
  ),
});

function getLocalTodayIso(): string {
  const now = new Date();
  const localTime = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return localTime.toISOString().slice(0, 10);
}

function HospitalDoctorsPage() {
  const { hospital_id, hospital_name } = useSearch({ from: "/hospital-doctors" });
  const { user } = useSession();
  const navigate = useNavigate();
  const toast = useToast();

  const [activeHospitalId, setActiveHospitalId] = useState<string>(hospital_id);
  const [activeHospitalName, setActiveHospitalName] = useState<string>(hospital_name);

  const [doctors, setDoctors] = useState<DoctorProfile[]>([]);
  const [loadingDoctors, setLoadingDoctors] = useState(true);
  const [selectedDoctor, setSelectedDoctor] = useState<DoctorProfile | null>(null);

  // Booking Form State — default to today's ISO date string (YYYY-MM-DD)
  const [selectedDate, setSelectedDate] = useState<string>(getLocalTodayIso);
  const [freeSlots, setFreeSlots] = useState<string[]>([]);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState<string>("");
  const [reason, setReason] = useState("");
  const [temperature, setTemperature] = useState<string>("98.6");
  const [temperatureUnit, setTemperatureUnit] = useState<TemperatureUnit>("F");
  const [selectedSymptoms, setSelectedSymptoms] = useState<Symptom[]>(["fever"]);
  const [bookingBusy, setBookingBusy] = useState(false);

  useEffect(() => {
    async function loadDoctors() {
      setLoadingDoctors(true);
      try {
        let currentId = hospital_id;
        let currentName = hospital_name;
        if (!currentId) {
          const availableHospitals = await api.browseHospitals();
          const firstHosp = availableHospitals[0];
          if (firstHosp) {
            currentId = firstHosp.hospital_id;
            currentName = firstHosp.name;
          }
        }
        setActiveHospitalId(currentId);
        setActiveHospitalName(currentName);

        if (currentId) {
          const data = await api.getHospitalDoctors(currentId);
          setDoctors(data);
          const firstDoc = data[0];
          if (firstDoc) {
            setSelectedDoctor(firstDoc);
          } else {
            setSelectedDoctor(null);
          }
        } else {
          setDoctors([]);
          setSelectedDoctor(null);
        }
      } catch (err: unknown) {
        toast.error(err instanceof Error ? err.message : "Failed to load doctor profiles");
      } finally {
        setLoadingDoctors(false);
      }
    }
    loadDoctors();
  }, [hospital_id, hospital_name, toast]);

  useEffect(() => {
    async function fetchSlots() {
      if (!activeHospitalId || !selectedDoctor || !selectedDate) {
        setFreeSlots([]);
        return;
      }
      setLoadingSlots(true);
      try {
        const res = await api.getDoctorFreeSlots(
          activeHospitalId,
          selectedDoctor.profile_id,
          selectedDate,
        );
        setFreeSlots(res.available_slots);
        const firstSlot = res.available_slots[0];
        if (firstSlot) {
          setSelectedSlot(firstSlot);
        } else {
          setSelectedSlot("");
        }
      } catch (err: unknown) {
        toast.error(err instanceof Error ? err.message : "Failed to fetch free slots");
        setFreeSlots([]);
      } finally {
        setLoadingSlots(false);
      }
    }
    fetchSlots();
  }, [activeHospitalId, selectedDoctor, selectedDate, toast]);

  function toggleSymptom(s: Symptom) {
    if (selectedSymptoms.includes(s)) {
      if (selectedSymptoms.length > 1) {
        setSelectedSymptoms(selectedSymptoms.filter((item) => item !== s));
      }
    } else {
      setSelectedSymptoms([...selectedSymptoms, s]);
    }
  }

  function changeTemperatureUnit(nextUnit: TemperatureUnit) {
    if (nextUnit === temperatureUnit) return;
    setTemperature((current) => convertTemperatureInput(current, temperatureUnit, nextUnit));
    setTemperatureUnit(nextUnit);
  }

  async function handleBook(e: React.FormEvent) {
    e.preventDefault();
    if (!user) {
      toast.info("Please sign in to book an appointment");
      navigate({ to: "/login" });
      return;
    }
    if (!selectedDoctor || !selectedDate || !selectedSlot) {
      toast.error("Please select a date and slot");
      return;
    }
    if (!activeHospitalId) {
      toast.error("Invalid hospital context. Please select a hospital from the list.");
      return;
    }
    if (reason.trim().length < 10) {
      toast.error("Reason must be at least 10 characters long");
      return;
    }
    const tempNum = parseFloat(temperature);
    const limits = TEMPERATURE_LIMITS[temperatureUnit];
    if (!isTemperatureInRange(tempNum, temperatureUnit)) {
      toast.error(
        `Temperature must be between ${limits.min.toFixed(1)}°${temperatureUnit} and ${limits.max.toFixed(1)}°${temperatureUnit}`,
      );
      return;
    }
    const temperatureFahrenheit = toFahrenheit(tempNum, temperatureUnit);

    setBookingBusy(true);
    try {
      await api.bookAppointment({
        hospital_id: activeHospitalId,
        doctor_id: selectedDoctor.profile_id,
        date: selectedDate,
        slot: selectedSlot,
        reason,
        // The API and existing records use Fahrenheit. Celsius is converted at the UI boundary.
        temperature: temperatureFahrenheit,
        symptoms: selectedSymptoms,
      });
      toast.success("Appointment booked successfully!");
      navigate({ to: "/dashboard" });
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to book appointment");
    } finally {
      setBookingBusy(false);
    }
  }

  return (
    <AppShell>
      <div className="space-y-8 animate-fade-in">
        {/* Back Link */}
        <Link
          to="/hospitals"
          className="inline-flex items-center text-xs font-medium text-cyan hover:underline"
        >
          <ArrowLeft className="size-3.5 mr-1" /> Back to Hospital List
        </Link>

        {/* Header Banner */}
        <div className="border-b border-glass-border pb-6">
          <span className="text-xs font-semibold uppercase tracking-wider text-cyan">
            Clinic Doctor Selection
          </span>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">
            {activeHospitalName}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Select a medical specialist and reserve an available appointment slot.
          </p>
        </div>

        {/* Doctor List Selection */}
        {loadingDoctors ? (
          <Skeleton className="h-40" />
        ) : doctors.length === 0 ? (
          <GlassCard className="text-center py-12">
            <Stethoscope className="mx-auto size-12 text-muted-foreground/50 mb-3" />
            <h3 className="text-lg font-semibold text-foreground">No Active Doctors</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              This hospital currently has no active doctor profiles.
            </p>
          </GlassCard>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Doctor Picker Column */}
            <div className="space-y-4">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                Select Specialist
              </h2>
              {doctors.map((d) => (
                <div
                  key={d.profile_id}
                  onClick={() => setSelectedDoctor(d)}
                  className={`p-4 rounded-2xl border transition-all cursor-pointer ${
                    selectedDoctor?.profile_id === d.profile_id
                      ? "border-cyan bg-cyan/10 shadow-lg shadow-cyan/10"
                      : "border-glass-border bg-card hover:border-cyan/40"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-semibold text-foreground text-sm">
                        {d.name || "Doctor"}
                      </div>
                      <div className="text-xs text-cyan font-medium">{d.specialization}</div>
                    </div>
                    <Badge tone="cyan">{d.consultation_fee}</Badge>
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    Hours: {d.clinic_hours?.["morning"] || "Morning"} ·{" "}
                    {d.clinic_hours?.["evening"] || "Evening"}
                  </div>
                  {d.languages_spoken?.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {d.languages_spoken.map((lang) => (
                        <span
                          key={lang}
                          className="text-[10px] bg-secondary/50 text-muted-foreground px-2 py-0.5 rounded-full"
                        >
                          {lang}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Booking Form Column */}
            {selectedDoctor && (
              <div className="md:col-span-2 space-y-6">
                <GlassCard className="space-y-6">
                  <div>
                    <h2 className="text-lg font-bold text-foreground">Book Consultation</h2>
                    <p className="text-xs text-muted-foreground">
                      Booking with{" "}
                      <span className="text-cyan font-medium">
                        {selectedDoctor.name
                          ? `${selectedDoctor.name} (${selectedDoctor.specialization})`
                          : selectedDoctor.specialization}
                      </span>{" "}
                      at {activeHospitalName}
                    </p>
                  </div>

                  <form onSubmit={handleBook} className="space-y-6">
                    {/* Date Picker */}
                    <div>
                      <AestheticDatePicker
                        selectedDate={selectedDate}
                        onDateChange={(newDate) => {
                          setSelectedDate(newDate);
                          setSelectedSlot("");
                        }}
                        unavailableDates={selectedDoctor?.unavailable_dates || []}
                        label="1. Select Appointment Date"
                      />
                    </div>

                    {/* Slot Picker */}
                    {selectedDate && (
                      <div>
                        <span className="mb-1.5 block text-xs font-medium tracking-wide text-muted-foreground uppercase">
                          2. Select Time Slot
                        </span>
                        {loadingSlots ? (
                          <Skeleton className="h-14" />
                        ) : selectedDoctor?.unavailable_dates?.includes(selectedDate) ? (
                          <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-3.5 text-xs text-destructive space-y-1.5 animate-rise">
                            <p className="font-bold flex items-center gap-1.5 text-sm">
                              <AlertTriangle className="size-4 shrink-0 text-destructive" />
                              Physician Marked Unavailable (Off-Day)
                            </p>
                            <p className="text-muted-foreground">
                              {selectedDoctor?.name || "The doctor"} is marked as unavailable
                              (off-day) on {selectedDate}. All consultation slots for this date are
                              disabled. Please select another date above.
                            </p>
                          </div>
                        ) : freeSlots.length === 0 ? (
                          <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3.5 text-xs text-amber-700 dark:text-amber-300 space-y-1.5 animate-rise">
                            <p className="font-bold flex items-center gap-1.5 text-sm">
                              <AlertTriangle className="size-4 shrink-0" />
                              No Slots Available
                            </p>
                            <p className="text-muted-foreground">
                              There are no remaining consultation slots for {selectedDate}. Please
                              select another date or specialist.
                            </p>
                          </div>
                        ) : (
                          <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                            {freeSlots.map((slot) => (
                              <button
                                key={slot}
                                type="button"
                                onClick={() => setSelectedSlot(slot)}
                                className={`py-2 px-3 rounded-xl text-xs font-medium border transition-all ${
                                  selectedSlot === slot
                                    ? "border-cyan bg-cyan text-cyan-foreground font-bold shadow-md shadow-cyan/20"
                                    : "border-glass-border bg-secondary/30 text-foreground hover:border-cyan/40"
                                }`}
                              >
                                {slot}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Symptoms Picker */}
                    <div>
                      <span className="mb-1.5 block text-xs font-medium tracking-wide text-muted-foreground uppercase">
                        3. Reported Symptoms
                      </span>
                      <div className="flex flex-wrap gap-2">
                        {SYMPTOMS.map((symptom) => {
                          const active = selectedSymptoms.includes(symptom);
                          return (
                            <button
                              key={symptom}
                              type="button"
                              onClick={() => toggleSymptom(symptom)}
                              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
                                active
                                  ? "border-cyan bg-cyan/15 text-cyan font-semibold"
                                  : "border-glass-border bg-secondary/30 text-muted-foreground hover:text-foreground"
                              }`}
                            >
                              {SYMPTOM_LABELS[symptom]}
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* Medical Details */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                      <div className="sm:col-span-2">
                        <Field
                          label="Reason for Visit"
                          placeholder="Describe symptoms or checkup purpose (min 10 chars)..."
                          value={reason}
                          onChange={(e) => setReason(e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <div
                          className="grid grid-cols-2 rounded-xl border border-glass-border bg-secondary/30 p-1"
                          role="group"
                          aria-label="Temperature unit"
                        >
                          {(["F", "C"] as const).map((unit) => (
                            <button
                              key={unit}
                              type="button"
                              onClick={() => changeTemperatureUnit(unit)}
                              aria-pressed={temperatureUnit === unit}
                              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                                temperatureUnit === unit
                                  ? "bg-cyan text-cyan-foreground shadow-sm"
                                  : "text-muted-foreground hover:text-foreground"
                              }`}
                            >
                              °{unit}
                            </button>
                          ))}
                        </div>
                        <Field
                          label={`Temperature (°${temperatureUnit})`}
                          type="number"
                          inputMode="decimal"
                          step="0.1"
                          min={TEMPERATURE_LIMITS[temperatureUnit].min}
                          max={TEMPERATURE_LIMITS[temperatureUnit].max}
                          placeholder={TEMPERATURE_LIMITS[temperatureUnit].defaultValue}
                          value={temperature}
                          onChange={(e) => setTemperature(e.target.value)}
                          hint={
                            temperatureUnit === "C" &&
                            isTemperatureInRange(Number.parseFloat(temperature), temperatureUnit)
                              ? `Equivalent to ${toFahrenheit(Number.parseFloat(temperature), "C").toFixed(1)}°F in the medical record`
                              : "Choose °F or °C; records remain standardized in °F"
                          }
                        />
                      </div>
                    </div>

                    <div className="pt-2 flex justify-end">
                      <Button
                        type="submit"
                        variant="primary"
                        disabled={bookingBusy || !selectedDate || !selectedSlot}
                      >
                        {bookingBusy ? "Confirming Booking..." : "Confirm & Book Appointment"}
                      </Button>
                    </div>
                  </form>
                </GlassCard>
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}
