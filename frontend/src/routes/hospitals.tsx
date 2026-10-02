import { useCallback, useEffect, useState } from "react";
import { Link, useSearch, createFileRoute } from "@tanstack/react-router";
import { Building2, MapPin, Phone, Search, Stethoscope, ChevronRight } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useToast } from "@/components/Toaster";
import { Badge, Button, GlassCard, Skeleton } from "@/components/ui-kit";
import { api, type Hospital } from "@/lib/api";

export const Route = createFileRoute("/hospitals")({
  validateSearch: (search: Record<string, unknown>): { city?: string } => {
    const city = search["city"] as string | undefined;
    return city ? { city } : {};
  },
  component: () => (
    <RoleGuard role="patient">
      <PatientHospitalsPage />
    </RoleGuard>
  ),
});

function PatientHospitalsPage() {
  const search = useSearch({ from: "/hospitals" });
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState(search.city || "");
  const toast = useToast();

  const loadHospitals = useCallback(async () => {
    setLoading(true);
    try {
      const list = await api.browseHospitals();
      setHospitals(list);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to load hospitals");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    loadHospitals();
  }, [loadHospitals]);

  const filteredHospitals = hospitals.filter((h) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase().trim();
    return (
      h.name.toLowerCase().includes(q) ||
      h.city.toLowerCase().includes(q) ||
      h.address.toLowerCase().includes(q)
    );
  });

  return (
    <AppShell>
      <div className="space-y-8 animate-fade-in">
        {/* Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-glass-border pb-6">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-cyan">
              Healthcare Discovery
            </span>
            <h1 className="text-3xl font-bold tracking-tight text-foreground">
              Find Hospitals & Clinics
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Browse verified multi-tenant clinics in your area and select a specialist for
              consultation.
            </p>
          </div>
          <div className="relative w-full sm:w-80">
            <Search className="absolute left-3.5 top-3 size-4 text-cyan" />
            <input
              type="text"
              className="w-full rounded-2xl border border-input bg-secondary/40 pl-10 pr-4 py-2 text-xs text-foreground placeholder:text-muted-foreground/70 focus:border-cyan/60 focus:outline-none focus:ring-2 focus:ring-cyan/30"
              placeholder="Search by hospital name or city (e.g. CityCare, Pune)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        {/* Hospital Card Grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Skeleton className="h-44" />
            <Skeleton className="h-44" />
          </div>
        ) : filteredHospitals.length === 0 ? (
          <GlassCard className="text-center py-12">
            <Building2 className="mx-auto size-12 text-muted-foreground/50 mb-3" />
            <h3 className="text-lg font-semibold text-foreground">No Hospitals Found</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {searchQuery
                ? `No active clinics found matching "${searchQuery}".`
                : "No active hospitals available."}
            </p>
          </GlassCard>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {filteredHospitals.map((h) => (
              <GlassCard
                key={h.hospital_id}
                className="hover:border-cyan/50 transition-all flex flex-col justify-between space-y-4"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-3">
                      <span className="flex size-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo/20 to-cyan/20 text-cyan">
                        <Building2 className="size-5" />
                      </span>
                      <div>
                        <h3 className="font-bold text-lg text-foreground">{h.name}</h3>
                        <span className="flex items-center gap-1 text-xs text-cyan font-medium">
                          <MapPin className="size-3" /> {h.city}
                        </span>
                      </div>
                    </div>
                    <Badge tone="cyan">Verified</Badge>
                  </div>

                  <p className="mt-3 text-xs text-muted-foreground line-clamp-2">{h.address}</p>
                  <div className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Phone className="size-3 text-indigo" /> {h.contact_number}
                  </div>
                </div>

                <div className="pt-2 border-t border-glass-border flex justify-end">
                  <Link
                    to="/hospital-doctors"
                    search={{ hospital_id: h.hospital_id, hospital_name: h.name }}
                  >
                    <Button variant="primary" size="sm">
                      View Doctors & Book <ChevronRight className="size-4 ml-1" />
                    </Button>
                  </Link>
                </div>
              </GlassCard>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
