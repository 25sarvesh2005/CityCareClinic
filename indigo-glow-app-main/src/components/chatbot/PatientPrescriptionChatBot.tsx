import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bot,
  ChevronRight,
  FileText,
  History,
  Loader2,
  MessageSquarePlus,
  Send,
  ShieldAlert,
  Sparkles,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { ChatMessage, type ChatMessageItem } from "@/components/chatbot/ChatMessage";
import { useToast } from "@/components/Toaster";
import { Badge, Button } from "@/components/ui-kit";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const SUGGESTED_PROMPTS = [
  "Which prescriptions do I have?",
  "What medicines are documented for me?",
  "Explain my dosage and timing",
  "What follow-up date did my doctor write?",
];

type PrescriptionChatSession = {
  session_id: string;
  title: string;
  created_at: string;
};

export function PatientPrescriptionChatBot() {
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessions, setSessions] = useState<PrescriptionChatSession[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const toast = useToast();

  const loadSessions = useCallback(async () => {
    try {
      const data = await api.getPrescriptionChatSessions();
      setSessions(data);
    } catch {
      setSessions([]);
    }
  }, []);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSelectSession = async (sid: string) => {
    setSessionId(sid);
    try {
      const savedMessages = await api.getPrescriptionChatMessages(sid);
      setMessages(savedMessages);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to load prescription chat");
    }
  };

  const handleStartNewChat = () => {
    setSessionId(undefined);
    setMessages([]);
  };

  const handleSendMessage = async (promptText?: string) => {
    const textToSend = (promptText || inputMessage).trim();
    if (!textToSend || loading) return;

    setInputMessage("");
    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        content: textToSend,
        created_at: new Date().toISOString(),
      },
    ]);
    setLoading(true);

    try {
      const res = await api.sendPrescriptionChatMessage({
        ...(sessionId ? { session_id: sessionId } : {}),
        message: textToSend,
      });

      setSessionId(res.session_id);
      setMessages(res.messages);
      void loadSessions();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Prescription assistant is unavailable");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-8.5rem)] min-h-[500px] w-full flex-col overflow-hidden rounded-2xl border border-glass-border bg-card/95 shadow-xl backdrop-blur-2xl">
      {/* Complete Window Header */}
      <div className="flex flex-wrap items-center justify-between border-b border-glass-border bg-secondary/30 px-6 py-4">
        <div className="flex items-center gap-3.5">
          <div className="flex size-11 items-center justify-center rounded-2xl bg-gradient-to-tr from-cyan via-indigo/80 to-indigo text-white shadow-md shadow-cyan/20">
            <FileText className="size-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-foreground tracking-tight flex items-center gap-2">
                Prescription AI Workspace
              </h2>
              <Badge tone="cyan">
                <Sparkles className="size-3 text-cyan inline mr-1" /> Gemini 2.0 AI
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              Patient-scoped prescription records and dosage assistant
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 mt-2 sm:mt-0">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setSidebarOpen((prev) => !prev)}
            className="text-xs gap-1.5"
            title="Toggle Sessions Sidebar"
          >
            <History className="size-4 text-cyan" />
            <span className="hidden md:inline">
              {sidebarOpen ? "Hide History" : "Show History"}
            </span>
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={handleStartNewChat}
            className="text-xs gap-1.5"
          >
            <MessageSquarePlus className="size-4" />
            <span>New Chat</span>
          </Button>
        </div>
      </div>

      {/* Main Workspace Layout (Sidebar + Chat Area) */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Session History Sidebar Panel */}
        {sidebarOpen && (
          <aside className="w-64 sm:w-72 shrink-0 border-r border-glass-border bg-secondary/20 p-4 flex flex-col justify-between animate-fade-in">
            <div className="space-y-4 flex-1 overflow-hidden flex flex-col">
              <div className="flex items-center justify-between px-1">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  <History className="size-3.5" /> Past Prescription Chats
                </span>
                <button
                  type="button"
                  onClick={() => void loadSessions()}
                  className="text-muted-foreground hover:text-cyan transition-colors"
                  title="Refresh Sessions"
                >
                  <RefreshCw className="size-3.5" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
                {sessions.length === 0 ? (
                  <div className="p-4 text-center text-xs text-muted-foreground italic border border-dashed border-glass-border rounded-xl">
                    No prescription chats yet.
                  </div>
                ) : (
                  sessions.map((s) => (
                    <button
                      key={s.session_id}
                      type="button"
                      onClick={() => handleSelectSession(s.session_id)}
                      className={cn(
                        "w-full text-left p-3 rounded-xl transition-all flex items-center justify-between border text-xs group",
                        s.session_id === sessionId
                          ? "bg-cyan/15 border-cyan/40 text-cyan font-semibold shadow-sm"
                          : "border-glass-border/60 hover:bg-secondary/60 hover:border-glass-border text-foreground",
                      )}
                    >
                      <div className="flex flex-col min-w-0 pr-2">
                        <span className="truncate">{s.title || "Prescription Query"}</span>
                        <span className="text-[10px] text-muted-foreground">
                          {new Date(s.created_at).toLocaleDateString(undefined, {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>
                      <ChevronRight className="size-3.5 shrink-0 opacity-40 group-hover:opacity-100 transition-opacity" />
                    </button>
                  ))
                )}
              </div>
            </div>

            <div className="pt-4 border-t border-glass-border/70 text-[11px] text-muted-foreground flex items-center gap-2">
              <ShieldCheck className="size-4 text-cyan shrink-0" />
              <span>Grounded strictly on patient prescription DB.</span>
            </div>
          </aside>
        )}

        {/* Central Chat Workspace */}
        <div className="flex flex-1 flex-col min-w-0 bg-background/40">
          {/* Message Stream */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-6 max-w-xl mx-auto">
                <div className="relative">
                  <div className="size-20 rounded-3xl bg-gradient-to-tr from-cyan/20 to-indigo/20 border border-cyan/30 flex items-center justify-center text-cyan shadow-lg">
                    <FileText className="size-10 text-cyan animate-pulse" />
                  </div>
                  <span className="absolute -bottom-1 -right-1 flex size-5 items-center justify-center rounded-full bg-success text-[10px] font-bold text-white shadow">
                    ✓
                  </span>
                </div>

                <div>
                  <h3 className="text-xl font-bold text-foreground tracking-tight">
                    Ask About Your Prescriptions
                  </h3>
                  <p className="mt-2 text-xs sm:text-sm text-muted-foreground leading-relaxed">
                    I can explain documented medicines, dosage, timing, doctor instructions, and follow-up dates from your CityCare records.
                  </p>
                </div>

                {/* Prompt Suggestions Grid */}
                <div className="w-full space-y-3 pt-2">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Quick Questions:
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    {SUGGESTED_PROMPTS.map((prompt) => (
                      <button
                        key={prompt}
                        type="button"
                        onClick={() => handleSendMessage(prompt)}
                        className="text-xs p-3 rounded-xl border border-glass-border bg-card/60 text-foreground hover:border-cyan/50 hover:bg-secondary/60 transition-all text-left flex items-center justify-between group shadow-sm"
                      >
                        <span className="font-medium">{prompt}</span>
                        <ChevronRight className="size-4 text-cyan opacity-0 group-hover:opacity-100 transition-opacity" />
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

            {/* Loading Assistant State */}
            {loading && (
              <div className="flex items-center gap-3 text-xs text-muted-foreground animate-pulse p-3 rounded-xl bg-cyan/5 border border-cyan/20 max-w-md">
                <div className="flex size-8 items-center justify-center rounded-xl bg-cyan/20 border border-cyan/40 text-cyan">
                  <Loader2 className="size-4 animate-spin" />
                </div>
                <span>Gemini is reading grounded prescription records…</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Prompt Input Box */}
          <div className="border-t border-glass-border p-4 bg-secondary/30 space-y-2">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="flex items-center gap-3"
            >
              <input
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                placeholder="Ask about your prescribed medicines, dosage, timing..."
                disabled={loading}
                className="flex-1 rounded-2xl border border-input bg-card/90 px-4 py-3 text-xs sm:text-sm text-foreground placeholder:text-muted-foreground/60 focus:border-cyan/60 focus:outline-none focus:ring-2 focus:ring-ring/40 shadow-inner"
              />
              <Button
                type="submit"
                variant="primary"
                size="sm"
                disabled={!inputMessage.trim() || loading}
                className="rounded-2xl px-5 py-3 h-auto gap-2"
              >
                {loading ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <>
                    <span>Send</span>
                    <Send className="size-4" />
                  </>
                )}
              </Button>
            </form>
            <div className="flex items-center justify-between text-[11px] text-muted-foreground px-2">
              <span>Press Enter to send message</span>
              <span className="text-cyan font-medium flex items-center gap-1">
                <ShieldAlert className="size-3 text-cyan inline" /> Medical safety filters active
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
