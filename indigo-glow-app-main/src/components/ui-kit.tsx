import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

export function GlassCard({
  className,
  children,
  ...props
}: { className?: string; children: ReactNode } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("glass rounded-3xl p-6", className)} {...props}>
      {children}
    </div>
  );
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "outline" | "danger" | "cyan" | "indigo";
  size?: "xs" | "sm" | "md";
};

export function Button({ variant = "primary", size = "md", className, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full font-medium transition-all duration-200",
        "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "active:scale-[0.97]",
        size === "xs" ? "px-2.5 py-1 text-[11px]" : size === "sm" ? "px-3.5 py-2 text-xs" : "px-5 py-2.5 text-sm",
        variant === "primary" &&
          "bg-gradient-to-r from-indigo to-cyan text-cyan-foreground hover:glow-indigo hover:-translate-y-0.5",
        variant === "secondary" && "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        variant === "outline" &&
          "border border-glass-border bg-glass text-foreground hover:border-cyan/50 hover:-translate-y-0.5",
        variant === "ghost" && "text-muted-foreground hover:bg-secondary hover:text-foreground",
        variant === "danger" &&
          "bg-destructive/15 text-destructive hover:bg-destructive/25 border border-destructive/30",
        variant === "cyan" &&
          "bg-cyan/15 text-cyan hover:bg-cyan/25 border border-cyan/30",
        variant === "indigo" &&
          "bg-indigo/15 text-indigo hover:bg-indigo/25 border border-indigo/30",
        className,
      )}
      {...props}
    />
  );
}

export function Field({
  label,
  hint,
  error,
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string; error?: string }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {label}
      </span>
      <input
        className={cn(
          "w-full rounded-xl border border-input bg-secondary/40 px-4 py-2.5 text-sm text-foreground",
          "placeholder:text-muted-foreground/60 transition-colors",
          "focus:border-cyan/60 focus:ring-2 focus:ring-ring/40 focus:outline-none",
          error && "border-destructive/60",
          className,
        )}
        {...props}
      />
      {error ? (
        <span className="mt-1 block text-xs text-destructive">{error}</span>
      ) : hint ? (
        <span className="mt-1 block text-xs text-muted-foreground">{hint}</span>
      ) : null}
    </label>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton rounded-xl", className)} />;
}

export function Badge({
  children,
  tone = "indigo",
}: {
  children: ReactNode;
  tone?: "indigo" | "cyan" | "success" | "danger" | "warning" | "muted";
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-medium",
        tone === "indigo" && "bg-indigo/15 text-indigo",
        tone === "cyan" && "bg-cyan/15 text-cyan",
        tone === "success" && "bg-success/15 text-success",
        tone === "danger" && "bg-destructive/15 text-destructive",
        tone === "warning" && "bg-warning/15 text-warning",
        tone === "muted" && "bg-secondary text-muted-foreground",
      )}
    >
      {children}
    </span>
  );
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  busy,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div
        className="absolute inset-0 bg-background/70 backdrop-blur-sm"
        onClick={onCancel}
        aria-hidden
      />
      <GlassCard className="animate-rise glow-indigo relative w-full max-w-sm">
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        <p className="mt-2 text-sm text-muted-foreground">{description}</p>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onCancel} disabled={busy}>
            Keep it
          </Button>
          <Button variant="danger" size="sm" onClick={onConfirm} disabled={busy}>
            {busy ? "Working…" : confirmLabel}
          </Button>
        </div>
      </GlassCard>
    </div>
  );
}
