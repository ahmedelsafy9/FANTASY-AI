import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import {
  Send,
  Loader2,
  Trophy,
  ArrowRightLeft,
  Users,
  ShieldCheck,
  RefreshCw,
  AlertTriangle,
  RotateCcw,
  Sparkles,
  ChevronRight,
} from "lucide-react";
import { sendChatMessage, getChatbotStatus } from "@/api/endpoints";
import type { ChatMessage, ChatStatusResponse } from "@/types/api";
import { AssistantIcon } from "@/components/brand/AssistantIcon";
import { cn } from "@/lib/utils";

interface SuggestionCard {
  title: string;
  desc: string;
  prompt: string;
  icon: typeof Trophy;
}

const STARTER_PROMPTS_EN: SuggestionCard[] = [
  {
    title: "Captaincy Recommendation",
    desc: "Evaluate highest ceiling & form for the armband",
    prompt: "Who should I captain this gameweek: Haaland, Palmer, or Salah?",
    icon: Trophy,
  },
  {
    title: "Transfer Analysis",
    desc: "Compare form, fixtures & hit feasibility",
    prompt: "Should I sell Saka for Palmer this week?",
    icon: ArrowRightLeft,
  },
  {
    title: "Squad Diagnostics",
    desc: "Scan for rotation risks and low-form assets",
    prompt: "Analyze my squad and identify my biggest weakness or rotation risk",
    icon: Users,
  },
  {
    title: "Injury & Availability Check",
    desc: "Verify latest official fitness & flag reports",
    prompt: "Check the availability and news for my target players",
    icon: ShieldCheck,
  },
];

const STARTER_PROMPTS_AR: SuggestionCard[] = [
  {
    title: "شارة الكابتن",
    desc: "أعلى خيارات الكابتنة المتوقعة وفقاً للنماذج",
    prompt: "مين أفضل كابتن للجولة دي: هالاند ولا بالمر ولا صلاح؟",
    icon: Trophy,
  },
  {
    title: "تقييم الانتقالات",
    desc: "مقارنة الصفقات وجدوى نقاط السالب 4",
    prompt: "هل أبيع ساكا وأشتري بالمر هذا الأسبوع؟",
    icon: ArrowRightLeft,
  },
  {
    title: "تحليل التشكيلة",
    desc: "كشف نقاط الضعف ومخاطر المداورة",
    prompt: "حلل تشكيلتي وقولي مين أضعف لاعب ومين مهدد بالمداورة",
    icon: Users,
  },
  {
    title: "فحص الإصابات والجاهزية",
    desc: "حالة الغيابات والتقارير الرسمية",
    prompt: "هل هناك أي إصابات أو إيقافات مؤكدة للاعبين الأساسيين؟",
    icon: ShieldCheck,
  },
];

function isArabicText(text: string): boolean {
  return /[\u0600-\u06FF]/.test(text);
}

export default function Assistant() {
  const [isArabic, setIsArabic] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null);
  const [status, setStatus] = useState<ChatStatusResponse | null>(null);
  const [statusChecked, setStatusChecked] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Check chatbot availability status on mount
  useEffect(() => {
    getChatbotStatus()
      .then((s) => {
        setStatus(s);
        setStatusChecked(true);
      })
      .catch(() => setStatusChecked(true));
  }, []);

  // Auto-scroll on new messages
  useEffect(() => {
    if (messages.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isLoading]);

  const handleSend = useCallback(
    async (textToSend?: string) => {
      const text = (textToSend ?? input).trim();
      if (!text || isLoading) return;

      const userMsg: ChatMessage = { role: "user", content: text };
      const currentHistory = [...messages, userMsg];
      setMessages(currentHistory);
      setInput("");
      setIsLoading(true);
      setLastFailedMessage(null);

      try {
        const response = await sendChatMessage(text, messages);
        const assistantMsg: ChatMessage = {
          role: "assistant",
          content: response.response,
        };
        setMessages([...currentHistory, assistantMsg]);
      } catch {
        setLastFailedMessage(text);
        const errorMsg: ChatMessage = {
          role: "assistant",
          content:
            "Sorry, I couldn't reach the tactical analysis service. Please check your network connection and retry.",
        };
        setMessages([...currentHistory, errorMsg]);
      } finally {
        setIsLoading(false);
      }
    },
    [input, isLoading, messages],
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleRetry = () => {
    if (lastFailedMessage) {
      setMessages((prev) => prev.slice(0, -1));
      handleSend(lastFailedMessage);
    }
  };

  const handleReset = () => {
    setMessages([]);
    setLastFailedMessage(null);
    setInput("");
  };

  const starters = useMemo(
    () => (isArabic ? STARTER_PROMPTS_AR : STARTER_PROMPTS_EN),
    [isArabic],
  );

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 lg:px-8 pb-safe-bottom">
      {/* Header Banner: Stadium Luxe Tactical Studio */}
      <section className="relative overflow-hidden rounded-2xl border border-gold-border/40 bg-gradient-to-br from-stadium-deep via-stadium-surface to-stadium-dark p-6 sm:p-8 text-ivory-surface shadow-card mb-6">
        {/* Architectural lighting effect */}
        <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-gold-metallic/15 blur-3xl pointer-events-none" />
        <div className="absolute right-12 bottom-0 w-80 h-32 opacity-10 pointer-events-none border border-gold-bright rounded-t-full" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            <AssistantIcon size="lg" glow={true} className="mt-1 shrink-0" />
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-gold-border/60 bg-gold-light/10 backdrop-blur-sm px-3 py-0.5 text-xs font-black text-gold-bright mb-2">
                <Sparkles size={13} className="text-gold-bright" />
                <span>Fantasy Wizard Intelligence Hub</span>
              </div>
              <h1 className="font-display text-2xl sm:text-3xl font-black text-ivory-surface tracking-tight">
                AI Tactical Co-Pilot
              </h1>
              <p className="mt-1 text-xs sm:text-sm font-medium text-ink-light-secondary max-w-2xl leading-relaxed">
                Data-driven FPL strategist. Query player comparisons, armband optimization, transfer impacts, and official fitness news.
              </p>
            </div>
          </div>

          {/* Quick Controls */}
          <div className="flex items-center gap-2 self-start md:self-auto shrink-0">
            <button
              type="button"
              onClick={() => setIsArabic((v) => !v)}
              className="rounded-xl border border-gold-border/40 bg-stadium-deep/80 px-3 py-1.5 text-xs font-black text-gold-bright hover:bg-gold-light/10 transition-colors cursor-pointer"
              title="Toggle language"
            >
              {isArabic ? "English" : "العربية"}
            </button>

            {messages.length > 0 && (
              <button
                type="button"
                onClick={handleReset}
                className="flex items-center gap-1.5 rounded-xl border border-border/40 bg-stadium-deep/80 px-3 py-1.5 text-xs font-bold text-ink-light-secondary hover:text-ivory-surface hover:bg-stadium-surface transition-colors cursor-pointer"
                title="Start a new tactical conversation"
              >
                <RotateCcw size={13} />
                <span>New Session</span>
              </button>
            )}
          </div>
        </div>
      </section>

      {/* Main Conversation Canvas */}
      <div className="flex flex-col rounded-2xl border border-border bg-ivory-surface shadow-card overflow-hidden min-h-[580px] h-[calc(100vh-280px)] max-h-[820px]">
        {/* Workspace Toolbar */}
        <div className="flex items-center justify-between border-b border-border/80 bg-ivory-subtle px-4 py-2.5 text-xs">
          <div className="flex items-center gap-2 text-ink-secondary font-bold">
            <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>Active Model:</span>
            <span className="font-mono font-black text-ink-primary">
              {status?.model ?? "FPL Multi-Objective Scorer & Resolver"}
            </span>
          </div>

          {statusChecked && status && !status.configured && (
            <div className="flex items-center gap-1.5 text-[11px] font-bold text-gold-dark bg-gold-light px-2.5 py-0.5 rounded-full border border-gold-border">
              <AlertTriangle size={12} />
              <span>Running verified FPL database & local models</span>
            </div>
          )}
        </div>

        {/* Message Stream or Empty Welcome with Starter Cards */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 bg-ivory-surface" id="assistant-messages">
          {messages.length === 0 ? (
            <div className="flex flex-col justify-between h-full max-w-3xl mx-auto py-4">
              <div>
                <div className="flex items-center gap-3 mb-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-stadium-deep text-gold-bright shadow-sm">
                    <Sparkles size={20} />
                  </div>
                  <div>
                    <h3 className="font-display text-lg font-black text-ink-primary">
                      {isArabic ? "قرارات الفانتازي الذكية تبدأ هنا" : "How can the Wizard assist your Gameweek?"}
                    </h3>
                    <p className="text-xs font-semibold text-ink-secondary">
                      {isArabic
                        ? "اختر سؤالاً سريعاً من المقترحات أو اكتب استفسارك مباشرة"
                        : "Select an analytical starter or ask any specific question about your squad."}
                    </p>
                  </div>
                </div>

                {/* 4 Starter Prompts Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-6">
                  {starters.map((item, idx) => {
                    const Icon = item.icon;
                    return (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => handleSend(item.prompt)}
                        className="group flex flex-col justify-between rounded-xl border border-border bg-ivory-subtle/80 p-4 text-left transition-all duration-200 hover:border-gold-metallic hover:bg-ivory-surface hover:shadow-card cursor-pointer focus:outline-none focus:ring-2 focus:ring-gold-metallic/40"
                      >
                        <div className="flex items-start justify-between w-full mb-2">
                          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-stadium-deep text-gold-bright transition-colors group-hover:scale-105">
                            <Icon size={16} />
                          </div>
                          <ChevronRight size={16} className="text-ink-secondary transition-transform group-hover:translate-x-1 group-hover:text-gold-metallic" />
                        </div>
                        <div>
                          <div className="font-display text-sm font-black text-ink-primary group-hover:text-stadium-deep">
                            {item.title}
                          </div>
                          <div className="text-xs font-medium text-ink-secondary mt-0.5 line-clamp-1">
                            {item.desc}
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Strategic Tip */}
              <div className="mt-6 rounded-xl bg-gold-light border border-gold-border p-3.5 text-xs text-gold-dark font-medium flex items-start gap-2.5">
                <span className="text-base leading-none">💡</span>
                <p>
                  <strong>Tactical Tip:</strong> You can ask comparison questions naturally, like{" "}
                  <em>&ldquo;Is Palmer worth a -4 hit over Diaz?&rdquo;</em> or request availability reports like{" "}
                  <em>&ldquo;Who is doubtful for Arsenal this weekend?&rdquo;</em>
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-4 max-w-3xl mx-auto">
              {messages.map((msg, i) => (
                <AssistantMessageBubble key={i} message={msg} />
              ))}

              {/* Model Loading State */}
              {isLoading && (
                <div className="flex items-start gap-3">
                  <AssistantIcon size="sm" className="mt-1" />
                  <div className="flex items-center gap-2.5 rounded-2xl rounded-tl-sm border border-border bg-ivory-subtle px-4 py-3 shadow-xs">
                    <Loader2 size={16} className="animate-spin text-gold-metallic" />
                    <span className="text-xs font-bold text-ink-secondary">
                      {isArabic
                        ? "جاري مراجعة نماذج التوقع وبيانات الفانتازي..."
                        : "Querying predictive models & Gameweek fixtures..."}
                    </span>
                  </div>
                </div>
              )}

              {/* Retry on Error */}
              {lastFailedMessage && !isLoading && (
                <div className="flex justify-end pr-2">
                  <button
                    onClick={handleRetry}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-ivory-surface px-3 py-1.5 text-xs font-black text-ink-secondary hover:text-ink-primary hover:border-gold-border shadow-xs transition-colors cursor-pointer"
                  >
                    <RefreshCw size={13} />
                    <span>Retry Request</span>
                  </button>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Composer Footer */}
        <footer className="border-t border-border bg-ivory-subtle p-3 sm:p-4">
          <div className="max-w-3xl mx-auto">
            <div className="relative flex items-end rounded-xl border border-border bg-ivory-surface transition-all focus-within:border-gold-metallic focus-within:ring-2 focus-within:ring-gold-metallic/30 shadow-xs">
              <textarea
                ref={textareaRef}
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  isArabic
                    ? "اسأل عن أي لاعب، مقارنة، كابتن، أو تشكيلة..."
                    : "Ask about any player, transfer decision, captaincy, or team weakness..."
                }
                dir={isArabicText(input) ? "rtl" : "ltr"}
                disabled={isLoading}
                className="max-h-32 min-h-[44px] flex-1 resize-none bg-transparent px-4 py-3 text-xs sm:text-sm text-ink-primary placeholder-ink-secondary outline-none disabled:opacity-50"
                id="assistant-input"
              />
              <button
                type="button"
                onClick={() => handleSend()}
                disabled={!input.trim() || isLoading}
                className="m-2 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-stadium-deep text-gold-bright transition-all hover:bg-stadium-forest disabled:opacity-30 disabled:cursor-not-allowed shadow-xs cursor-pointer"
                aria-label="Send message to assistant"
                id="assistant-send-btn"
              >
                <Send size={16} />
              </button>
            </div>
            <div className="mt-1.5 flex items-center justify-between text-[10px] text-ink-secondary font-semibold px-1">
              <span>Press Enter to send, Shift+Enter for new line</span>
              <span>Fantasy Wizard ML Analytics</span>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------
// Message Bubble & Formatter
// ---------------------------------------------------------------

function AssistantMessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const isArabic = isArabicText(message.content);

  return (
    <div
      className={cn(
        "flex items-start gap-3",
        isUser ? "flex-row-reverse" : "flex-row",
      )}
      dir={isArabic ? "rtl" : "ltr"}
    >
      {/* Avatar Indicator */}
      <div className="shrink-0 mt-0.5">
        {isUser ? (
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-stadium-deep text-ivory-surface font-display font-black text-xs shadow-xs">
            You
          </div>
        ) : (
          <AssistantIcon size="sm" />
        )}
      </div>

      {/* Bubble Content */}
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-3 text-xs sm:text-sm leading-relaxed",
          isUser
            ? "rounded-tr-xs bg-stadium-deep text-ivory-surface font-medium shadow-sm"
            : "rounded-tl-xs border border-border bg-ivory-surface text-ink-primary shadow-xs",
        )}
      >
        <AssistantMarkdownContent text={message.content} isUser={isUser} />
      </div>
    </div>
  );
}

function AssistantMarkdownContent({
  text,
  isUser,
}: {
  text: string;
  isUser: boolean;
}) {
  if (isUser) {
    return <span className="whitespace-pre-wrap">{text}</span>;
  }

  const lines = text.split("\n");

  return (
    <div className="space-y-2 leading-relaxed">
      {lines.map((line, idx) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={idx} className="h-1" />;

        // Headers (### or ##)
        if (trimmed.startsWith("### ") || trimmed.startsWith("## ")) {
          const header = trimmed.replace(/^#{2,3}\s+/, "");
          return (
            <h4
              key={idx}
              className="mt-3 mb-1.5 flex items-center gap-2 border-b border-border pb-1 font-display text-xs sm:text-sm font-black text-stadium-deep"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-gold-metallic" />
              <span>{header}</span>
            </h4>
          );
        }

        // Callout blocks for Key Recommendations / Verdict / Armband Pick
        if (
          trimmed.startsWith("**Recommendation**:") ||
          trimmed.startsWith("**Verdict**:") ||
          trimmed.startsWith("**Winner**:") ||
          trimmed.startsWith("**Armband Pick**:") ||
          trimmed.startsWith("**Summary**:")
        ) {
          return (
            <div
              key={idx}
              className="my-2 rounded-xl border border-gold-border bg-gold-light p-2.5 text-xs sm:text-sm font-semibold text-gold-dark"
            >
              <InlineFormatting text={trimmed} />
            </div>
          );
        }

        // Notes and Notices
        if (trimmed.startsWith("> [!NOTE]") || trimmed.startsWith("> **")) {
          const cleaned = trimmed.replace(/^>\s*(\[!NOTE\])?\s*/, "");
          return (
            <div
              key={idx}
              className="my-2 rounded-xl border border-border bg-ivory-subtle p-2.5 text-xs text-ink-secondary font-medium"
            >
              <InlineFormatting text={cleaned} />
            </div>
          );
        }

        // Bullet points
        if (trimmed.startsWith("• ") || trimmed.startsWith("- ")) {
          const body = trimmed.replace(/^[•-]\s+/, "");
          return (
            <div key={idx} className="flex items-start gap-2 pl-1">
              <span className="font-black text-gold-muted shrink-0">•</span>
              <span className="flex-1">
                <InlineFormatting text={body} />
              </span>
            </div>
          );
        }

        // Source or Footnotes
        if (
          trimmed.startsWith("*(") ||
          trimmed.startsWith("Source:") ||
          trimmed.startsWith("• Source:") ||
          trimmed.startsWith("*(Direct from")
        ) {
          return (
            <div
              key={idx}
              className="mt-2 border-t border-border/60 pt-1 text-[11px] italic text-ink-secondary"
            >
              <InlineFormatting text={trimmed} />
            </div>
          );
        }

        // Standard Paragraph
        return (
          <p key={idx}>
            <InlineFormatting text={trimmed} />
          </p>
        );
      })}
    </div>
  );
}

function InlineFormatting({ text }: { text: string }) {
  const parts = text.split(/(\*\*.*?\*\*|\*.*?\*)/g);

  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return (
            <strong key={i} className="font-black text-ink-primary">
              {part.slice(2, -2)}
            </strong>
          );
        }
        if (part.startsWith("*") && part.endsWith("*") && !part.startsWith("**")) {
          return (
            <em key={i} className="text-ink-secondary">
              {part.slice(1, -1)}
            </em>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}
