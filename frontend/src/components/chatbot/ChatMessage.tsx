import React from "react";
import { Bot, User } from "lucide-react";
import { cn } from "@/lib/utils";

export type ChatMessageItem = {
  message_id?: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  created_at?: string;
};

function formatTime(isoString?: string) {
  if (!isoString) return "";
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function renderAssistantContent(content: string) {
  const lines = content.split("\n");

  return (
    <div className="space-y-2.5">
      {lines.map((rawLine, index) => {
        const line = rawLine.trim();
        if (!line) return <div key={index} className="h-1" />;

        const isPrescriptionHeading = /^Prescription\s+\d+\s+-/i.test(line);
        const [label, ...valueParts] = line.split(":");
        const hasLabel = Boolean(label && valueParts.length > 0 && label.length <= 36);

        if (isPrescriptionHeading) {
          return (
            <div
              key={index}
              className="mt-3 rounded-xl border border-indigo/20 bg-indigo/10 px-3 py-2 text-xs font-bold text-indigo first:mt-0"
            >
              {line}
            </div>
          );
        }

        if (hasLabel) {
          return (
            <div
              key={index}
              className="rounded-xl border border-glass-border/60 bg-card/70 px-3 py-2"
            >
              <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                {label}
              </span>
              <span className="block pt-0.5 text-sm text-foreground/95">
                {valueParts.join(":").trim()}
              </span>
            </div>
          );
        }

        return (
          <p key={index} className="text-sm leading-relaxed text-foreground/95">
            {line}
          </p>
        );
      })}
    </div>
  );
}

export function ChatMessage({ message }: { message: ChatMessageItem }) {
  const isUser = message.role === "user";
  const formattedTime = formatTime(message.created_at);

  return (
    <div
      className={cn(
        "flex items-start gap-3 text-sm animate-fade-in",
        isUser ? "flex-row-reverse" : "flex-row",
      )}
    >
      {/* Role Avatar */}
      <div
        className={cn(
          "flex size-8 shrink-0 items-center justify-center rounded-xl border text-xs font-semibold shadow-sm",
          isUser
            ? "border-cyan/50 bg-cyan/15 text-cyan"
            : "border-indigo/50 bg-indigo/15 text-indigo",
        )}
      >
        {isUser ? <User className="size-4" /> : <Bot className="size-4" />}
      </div>

      {/* Message Bubble */}
      <div
        className={cn(
          "space-y-1",
          isUser ? "max-w-[85%] items-end text-right" : "max-w-[94%] items-start",
        )}
      >
        <div
          className={cn(
            "rounded-2xl px-4 py-3 text-sm leading-relaxed transition-all",
            isUser
              ? "rounded-tr-sm border border-cyan/20 bg-cyan/10 text-foreground shadow-sm"
              : "rounded-tl-sm border border-glass-border bg-card text-foreground/95 shadow-sm",
          )}
        >
          <div className="break-words">
            {isUser ? (
              <div className="whitespace-pre-wrap">{message.content}</div>
            ) : (
              renderAssistantContent(message.content)
            )}
          </div>
        </div>

        {formattedTime && (
          <div className="px-1 text-[10px] text-muted-foreground/70 font-medium">
            {formattedTime}
          </div>
        )}
      </div>
    </div>
  );
}
