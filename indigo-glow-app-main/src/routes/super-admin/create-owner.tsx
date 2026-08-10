import { useEffect, useState } from "react";
import { useNavigate, createFileRoute } from "@tanstack/react-router";
import { UserPlus, ShieldCheck, Building2 } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useToast } from "@/components/Toaster";
import { Button, Field, GlassCard } from "@/components/ui-kit";
import { api, type Hospital } from "@/lib/api";

export const Route = createFileRoute("/super-admin/create-owner")({
  component: SuperAdminCreateOwner,
});

function SuperAdminCreateOwner() {
  return (
    <RoleGuard role="super_admin">
      <AppShell>
        <CreateOwnerContent />
      </AppShell>
    </RoleGuard>
  );
}

function CreateOwnerContent() {
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [selectedHospitalId, setSelectedHospitalId] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    async function load() {
      try {
        const list = await api.listHospitals();
        setHospitals(list);
        const first = list[0];
        if (first) {
          setSelectedHospitalId(first.hospital_id);
        }
      } catch (err) {
        console.error(err);
      }
    }
    load();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedHospitalId || !name || !email || !password) {
      toast.error("Please complete all fields");
      return;
    }
    setBusy(true);
    try {
      await api.createHospitalOwner(selectedHospitalId, { name, email, password });
      toast.success("Hospital owner account created successfully!");
      navigate({ to: "/super-admin/hospitals" });
    } catch (err: any) {
      toast.error(err.message || "Failed to create hospital owner");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-6 animate-fade-in py-4">
      <div>
        <span className="text-xs font-semibold uppercase tracking-wider text-cyan">
          Provisioning
        </span>
        <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <UserPlus className="size-7 text-cyan" /> Provision Hospital Owner
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Create an administrative account for a hospital. The owner can provision doctors and
          manage their clinic schedule.
        </p>
      </div>

      <GlassCard className="space-y-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium tracking-wide text-muted-foreground uppercase">
              Select Hospital Tenant
            </label>
            <select
              className="w-full rounded-xl border border-input bg-secondary/40 px-4 py-2.5 text-sm text-foreground focus:border-cyan/60 focus:outline-none"
              value={selectedHospitalId}
              onChange={(e) => setSelectedHospitalId(e.target.value)}
            >
              {hospitals.length === 0 ? (
                <option value="">No hospitals registered</option>
              ) : (
                hospitals.map((h) => (
                  <option key={h.hospital_id} value={h.hospital_id}>
                    {h.name} ({h.city}) {h.owner_id ? "— Owner Exists" : "— No Owner"}
                  </option>
                ))
              )}
            </select>
          </div>

          <Field
            label="Owner Full Name"
            placeholder="e.g. Dr. Rajesh Verma"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />

          <Field
            label="Owner Login Email"
            type="email"
            placeholder="e.g. owner@citycarepune.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <Field
            label="Initial Password"
            type="password"
            placeholder="Minimum 8 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          <div className="pt-2 flex justify-end gap-3">
            <Button
              type="button"
              variant="ghost"
              onClick={() => navigate({ to: "/super-admin/hospitals" })}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={busy || hospitals.length === 0}>
              {busy ? "Creating Account..." : "Create Owner Account"}
            </Button>
          </div>
        </form>
      </GlassCard>
    </div>
  );
}
