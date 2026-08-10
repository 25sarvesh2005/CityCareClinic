import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { CheckCircle2, Info, TriangleAlert, X } from "lucide-react";
import { cn } from "@/lib/utils";

type ToastKind = "success" | "error" | "info";
type Toast = { id: number; kind: ToastKind; title: string; description?: string | undefined };

type ToastApi = {
  toast: (kind: ToastKind, title: string, description?: string) => void;
  success: (title: string, description?: string) => void;
  error: (title: string, description?: string) => void;
  info: (title: string, description?: string) => void;
};

const ToastContext = createContext<ToastApi | null>(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}

let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  const api = useMemo<ToastApi>(() => {
    const toast = (kind: ToastKind, title: string, description?: string) => {
      const id = nextId++;
      setToasts((t) => [...t, { id, kind, title, description }]);
      setTimeout(() => dismiss(id), 4500);
    };
    return {
      toast,
      success: (t, d) => toast("success", t, d),
      error: (t, d) => toast("error", t, d),
      info: (t, d) => toast("info", t, d),
    };
  }, [dismiss]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed top-4 right-4 z-[100] flex w-[min(22rem,calc(100vw-2rem))] flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className="glass animate-toast pointer-events-auto flex items-start gap-3 rounded-2xl px-4 py-3"
          >
            <span
              className={cn(
                "mt-0.5 shrink-0",
                t.kind === "success" && "text-success",
                t.kind === "error" && "text-destructive",
                t.kind === "info" && "text-cyan",
              )}
            >
              {t.kind === "success" ? (
                <CheckCircle2 className="size-4" />
              ) : t.kind === "error" ? (
                <TriangleAlert className="size-4" />
              ) : (
                <Info className="size-4" />
              )}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-foreground">{t.title}</p>
              {t.description ? (
                <p className="mt-0.5 text-xs text-muted-foreground">{t.description}</p>
              ) : null}
            </div>
            <button
              onClick={() => dismiss(t.id)}
              aria-label="Dismiss notification"
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              <X className="size-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
