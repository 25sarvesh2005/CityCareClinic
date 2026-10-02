import { useCallback, useEffect, type ReactNode } from "react";
import { useNavigate } from "@tanstack/react-router";
import type { Role } from "@/lib/api";
import { homeForRole, useSession } from "@/lib/auth";
import { Skeleton } from "./ui-kit";

/** Client-side route guard driven by the role stored in localStorage. */
export function RoleGuard({ role, children }: { role: Role | Role[]; children: ReactNode }) {
  const { user, ready } = useSession();
  const navigate = useNavigate();

  const isAllowed = useCallback(
    (userRole: Role) => {
      return Array.isArray(role) ? role.includes(userRole) : userRole === role;
    },
    [role],
  );

  useEffect(() => {
    if (!ready) return;
    if (!user) {
      navigate({ to: "/login", replace: true });
    } else if (!isAllowed(user.role)) {
      navigate({ to: homeForRole(user.role), replace: true });
    }
  }, [ready, user, isAllowed, navigate]);

  if (!ready || !user || !isAllowed(user.role)) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-10 w-52" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  return <>{children}</>;
}
