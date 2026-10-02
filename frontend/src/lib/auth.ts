import { useEffect, useState } from "react";
import { clearToken, setToken, type Role } from "./api";
import { STORAGE_KEYS } from "./constants";

const ROLE_KEY = STORAGE_KEYS.ROLE;
const NAME_KEY = STORAGE_KEYS.NAME;
const EMAIL_KEY = STORAGE_KEYS.EMAIL;

export type SessionUser = {
  name: string;
  role: Role;
  email?: string;
};

export function readStoredUser(): SessionUser | null {
  if (typeof window === "undefined") return null;
  const role = window.localStorage.getItem(ROLE_KEY) as Role | null;
  const name = window.localStorage.getItem(NAME_KEY);
  const email = window.localStorage.getItem(EMAIL_KEY);
  if (!role || !name) return null;
  const user: SessionUser = { name, role };
  if (email) user.email = email;
  return user;
}

const listeners = new Set<() => void>();
function emit() {
  listeners.forEach((l) => l());
}

export function saveSession(token: string, name: string, role: Role, email?: string) {
  setToken(token);
  window.localStorage.setItem(ROLE_KEY, role);
  window.localStorage.setItem(NAME_KEY, name);
  if (email) window.localStorage.setItem(EMAIL_KEY, email);
  emit();
}

export function clearSession() {
  clearToken();
  window.localStorage.removeItem(ROLE_KEY);
  window.localStorage.removeItem(NAME_KEY);
  window.localStorage.removeItem(EMAIL_KEY);
  emit();
}

/** Session read after hydration so SSR markup and client markup match. */
export function useSession() {
  const [state, setState] = useState<{ user: SessionUser | null; ready: boolean }>({
    user: null,
    ready: false,
  });

  useEffect(() => {
    const sync = () => setState({ user: readStoredUser(), ready: true });
    sync();
    listeners.add(sync);
    window.addEventListener("storage", sync);
    return () => {
      listeners.delete(sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  return state;
}

export function homeForRole(role: Role) {
  switch (role) {
    case "super_admin":
      return "/super-admin/dashboard";
    case "hospital_owner":
      return "/hospital-owner/dashboard";
    case "doctor":
      return "/doctor";
    case "patient":
    default:
      return "/dashboard";
  }
}
