import { useEffect, useState } from "react";
import { Link, createFileRoute } from "@tanstack/react-router";
import { Building2, Users, Calendar, ShieldCheck, UserCheck, Activity, Plus } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { Badge, Button, GlassCard, Skeleton } from "@/components/ui-kit";
import { api, type Hospital, type PlatformStats } from "@/lib/api";

export const Route = createFileRoute("/super-admin/dashboard")({
  component: SuperAdminDashboard,
});

function SuperAdminDashboard() {
  return (
    <RoleGuard role="super_admin">
      <AppShell>
        <DashboardContent />
      </AppShell>
    </RoleGuard>
  );
}

function DashboardContent() {
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [statsData, hospitalsData] = await Promise.all([
          api.getPlatformStats(),
          api.listHospitals(),
        ]);
        setStats(statsData);
        setHospitals(hospitalsData);
      } catch (err) {
        console.error("Failed to load platform data", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-glass-border pb-6">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-cyan">
            Platform Oversight
          </span>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">
            Super Admin Dashboard
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage multi-tenant hospital registrations, tenant approvals, and platform metrics.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link to="/super-admin/hospitals">
            <Button variant="outline" size="sm">
              <Building2 className="size-4" /> Manage Hospitals
            </Button>
          </Link>
          <Link to="/super-admin/create-owner">
            <Button variant="primary" size="sm">
              <Plus className="size-4" /> Provision Owner
            </Button>
          </Link>
        </div>
      </div>

      {/* KPI Grid */}
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
              <span className="text-xs font-medium uppercase tracking-wider">Hospitals</span>
              <Building2 className="size-4 text-cyan" />
            </div>
            <div className="text-2xl font-bold text-foreground">{stats.total_hospitals}</div>
            <div className="flex gap-2">
              <Badge tone="success">{stats.active_hospitals} Active</Badge>
              <Badge tone="cyan">{stats.approved_hospitals} Approved</Badge>
            </div>
          </GlassCard>

          <GlassCard className="space-y-2">
            <div className="flex items-center justify-between text-muted-foreground">
              <span className="text-xs font-medium uppercase tracking-wider">Doctors</span>
              <UserCheck className="size-4 text-indigo" />
            </div>
            <div className="text-2xl font-bold text-foreground">{stats.total_doctors}</div>
            <span className="text-xs text-muted-foreground">Platform Doctors</span>
          </GlassCard>

          <GlassCard className="space-y-2">
            <div className="flex items-center justify-between text-muted-foreground">
              <span className="text-xs font-medium uppercase tracking-wider">Patients</span>
              <Users className="size-4 text-cyan" />
            </div>
            <div className="text-2xl font-bold text-foreground">{stats.total_patients}</div>
            <span className="text-xs text-muted-foreground">Registered Patients</span>
          </GlassCard>

          <GlassCard className="space-y-2">
            <div className="flex items-center justify-between text-muted-foreground">
              <span className="text-xs font-medium uppercase tracking-wider">Appointments</span>
              <Activity className="size-4 text-success" />
            </div>
            <div className="text-2xl font-bold text-foreground">{stats.total_appointments}</div>
            <Badge tone="success">{stats.active_appointments} Active Bookings</Badge>
          </GlassCard>
        </div>
      ) : null}

      {/* Hospital Overview Section */}
      <GlassCard className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-foreground">Registered Hospitals</h2>
            <p className="text-xs text-muted-foreground">
              Overview of all clinic tenants operating on CityCare
            </p>
          </div>
          <Link to="/super-admin/hospitals">
            <Button variant="ghost" size="sm">
              View All ({hospitals.length})
            </Button>
          </Link>
        </div>

        {loading ? (
          <Skeleton className="h-48" />
        ) : hospitals.length === 0 ? (
          <div className="text-center py-8 text-sm text-muted-foreground">
            No hospitals registered yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-glass-border text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="py-3 px-4">Hospital Name</th>
                  <th className="py-3 px-4">City</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Approval</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-glass-border">
                {hospitals.slice(0, 5).map((h) => (
                  <tr key={h.hospital_id} className="hover:bg-secondary/20 transition-colors">
                    <td className="py-3 px-4 font-medium text-foreground">{h.name}</td>
                    <td className="py-3 px-4 text-muted-foreground">{h.city}</td>
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
                        <Badge tone="muted">Pending Approval</Badge>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Link to="/super-admin/hospitals">
                        <Button variant="outline" size="sm">
                          Manage
                        </Button>
                      </Link>
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
