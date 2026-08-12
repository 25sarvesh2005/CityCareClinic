import { useCallback, useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import {
  Users,
  Plus,
  Stethoscope,
  Mail,
  DollarSign,
  CheckCircle,
  Search,
  CalendarOff,
} from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useToast } from "@/components/Toaster";
import { Badge, Button, Field, GlassCard, Skeleton } from "@/components/ui-kit";
import { api, type DoctorProfile } from "@/lib/api";

export const Route = createFileRoute("/hospital-owner/doctors")({
  component: HospitalOwnerDoctors,
});

function HospitalOwnerDoctors() {
  return (
    <RoleGuard role="hospital_owner">
      <AppShell>
        <DoctorsContent />
      </AppShell>
    </RoleGuard>
  );
}

function DoctorsContent() {
  const [doctors, setDoctors] = useState<DoctorProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const [filterMode, setFilterMode] = useState<"all" | "active" | "off_days">("all");
  const toast = useToast();

  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    specialization: "General Physician",
    consultation_fee: "Rs. 300",
  });

  const loadDoctors = useCallback(async () => {
    try {
      const data = await api.listOwnerDoctors();
      setDoctors(data);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to load doctors");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    loadDoctors();
  }, [loadDoctors]);

  async function handleCreateDoctor(e: React.FormEvent) {
    e.preventDefault();
    if (
      !form.name ||
      !form.email ||
      !form.password ||
      !form.specialization ||
      !form.consultation_fee
    ) {
      toast.error("Please fill all fields");
      return;
    }
    setBusy(true);
    try {
      await api.createDoctor(form);
      toast.success(`Doctor '${form.name}' created successfully!`);
      setForm({
        name: "",
        email: "",
        password: "",
        specialization: "General Physician",
        consultation_fee: "Rs. 300",
      });
      setShowAddForm(false);
      await loadDoctors();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to create doctor account");
    } finally {
      setBusy(false);
    }
  }

  async function handleToggleDoctorStatus(profileId: string, currentActive: boolean) {
    try {
      await api.setDoctorStatus(profileId, { is_active: !currentActive });
      toast.success(`Doctor profile ${!currentActive ? "activated" : "deactivated"} successfully.`);
      await loadDoctors();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to update doctor status.");
    }
  }

  const filteredDoctors = doctors.filter((d) => {
    const matchesSearch =
      !search ||
      d.name?.toLowerCase().includes(search.toLowerCase()) ||
      d.email?.toLowerCase().includes(search.toLowerCase()) ||
      d.specialization.toLowerCase().includes(search.toLowerCase());

    if (!matchesSearch) return false;
    if (filterMode === "active") return d.is_active;
    if (filterMode === "off_days") return (d.unavailable_dates || []).length > 0;
    return true;
  });

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-glass-border pb-6">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-cyan">
            Hospital Administration
          </span>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">
            Doctor Roster & Off-Days
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage provisioned doctors, review individual off-day records, and set active status.
          </p>
        </div>
        <Button variant="primary" size="sm" onClick={() => setShowAddForm(!showAddForm)}>
          <Plus className="size-4" /> {showAddForm ? "Cancel" : "Add New Doctor"}
        </Button>
      </div>

      {/* Provision Form */}
      {showAddForm && (
        <GlassCard className="space-y-4 border-cyan/30 bg-cyan/5 animate-rise">
          <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
            <Stethoscope className="size-5 text-cyan" /> Provision New Doctor Account
          </h2>
          <form onSubmit={handleCreateDoctor} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field
              label="Doctor Full Name"
              placeholder="e.g. Dr. Ananya Sharma"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <Field
              label="Login Email"
              type="email"
              placeholder="e.g. dr.ananya@hospital.com"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
            <Field
              label="Initial Password"
              type="password"
              placeholder="Minimum 8 characters"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
            <Field
              label="Specialization"
              placeholder="e.g. Cardiologist, General Physician"
              value={form.specialization}
              onChange={(e) => setForm({ ...form, specialization: e.target.value })}
            />
            <Field
              label="Consultation Fee"
              placeholder="e.g. Rs. 400"
              value={form.consultation_fee}
              onChange={(e) => setForm({ ...form, consultation_fee: e.target.value })}
            />
            <div className="md:col-span-2 flex justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" size="sm" onClick={() => setShowAddForm(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" size="sm" disabled={busy}>
                {busy ? "Provisioning..." : "Create Doctor Account"}
              </Button>
            </div>
          </form>
        </GlassCard>
      )}

      {/* Doctor Roster & Filters */}
      <GlassCard className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-glass-border pb-4">
          <div className="flex items-center gap-3">
            <Users className="size-5 text-cyan" />
            <h2 className="text-lg font-semibold text-foreground">
              Doctor Roster ({filteredDoctors.length})
            </h2>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Search Box */}
            <div className="relative">
              <Search className="size-3.5 absolute left-3 top-2.5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search name, email, specialty..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="rounded-xl border border-glass-border bg-secondary/40 pl-8 pr-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:border-cyan/50 focus:outline-none w-56"
              />
            </div>

            {/* Filter Mode */}
            <div className="flex items-center gap-1 bg-secondary/30 p-1 rounded-xl border border-glass-border text-xs">
              <button
                type="button"
                className={`px-2.5 py-1 rounded-lg transition-all ${
                  filterMode === "all"
                    ? "bg-cyan text-cyan-foreground font-bold"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                onClick={() => setFilterMode("all")}
              >
                All ({doctors.length})
              </button>
              <button
                type="button"
                className={`px-2.5 py-1 rounded-lg transition-all ${
                  filterMode === "active"
                    ? "bg-cyan text-cyan-foreground font-bold"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                onClick={() => setFilterMode("active")}
              >
                Active
              </button>
              <button
                type="button"
                className={`px-2.5 py-1 rounded-lg transition-all ${
                  filterMode === "off_days"
                    ? "bg-cyan text-cyan-foreground font-bold"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                onClick={() => setFilterMode("off_days")}
              >
                Has Off-Days
              </button>
            </div>
          </div>
        </div>

        {loading ? (
          <Skeleton className="h-64" />
        ) : filteredDoctors.length === 0 ? (
          <div className="text-center py-12 text-sm text-muted-foreground">
            No doctor records match the current filter.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-glass-border text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="py-3 px-4">Doctor Name</th>
                  <th className="py-3 px-4">Email</th>
                  <th className="py-3 px-4">Specialization</th>
                  <th className="py-3 px-4">Fee</th>
                  <th className="py-3 px-4">Individual Off-Days</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-glass-border">
                {filteredDoctors.map((d) => (
                  <tr key={d.profile_id} className="hover:bg-secondary/20 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-foreground">{d.name || "Doctor"}</div>
                      <div className="font-mono text-[10px] text-cyan/70">ID: {d.profile_id}</div>
                    </td>
                    <td className="py-3 px-4 text-muted-foreground text-xs">{d.email || "—"}</td>
                    <td className="py-3 px-4 text-foreground font-medium">{d.specialization}</td>
                    <td className="py-3 px-4 text-muted-foreground">{d.consultation_fee}</td>
                    <td className="py-3 px-4">
                      {d.unavailable_dates && d.unavailable_dates.length > 0 ? (
                        <div className="space-y-1">
                          <div className="flex flex-wrap gap-1">
                            {d.unavailable_dates.map((dt) => (
                              <Badge key={dt} tone="danger">
                                Off: {dt}
                              </Badge>
                            ))}
                          </div>
                          <span className="text-[10px] text-muted-foreground block">
                            {d.unavailable_dates.length} total off-day(s) marked
                          </span>
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground italic">
                          No off-days marked
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      {d.is_active ? (
                        <Badge tone="success">Active</Badge>
                      ) : (
                        <Badge tone="danger">Deactivated</Badge>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Button
                        variant={d.is_active ? "danger" : "outline"}
                        size="sm"
                        onClick={() => handleToggleDoctorStatus(d.profile_id, d.is_active)}
                      >
                        {d.is_active ? "Deactivate" : "Activate"}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </GlassCard>
    </div>
  );
}
