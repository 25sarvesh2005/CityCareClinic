import { useState } from "react";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import {
  Stethoscope,
  LogOut,
  Building2,
  UserPlus,
  Users,
  LayoutDashboard,
  Calendar,
  Home,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Activity,
  Menu,
  X,
  LogIn,
  UserCheck,
  Sparkles,
} from "lucide-react";
import type { ReactNode } from "react";
import { clearSession, homeForRole, useSession } from "@/lib/auth";
import { Button } from "./ui-kit";
import { useToast } from "./Toaster";

export function AppShell({
  children,
  onOpenAuth,
}: {
  children: ReactNode;
  onOpenAuth?: (mode: "login" | "signup") => void;
}) {
  const { user } = useSession();
  const logoDestination = user ? homeForRole(user.role) : "/";
  const navigate = useNavigate();
  const toast = useToast();
  const routerState = useRouterState();
  const currentPath = routerState.location.pathname;

  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const roleLabel = (role: string) => {
    switch (role) {
      case "super_admin":
        return "Super Admin";
      case "hospital_owner":
        return "Hospital Owner";
      case "doctor":
        return "Doctor";
      case "patient":
        return "Patient";
      default:
        return "Guest";
    }
  };

  const navItems = () => {
    if (!user) {
      return [{ label: "Home Overview", to: "/", icon: Home }];
    }

    switch (user.role) {
      case "super_admin":
        return [
          { label: "Platform Dashboard", to: "/super-admin/dashboard", icon: LayoutDashboard },
          { label: "Hospitals", to: "/super-admin/hospitals", icon: Building2 },
          { label: "Add Owner", to: "/super-admin/create-owner", icon: UserPlus },
        ];
      case "hospital_owner":
        return [
          { label: "Hospital Dashboard", to: "/hospital-owner/dashboard", icon: LayoutDashboard },
          { label: "Doctors Staff", to: "/hospital-owner/doctors", icon: Users },
          { label: "Schedule AI Workspace", to: "/schedule-ai", icon: Sparkles },
        ];
      case "doctor":
        return [
          { label: "Consultation Timeline", to: "/doctor", icon: Activity },
          { label: "Schedule AI Workspace", to: "/schedule-ai", icon: Sparkles },
        ];
      case "patient":
      default:
        return [
          { label: "Home Overview", to: "/", icon: Home },
          { label: "Browse Hospitals", to: "/hospitals", icon: Building2 },
          { label: "My Appointments", to: "/dashboard", icon: Calendar },
          { label: "Prescription AI Workspace", to: "/prescription-ai", icon: Sparkles },
        ];
    }
  };

  const activeNavs = navItems();

  return (
    <div className="mesh flex min-h-screen flex-col gap-3 bg-background p-0 text-foreground sm:p-3 md:flex-row">
      {/* Mobile Top Bar */}
      <div className="md:hidden sticky top-0 z-50 flex items-center justify-between border-b border-glass-border bg-card/90 px-4 py-3 backdrop-blur-xl">
        <Link to={logoDestination} className="flex items-center gap-2.5">
          <span className="flex size-8 items-center justify-center rounded-lg bg-indigo text-primary-foreground shadow-sm">
            <Stethoscope className="size-4" />
          </span>
          <span className="font-bold text-sm text-foreground">CityCare</span>
        </Link>
        <button
          type="button"
          onClick={() => setMobileOpen(!mobileOpen)}
          className="rounded-lg p-2 text-muted-foreground hover:bg-secondary/60 hover:text-foreground"
        >
          {mobileOpen ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
      </div>

      {/* Role-Based Interactive Left Sidebar */}
      <aside
        className={`glass z-40 flex flex-col justify-between rounded-none border border-glass-border bg-sidebar/95 shadow-sm transition-all duration-300 md:sticky md:top-3 md:h-[calc(100vh-1.5rem)] md:self-start md:rounded-2xl ${
          mobileOpen ? "fixed inset-x-3 top-16 bottom-3 z-50 flex" : "hidden md:flex"
        } ${collapsed ? "md:w-20" : "md:w-60"}`}
      >
        {/* Top Branding & Collapse Toggle */}
        <div
          className={`max-h-full space-y-5 overflow-y-auto p-4 ${collapsed ? "flex flex-col items-center px-2 py-4" : ""}`}
        >
          <div
            className={`flex items-center w-full ${collapsed ? "flex-col gap-3 justify-center" : "justify-between"}`}
          >
            <Link to={logoDestination} className="flex items-center gap-3 shrink-0">
              <span className="flex size-10 shrink-0 items-center justify-center rounded-xl border border-indigo/15 bg-indigo/10 text-indigo transition-colors hover:bg-indigo/15">
                <Stethoscope className="size-5" />
              </span>
              {!collapsed && (
                <div className="flex flex-col min-w-0">
                  <span className="text-sm font-bold tracking-tight text-foreground truncate flex items-center gap-1.5">
                    CityCare
                    <span className="size-1.5 rounded-full bg-success shrink-0" />
                  </span>
                  <span className="text-[10px] font-medium tracking-wider text-muted-foreground uppercase truncate">
                    Care Operations
                  </span>
                </div>
              )}
            </Link>

            <button
              type="button"
              onClick={() => setCollapsed(!collapsed)}
              className="hidden md:flex size-7 shrink-0 items-center justify-center rounded-lg border border-glass-border bg-secondary/40 text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {collapsed ? <ChevronRight className="size-4" /> : <ChevronLeft className="size-4" />}
            </button>
          </div>

          {/* Role Context Chip */}
          {!collapsed && (
            <div className="flex items-center justify-between rounded-xl border border-glass-border/70 bg-accent/45 px-3 py-2 text-xs">
              <span className="text-muted-foreground">Context:</span>
              <span className="font-semibold text-indigo flex items-center gap-1">
                <ShieldCheck className="size-3.5" />
                {roleLabel(user?.role || "guest")}
              </span>
            </div>
          )}

          {/* Nav Items List */}
          <nav className="w-full space-y-1.5">
            {!collapsed && (
              <p className="px-3 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                Navigation
              </p>
            )}
            {activeNavs.map((item) => {
              const Icon = item.icon;
              const isActive =
                item.to === "/"
                  ? currentPath === "/"
                  : currentPath === item.to || currentPath.startsWith(item.to + "/");

              return (
                <Link
                  key={item.to}
                  to={item.to}
                  onClick={() => setMobileOpen(false)}
                  title={collapsed ? item.label : undefined}
                  className={`group flex items-center gap-3 rounded-xl px-3 py-2.5 text-xs font-medium transition-all ${
                    collapsed ? "justify-center px-0 py-2.5" : ""
                  } ${
                    isActive
                      ? "border border-indigo/20 bg-indigo/10 text-indigo font-semibold"
                      : "text-muted-foreground hover:text-foreground hover:bg-secondary/40 border border-transparent"
                  }`}
                >
                  <Icon
                    className={`size-4 shrink-0 transition-transform group-hover:scale-110 ${
                      isActive ? "text-indigo" : "text-muted-foreground"
                    }`}
                  />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Sidebar Footer — User Profile / Context */}
        <div
          className={`p-4 border-t border-glass-border shrink-0 ${collapsed ? "flex flex-col items-center px-2 py-4" : ""}`}
        >
          {user ? (
            <div className="w-full space-y-3">
              {!collapsed && (
                <div className="flex items-center gap-2.5 px-1">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-xl bg-indigo text-xs font-bold text-primary-foreground">
                    {user.name ? user.name.charAt(0).toUpperCase() : "U"}
                  </div>
                  <div className="flex flex-col min-w-0">
                    <span className="text-xs font-semibold text-foreground truncate">
                      {user.name}
                    </span>
                    <span className="text-[10px] text-muted-foreground truncate">{user.email}</span>
                  </div>
                </div>
              )}
              <Button
                variant="ghost"
                size="sm"
                className={`w-full text-xs text-destructive hover:bg-destructive/10 ${
                  collapsed ? "justify-center px-0" : "justify-start"
                }`}
                onClick={() => {
                  clearSession();
                  toast.info("Signed out");
                  navigate({ to: "/", replace: true });
                }}
                title={collapsed ? "Sign Out" : undefined}
              >
                <LogOut className="size-4 shrink-0" />
                {!collapsed && <span>Sign Out</span>}
              </Button>
            </div>
          ) : (
            <div className="w-full text-center text-[11px] text-muted-foreground">
              {!collapsed ? (
                <p className="px-1">Welcome to CityCare Platform</p>
              ) : (
                <span className="inline-block size-2 rounded-full bg-success" />
              )}
            </div>
          )}
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="glass flex min-w-0 flex-1 flex-col justify-between overflow-hidden rounded-none border border-glass-border bg-card/95 shadow-sm md:rounded-2xl">
        {/* Top Header Bar for Quick Auth / Session Status */}
        <header className="flex items-center justify-between border-b border-glass-border bg-card/85 px-6 py-3.5 backdrop-blur-md">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Link
              to={logoDestination}
              className="font-semibold text-foreground hover:text-cyan transition-colors"
            >
              CityCare
            </Link>{" "}
            /
            <span className="text-cyan font-medium capitalize">
              {currentPath === "/" ? "Home" : currentPath.replace("/", "").replace("-", " ")}
            </span>
          </div>

          {!user && (
            <div className="flex items-center gap-2">
              <Link to="/login">
                <Button variant="outline" size="sm" className="text-xs py-1 px-3 h-8">
                  <LogIn className="size-3.5 mr-1" /> Sign In
                </Button>
              </Link>
              <Link to="/signup">
                <Button variant="primary" size="sm" className="text-xs py-1 px-3 h-8">
                  <UserCheck className="size-3.5 mr-1" /> Register
                </Button>
              </Link>
            </div>
          )}
        </header>

        <main className="mx-auto w-full max-w-7xl px-4 py-6 md:px-8 md:py-8">{children}</main>

        <footer className="border-t border-glass-border py-4 px-6 text-xs text-muted-foreground flex flex-wrap items-center justify-between gap-2">
          <p>© {new Date().getFullYear()} CityCare Multi-Tenant Healthcare Platform</p>
          <span className="text-[11px] text-cyan font-medium">Multi-Tenant Platform</span>
        </footer>
      </div>
    </div>
  );
}
