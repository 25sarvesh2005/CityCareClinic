import React, { useEffect, useRef, useState } from "react";
import {
  Bot,
  ChevronRight,
  MessageSquarePlus,
  History,
  Loader2,
  Send,
  Sparkles,
  X,
} from "lucide-react";
import { ChatMessage, type ChatMessageItem } from "@/components/chatbot/ChatMessage";
import { useToast } from "@/components/Toaster";
import { Button, GlassCard } from "@/components/ui-kit";
import { api, type ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

const SUGGESTED_PROMPTS = [
  "Show my schedule for today",
  "Are there any open slots tomorrow?",
  "List doctors in our clinic",
  "Show appointments for this week",
];

export function ScheduleChatBot() {
  const [isOpen, setIsOpen] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessions, setSessions] = useState<{ session_id: string; title: string; created_at: string }[]>([]);
  const [showSessionsDropdown, setShowSessionsDropdown] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const toast = useToast();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (isOpen) {
      loadSessions();
    }
  }, [isOpen]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const loadSessions = async () => {
    try {
      const data = await api.getChatSessions();
      setSessions(data);
    } catch {
      // Ignore initial session load error if none exists
    }
  };

  const handleSelectSession = async (sid: string) => {
    setSessionId(sid);
    setShowSessionsDropdown(false);
    try {
      const msgs = await api.getChatMessages(sid);
      setMessages(msgs);
    } catch (err: any) {
      toast.error(err?.message || "Failed to load session history");
    }
  };

  const handleStartNewChat = () => {
    setSessionId(undefined);
    setMessages([]);
    setShowSessionsDropdown(false);
  };

  const handleSendMessage = async (promptText?: string) => {
    const textToSend = (promptText || inputMessage).trim();
    if (!textToSend || loading) return;

    setInputMessage("");

    // Optimistically add user message to UI
    const tempUserMsg: ChatMessageItem = {
      role: "user",
      content: textToSend,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, tempUserMsg]);
    setLoading(true);

    try {
      const res = await api.sendScheduleChatMessage({
        ...(sessionId ? { session_id: sessionId } : {}),
        message: textToSend,
      });

      setSessionId(res.session_id);
      setMessages(res.messages);
      loadSessions();
    } catch (err: any) {
      toast.error(err?.message || "Failed to get response from Schedule Assistant");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Floating Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className={cn(
          "fixed bottom-6 right-6 z-40 flex items-center gap-2.5 rounded-full px-5 py-3.5 text-sm font-semibold shadow-2xl transition-all duration-300",
          "bg-gradient-to-r from-indigo via-purple-600 to-cyan text-white hover:scale-105 active:scale-95",
          "glow-indigo border border-cyan/40",
          isOpen && "ring-2 ring-cyan ring-offset-2 ring-offset-background",
        )}
      >
        <Sparkles className="size-5 animate-pulse text-cyan-200" />
        <span className="tracking-wide">Schedule AI</span>
      </button>

      {/* Slide-Over Chatbot Drawer Overlay */}
      {isOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-background/60 backdrop-blur-md transition-opacity animate-fade-in"
            onClick={() => setIsOpen(false)}
          />

          <div className="fixed inset-y-0 right-0 flex max-w-full pl-10">
            <div className="w-screen max-w-md animate-slide-in-from-right">
              <div className="flex h-full flex-col border-l border-glass-border bg-card/95 backdrop-blur-2xl shadow-2xl">
                {/* Header */}
                <div className="flex items-center justify-between border-b border-glass-border p-4 bg-secondary/30">
                  <div className="flex items-center gap-3">
                    <div className="flex size-10 items-center justify-center rounded-2xl bg-gradient-to-tr from-indigo to-cyan text-white shadow-md">
                      <Bot className="size-6" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground text-sm flex items-center gap-1.5">
                        Schedule Assistant <Sparkles className="size-3.5 text-cyan" />
                      </h3>
                      <p className="text-[11px] text-muted-foreground">
                        Gemini Function Calling · Live Clinic Data
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5">
                    {/* Session Selector Button */}
                    <button
                      type="button"
                      onClick={() => setShowSessionsDropdown((prev) => !prev)}
                      className="rounded-xl border border-glass-border p-2 text-muted-foreground hover:bg-secondary hover:text-foreground transition-all"
                      title="Chat History"
                    >
                      <History className="size-4" />
                    </button>

                    {/* New Chat Button */}
                    <button
                      type="button"
                      onClick={handleStartNewChat}
                      className="rounded-xl border border-glass-border p-2 text-muted-foreground hover:bg-secondary hover:text-foreground transition-all"
                      title="New Chat"
                    >
                      <MessageSquarePlus className="size-4" />
                    </button>

                    {/* Close Panel Button */}
                    <button
                      type="button"
                      onClick={() => setIsOpen(false)}
                      className="rounded-xl border border-glass-border p-2 text-muted-foreground hover:bg-destructive/20 hover:text-destructive transition-all"
                    >
                      <X className="size-4" />
                    </button>
                  </div>
                </div>

                {/* Session Dropdown Drawer if open */}
                {showSessionsDropdown && (
                  <div className="border-b border-glass-border bg-secondary/40 p-3 space-y-2 animate-fade-in text-xs">
                    <div className="flex items-center justify-between font-semibold text-muted-foreground px-1">
                      <span>Past Chat Sessions</span>
                      <button
                        type="button"
                        onClick={handleStartNewChat}
                        className="text-cyan hover:underline flex items-center gap-1 text-[11px]"
                      >
                        + Start Fresh Session
                      </button>
                    </div>
                    {sessions.length === 0 ? (
                      <p className="p-2 text-muted-foreground italic">No prior chat sessions found.</p>
                    ) : (
                      <div className="max-h-40 overflow-y-auto space-y-1 pr-1">
                        {sessions.map((s) => (
                          <button
                            key={s.session_id}
                            type="button"
                            onClick={() => handleSelectSession(s.session_id)}
                            className={cn(
                              "w-full text-left p-2 rounded-xl transition-all flex items-center justify-between border",
                              s.session_id === sessionId
                                ? "bg-cyan/15 border-cyan/40 text-cyan font-medium"
                                : "border-glass-border/40 hover:bg-secondary hover:border-glass-border text-foreground",
                            )}
                          >
                            <span className="truncate max-w-[240px]">{s.title}</span>
                            <ChevronRight className="size-3 shrink-0 opacity-60" />
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Message Timeline Area */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {messages.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-4">
                      <div className="size-16 rounded-3xl bg-cyan/10 border border-cyan/20 flex items-center justify-center text-cyan shadow-inner">
                        <Bot className="size-8 animate-bounce" />
                      </div>
                      <div>
                        <h4 className="font-semibold text-foreground text-base">
                          How can I help with your schedule today?
                        </h4>
                        <p className="mt-1 text-xs text-muted-foreground leading-relaxed max-w-xs">
                          Ask me about doctor rosters, daily appointment bookings, or date ranges.
                        </p>
                      </div>

                      {/* Prompt Suggestions Chips */}
                      <div className="w-full pt-4 space-y-2 text-left">
                        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground px-1">
                          Suggested Prompts:
                        </span>
                        <div className="flex flex-col gap-2">
                          {SUGGESTED_PROMPTS.map((prompt) => (
                            <button
                              key={prompt}
                              type="button"
                              onClick={() => handleSendMessage(prompt)}
                              className="text-xs p-2.5 rounded-xl border border-glass-border bg-secondary/30 text-foreground hover:border-cyan/50 hover:bg-secondary/60 transition-all text-left flex items-center justify-between group"
                            >
                              <span>{prompt}</span>
                              <ChevronRight className="size-3.5 text-cyan opacity-0 group-hover:opacity-100 transition-opacity" />
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    messages.map((msg, idx) => (
                      <ChatMessage key={msg.message_id || idx} message={msg} />
                    ))
                  )}

                  {/* Loading Assistant Bubble */}
                  {loading && (
                    <div className="flex items-center gap-3 text-xs text-muted-foreground animate-pulse p-2">
                      <div className="flex size-8 items-center justify-center rounded-xl bg-indigo/15 border border-indigo/40 text-indigo">
                        <Loader2 className="size-4 animate-spin" />
                      </div>
                      <span>Gemini is checking schedule tools & querying data…</span>
                    </div>
                  )}

                  <div ref={messagesEndRef} />
                </div>

                {/* Input Controls Footer */}
                <div className="border-t border-glass-border p-4 bg-secondary/20 space-y-2">
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      handleSendMessage();
                    }}
                    className="flex items-center gap-2"
                  >
                    <input
                      type="text"
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      placeholder="Ask about schedule, appointments..."
                      disabled={loading}
                      className="flex-1 rounded-2xl border border-input bg-secondary/40 px-4 py-2.5 text-xs text-foreground placeholder:text-muted-foreground/60 focus:border-cyan/60 focus:outline-none focus:ring-2 focus:ring-ring/40"
                    />
                    <Button
                      type="submit"
                      variant="primary"
                      size="sm"
                      disabled={!inputMessage.trim() || loading}
                      className="rounded-2xl px-4 py-2.5 h-auto"
                    >
                      {loading ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : (
                        <Send className="size-4" />
                      )}
                    </Button>
                  </form>
                  <p className="text-[10px] text-center text-muted-foreground/60">
                    Security enforced: Doctor & owner scopes strictly validated per tool call.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
