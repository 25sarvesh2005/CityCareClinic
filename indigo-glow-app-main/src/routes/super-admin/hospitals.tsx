import { useEffect, useState } from "react";
import { Link, createFileRoute } from "@tanstack/react-router";
import { Building2, Plus, CheckCircle, AlertTriangle, UserPlus, Search } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useToast } from "@/components/Toaster";
import { Badge, Button, Field, GlassCard, Skeleton } from "@/components/ui-kit";
import { api, type Hospital } from "@/lib/api";

export const Route = createFileRoute("/super-admin/hospitals")({
  component: SuperAdminHospitals,
});

function SuperAdminHospitals() {
  return (
    <RoleGuard role="super_admin">
      <AppShell>
        <HospitalsContent />
      </AppShell>
    </RoleGuard>
  );
}

function HospitalsContent() {
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const [form, setForm] = useState({
    name: "",
    address: "",
    city: "",
    contact_number: "",
  });

  async function loadHospitals() {
    try {
      const data = await api.listHospitals();
      setHospitals(data);
    } catch (err: any) {
      toast.error(err.message || "Failed to load hospitals");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadHospitals();
  }, []);

  async function handleCreateHospital(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name || !form.address || !form.city || !form.contact_number) {
      toast.error("Please fill all required fields");
      return;
    }
    setBusy(true);
    try {
      await api.createHospital(form);
      toast.success("Hospital created successfully!");
      setForm({ name: "", address: "", city: "", contact_number: "" });
      setShowAddForm(false);
      await loadHospitals();
    } catch (err: any) {
      toast.error(err.message || "Failed to create hospital");
    } finally {
      setBusy(false);
    }
  }

  async function handleToggleStatus(
    hospital_id: string,
    is_active?: boolean,
    is_approved?: boolean,
  ) {
    try {
      const payload: { is_active?: boolean; is_approved?: boolean } = {};
      if (is_active !== undefined) payload.is_active = is_active;
      if (is_approved !== undefined) payload.is_approved = is_approved;
      await api.setHospitalStatus(hospital_id, payload);
      toast.success("Hospital status updated");
      await loadHospitals();
    } catch (err: any) {
      toast.error(err.message || "Failed to update hospital status");
    }
  }

  const filteredHospitals = hospitals.filter(
    (h) =>
      h.name.toLowerCase().includes(search.toLowerCase()) ||
      h.city.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-glass-border pb-6">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-cyan">
            Tenant Management
          </span>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Hospitals & Clinics</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Register new hospital tenants, manage activation status, and approve platform access.
          </p>
        </div>
        <Button variant="primary" size="sm" onClick={() => setShowAddForm(!showAddForm)}>
          <Plus className="size-4" /> {showAddForm ? "Cancel" : "Register Hospital"}
        </Button>
      </div>

      {/* Add Hospital Form */}
      {showAddForm && (
        <GlassCard className="animate-rise space-y-4">
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Building2 className="size-5 text-cyan" /> Register New Hospital Tenant
          </h2>
          <form onSubmit={handleCreateHospital} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field
              label="Hospital Name"
              placeholder="e.g. CityCare Specialty Hospital"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <Field
              label="City"
              placeholder="e.g. Pune"
              value={form.city}
              onChange={(e) => setForm({ ...form, city: e.target.value })}
            />
            <Field
              label="Street Address"
              placeholder="e.g. 12 MG Road, Shivajinagar"
              value={form.address}
              onChange={(e) => setForm({ ...form, address: e.target.value })}
            />
            <Field
              label="Contact Number"
              placeholder="e.g. +91-20-1234-5678"
              value={form.contact_number}
              onChange={(e) => setForm({ ...form, contact_number: e.target.value })}
            />
            <div className="md:col-span-2 flex justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" size="sm" onClick={() => setShowAddForm(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" size="sm" disabled={busy}>
                {busy ? "Saving..." : "Save & Register"}
              </Button>
            </div>
          </form>
        </GlassCard>
      )}

      {/* Search Bar */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-3 size-4 text-muted-foreground" />
          <input
            className="w-full rounded-full border border-input bg-secondary/40 pl-10 pr-4 py-2 text-sm text-foreground focus:border-cyan/60 focus:outline-none"
            placeholder="Search hospitals by name or city..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Table */}
      <GlassCard className="space-y-4">
        {loading ? (
          <Skeleton className="h-64" />
        ) : filteredHospitals.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground text-sm">
            {search ? "No hospitals match your search." : "No hospitals registered yet."}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-glass-border text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="py-3 px-4">Hospital Details</th>
                  <th className="py-3 px-4">City</th>
                  <th className="py-3 px-4">Owner Bound</th>
                  <th className="py-3 px-4">Active</th>
                  <th className="py-3 px-4">Approval</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-glass-border">
                {filteredHospitals.map((h) => (
                  <tr key={h.hospital_id} className="hover:bg-secondary/20 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-foreground">{h.name}</div>
                      <div className="text-xs text-muted-foreground">{h.address}</div>
                    </td>
                    <td className="py-3 px-4 text-muted-foreground">{h.city}</td>
                    <td className="py-3 px-4">
                      {h.owner_id ? (
                        <Badge tone="cyan">Owner Assigned</Badge>
                      ) : (
                        <Link to="/super-admin/create-owner">
                          <Badge tone="indigo">
                            <UserPlus className="size-3 mr-1 inline" /> Assign Owner
                          </Badge>
                        </Link>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      {h.is_active ? (
                        <Badge tone="success">Active</Badge>
                      ) : (
                        <Badge tone="danger">Suspended</Badge>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      {h.is_approved ? (
                        <Badge tone="cyan">Approved</Badge>
                      ) : (
                        <Badge tone="muted">Pending</Badge>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant={h.is_approved ? "outline" : "primary"}
                          size="sm"
                          onClick={() =>
                            handleToggleStatus(h.hospital_id, undefined, !h.is_approved)
                          }
                        >
                          {h.is_approved ? "Revoke Approval" : "Approve"}
                        </Button>
                        <Button
                          variant={h.is_active ? "danger" : "outline"}
                          size="sm"
                          onClick={() => handleToggleStatus(h.hospital_id, !h.is_active, undefined)}
                        >
                          {h.is_active ? "Suspend" : "Reactivate"}
                        </Button>
                      </div>
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
