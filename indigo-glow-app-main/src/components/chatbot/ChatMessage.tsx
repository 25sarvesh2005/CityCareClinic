import React from "react";
import { Bot, User, Sparkles } from "lucide-react";
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
      <div className={cn("max-w-[85%] space-y-1", isUser ? "items-end text-right" : "items-start")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-3 text-sm leading-relaxed transition-all",
            isUser
              ? "rounded-tr-xs bg-gradient-to-br from-indigo/30 via-indigo/20 to-cyan/20 border border-cyan/30 text-foreground shadow-md"
              : "rounded-tl-xs glass border border-glass-border text-foreground/95 shadow-md",
          )}
        >
          <div className="whitespace-pre-wrap break-words">{message.content}</div>
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
