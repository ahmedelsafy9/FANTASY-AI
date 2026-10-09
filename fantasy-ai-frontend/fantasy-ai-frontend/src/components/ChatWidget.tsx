import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Send,
  Loader2,
  Trophy,
  ArrowRightLeft,
  Users,
  Shield,
  RefreshCw,
  AlertTriangle,
  ChevronRight,
} from "lucide-react";
import { sendChatMessage, getChatbotStatus } from "@/api/endpoints";
import type { ChatMessage, ChatStatusResponse } from "@/types/api";

interface SuggestionCard {
  title: string;
  desc: string;
  prompt: string;
  icon: typeof Trophy;
}

const SUGGESTION_CARDS_EN: SuggestionCard[] = [
  {
    title: "Best Transfers",
    desc: "Compare moves & evaluate hit costs",
    prompt: "Should I sell Saka for Palmer this week?",
    icon: ArrowRightLeft,
  },
  {
    title: "Captain Pick",
    desc: "Find the highest-ceiling armband",
    prompt: "Who should I captain: Haaland or Salah?",
    icon: Trophy,
  },
  {
    title: "Analyze My Squad",
    desc: "Identify weaknesses & rotation risks",
    prompt: "Analyze my team and identify my biggest weakness",
    icon: Users,
  },
];

const SUGGESTION_CARDS_AR: SuggestionCard[] = [
  {
    title: "أفضل الانتقالات",
    desc: "مقارنة الصفقات وجدوى السالب 4",
    prompt: "هل أبيع ساكا وأشتري بالمر هذا الأسبوع؟",
    icon: ArrowRightLeft,
  },
  {
    title: "شارة الكابتن",
    desc: "أعلى خيارات الكابتنة المتوقعة",
    prompt: "مين أفضل كابتن للجولة دي: هالاند ولا صلاح؟",
    icon: Trophy,
  },
  {
    title: "تحليل التشكيلة",
    desc: "كشف نقاط الضعف ومخاطر المداورة",
    prompt: "حلل تشكيلتي وقولي مين أضعف لاعب عندي",
    icon: Users,
  },
];

function isArabicText(text: string): boolean {
  return /[\u0600-\u06FF]/.test(text);
}

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
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

  // Scroll to bottom on new messages
  useEffect(() => {
    if (messages.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isLoading]);

  // Focus textarea when panel opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => textareaRef.current?.focus(), 250);
    }
  }, [isOpen]);

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
            "Sorry, I couldn't reach the analysis service. Please check your connection and try again.",
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
      // Remove last error message and retry
      setMessages((prev) => prev.slice(0, -1));
      handleSend(lastFailedMessage);
    }
  };

  const suggestionCards = useMemo(
    () => (isArabic ? SUGGESTION_CARDS_AR : SUGGESTION_CARDS_EN),
    [isArabic],
  );

  // Don't show widget if feature is explicitly disabled
  if (statusChecked && status && !status.enabled) return null;

  return (
    <>
      {/* Floating Launcher Button */}
      <AnimatePresence>
        {!isOpen && (
          <motion.button
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.8, opacity: 0 }}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setIsOpen(true)}
            className="fixed bottom-5 right-5 z-50 flex h-14 items-center gap-2.5 rounded-full bg-[#064e3b] px-4 py-3 text-white shadow-xl shadow-emerald-950/20 ring-1 ring-emerald-600/30 transition-all hover:bg-[#073f30] hover:shadow-2xl"
            aria-label="Open Fantasy AI Assistant"
            id="chat-toggle-btn"
          >
            <div className="relative flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-300">
              <Shield className="h-4.5 w-4.5 fill-emerald-400/20 text-emerald-400" />
              <span className="absolute -top-0.5 -right-0.5 flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-400" />
              </span>
            </div>
            <div className="hidden flex-col items-start pr-1 sm:flex">
              <span className="text-xs font-semibold tracking-wide text-white">Fantasy AI</span>
              <span className="text-[10px] font-medium text-emerald-300/90">FPL Co-pilot</span>
            </div>
          </motion.button>
        )}
      </AnimatePresence>

      {/* Floating Chat Panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.96 }}
            transition={{ type: "spring", damping: 28, stiffness: 320 }}
            className="fixed inset-x-3 bottom-3 top-auto z-50 flex h-[620px] max-h-[90vh] flex-col overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-2xl sm:bottom-6 sm:right-6 sm:inset-x-auto sm:w-[430px]"
            id="chat-panel"
          >
            {/* Header: Forest Green Sports Brand */}
            <header className="relative flex items-center justify-between border-b border-emerald-900/40 bg-[#064e3b] px-4 py-3.5 text-white">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500/15 border border-emerald-400/20 text-emerald-300">
                  <Shield className="h-5 w-5 fill-emerald-400/20 text-emerald-400" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold tracking-tight text-white">Fantasy AI</h3>
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/20 px-1.5 py-0.5 text-[10px] font-medium text-emerald-300">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      Live
                    </span>
                  </div>
                  <p className="text-[11px] text-emerald-100/70">Your FPL co-pilot</p>
                </div>
              </div>

              <div className="flex items-center gap-1.5">
                {/* Language Switcher */}
                <button
                  type="button"
                  onClick={() => setIsArabic((v) => !v)}
                  className="rounded-lg px-2 py-1 text-[11px] font-medium text-emerald-200/80 hover:bg-white/10 hover:text-white transition-colors"
                  title="Toggle Arabic / English suggestions"
                >
                  {isArabic ? "English" : "العربية"}
                </button>

                {/* Close Button */}
                <button
                  onClick={() => setIsOpen(false)}
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-emerald-200/80 hover:bg-white/10 hover:text-white transition-colors"
                  aria-label="Close chat"
                  id="chat-close-btn"
                >
                  <X className="h-4.5 w-4.5" />
                </button>
              </div>
            </header>

            {/* Conversation Surface */}
            <div
              className="flex-1 overflow-y-auto bg-[#fafbfa] p-4 text-slate-800"
              id="chat-messages"
            >
              {messages.length === 0 ? (
                /* Welcome Experience */
                <div className="flex h-full flex-col justify-between py-2">
                  <div className="pt-2">
                    <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 text-[#064e3b]">
                      <Trophy className="h-5 w-5 text-[#064e3b]" />
                    </div>
                    <h4 className="text-base font-semibold tracking-tight text-slate-900">
                      {isArabic ? "قرارات الفانتازي تبدأ من هنا." : "Your next FPL decision starts here."}
                    </h4>
                    <p className="mt-1 text-xs text-slate-500 leading-relaxed">
                      {isArabic
                        ? "تحليلات دقيقة للاعبين، نصائح الانتقالات، خيارات الكابتنة، وتقييم شامل للتشكيلة."
                        : "Get player insights, transfer advice, captain picks, and squad analysis."}
                    </p>
                  </div>

                  {/* 3 Compact Action Cards */}
                  <div className="my-auto space-y-2 py-4">
                    <p className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
                      {isArabic ? "ابدأ بسؤال سريع" : "Suggested questions"}
                    </p>
                    {suggestionCards.map((card, idx) => {
                      const Icon = card.icon;
                      return (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => handleSend(card.prompt)}
                          className="group flex w-full items-center justify-between rounded-xl border border-slate-200/80 bg-white p-3 text-left transition-all hover:border-emerald-300 hover:bg-emerald-50/40 hover:shadow-xs focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                        >
                          <div className="flex items-center gap-3">
                            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700 transition-colors group-hover:bg-emerald-100">
                              <Icon className="h-4 w-4" />
                            </div>
                            <div>
                              <div className="text-xs font-semibold text-slate-800 group-hover:text-emerald-900">
                                {card.title}
                              </div>
                              <div className="text-[11px] text-slate-500">
                                {card.desc}
                              </div>
                            </div>
                          </div>
                          <ChevronRight className="h-4 w-4 text-slate-400 transition-transform group-hover:translate-x-0.5 group-hover:text-emerald-600" />
                        </button>
                      );
                    })}
                  </div>

                  <div className="rounded-lg bg-emerald-50/70 border border-emerald-100 p-2.5 text-[11px] text-emerald-900/80">
                    💡 <strong>Pro tip:</strong> You can ask naturally, like <em>&quot;Sell Saka for Palmer?&quot;</em> or paste 9 players from your team.
                  </div>
                </div>
              ) : (
                /* Message Stream */
                <div className="space-y-3.5">
                  {messages.map((msg, i) => (
                    <MessageRow key={i} message={msg} />
                  ))}

                  {/* Real Loading Indicator */}
                  {isLoading && (
                    <div className="flex items-start gap-2.5">
                      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-emerald-100 text-[#064e3b]">
                        <Shield className="h-3.5 w-3.5" />
                      </div>
                      <div className="flex items-center gap-2 rounded-2xl rounded-tl-sm border border-emerald-100 bg-[#f4f7f4] px-3.5 py-2.5 shadow-xs">
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-[#064e3b]" />
                        <span className="text-xs font-medium text-slate-700">
                          {isArabic ? "جاري تحليل البيانات والنماذج..." : "Analyzing data & model projections..."}
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Retry button on error */}
                  {lastFailedMessage && !isLoading && (
                    <div className="flex justify-end pr-1">
                      <button
                        onClick={handleRetry}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors"
                      >
                        <RefreshCw className="h-3 w-3" />
                        Retry last request
                      </button>
                    </div>
                  )}

                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            {/* Warning if AI key is missing */}
            {statusChecked && status && !status.configured && (
              <div className="flex items-center gap-2 border-t border-amber-100 bg-amber-50/80 px-4 py-1.5">
                <AlertTriangle className="h-3 w-3 shrink-0 text-amber-600" />
                <p className="text-[10px] text-amber-700">
                  Using local predictive models & verified FPL data.
                </p>
              </div>
            )}

            {/* Chat Composer */}
            <footer className="border-t border-slate-100 bg-white p-3">
              <div className="relative flex items-end rounded-xl border border-slate-200 bg-slate-50/80 transition-all focus-within:border-emerald-600 focus-within:bg-white focus-within:ring-2 focus-within:ring-emerald-100">
                <textarea
                  ref={textareaRef}
                  rows={1}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={
                    isArabic
                      ? "اسأل عن اللاعبين أو الانتقالات أو الكابتنة..."
                      : "Ask about players, transfers, or fixtures..."
                  }
                  dir={isArabicText(input) ? "rtl" : "ltr"}
                  disabled={isLoading}
                  className="max-h-24 flex-1 resize-none bg-transparent px-3.5 py-2.5 text-xs text-slate-800 placeholder-slate-400 outline-none disabled:opacity-50"
                  id="chat-input"
                />
                <button
                  onClick={() => handleSend()}
                  disabled={!input.trim() || isLoading}
                  className="m-1.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#064e3b] text-white transition-all hover:bg-[#073f30] disabled:cursor-not-allowed disabled:opacity-30"
                  aria-label="Send message"
                  id="chat-send-btn"
                >
                  <Send className="h-3.5 w-3.5" />
                </button>
              </div>
            </footer>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

// ---------------------------------------------------------------
// Message Row & Formatter
// ---------------------------------------------------------------

function MessageRow({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const isArabic = isArabicText(message.content);

  return (
    <div
      className={`flex items-start gap-2.5 ${isUser ? "flex-row-reverse" : "flex-row"}`}
      dir={isArabic ? "rtl" : "ltr"}
    >
      <div
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-xs font-semibold ${
          isUser
            ? "bg-[#064e3b] text-white"
            : "bg-emerald-100 text-[#064e3b]"
        }`}
      >
        {isUser ? "You" : <Shield className="h-3.5 w-3.5" />}
      </div>

      <div
        className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed ${
          isUser
            ? "rounded-tr-xs bg-[#064e3b] text-white font-normal shadow-xs"
            : "rounded-tl-xs border border-slate-200/70 bg-[#f8faf8] text-slate-800 shadow-xs"
        }`}
      >
        <MessageContent text={message.content} isUser={isUser} />
      </div>
    </div>
  );
}

function MessageContent({ text, isUser }: { text: string; isUser: boolean }) {
  if (isUser) {
    return <span className="whitespace-pre-wrap">{text}</span>;
  }

  const lines = text.split("\n");

  return (
    <div className="space-y-1.5 leading-relaxed">
      {lines.map((line, idx) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={idx} className="h-1" />;

        // Markdown Headers (### or ##)
        if (trimmed.startsWith("### ") || trimmed.startsWith("## ")) {
          const header = trimmed.replace(/^#{2,3}\s+/, "");
          return (
            <h4
              key={idx}
              className="mt-2.5 mb-1 flex items-center gap-1.5 border-b border-slate-200/80 pb-1 text-xs font-bold text-[#064e3b]"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              <span>{header}</span>
            </h4>
          );
        }

        // Callout blocks for Recommendation / Verdict / Winner
        if (
          trimmed.startsWith("**Recommendation**:") ||
          trimmed.startsWith("**Verdict**:") ||
          trimmed.startsWith("**Winner**:") ||
          trimmed.startsWith("**Armband Pick**:")
        ) {
          return (
            <div
              key={idx}
              className="my-1.5 rounded-xl border border-emerald-200/80 bg-emerald-50/80 p-2 text-xs font-medium text-emerald-950"
            >
              <InlineMarkdown text={trimmed} />
            </div>
          );
        }

        // Incomplete Squad / Warning Callout
        if (trimmed.startsWith("> [!NOTE]") || trimmed.startsWith("> **Incomplete Squad Notice")) {
          const cleanedNotice = trimmed.replace(/^>\s*(\[!NOTE\])?\s*/, "");
          return (
            <div
              key={idx}
              className="my-1.5 rounded-xl border border-amber-200/80 bg-amber-50/80 p-2 text-[11px] text-amber-900"
            >
              <InlineMarkdown text={cleanedNotice} />
            </div>
          );
        }

        // Bullet items
        if (trimmed.startsWith("• ") || trimmed.startsWith("- ")) {
          const bulletBody = trimmed.replace(/^[•-]\s+/, "");
          return (
            <div key={idx} className="flex items-start gap-1.5 pl-1 text-xs">
              <span className="font-bold text-emerald-600 shrink-0">•</span>
              <span className="flex-1">
                <InlineMarkdown text={bulletBody} />
              </span>
            </div>
          );
        }

        // Source Footnotes
        if (
          trimmed.startsWith("*(") ||
          trimmed.startsWith("Source:") ||
          trimmed.startsWith("• Source:") ||
          trimmed.startsWith("*(Direct from")
        ) {
          return (
            <div
              key={idx}
              className="mt-1.5 border-t border-slate-200/60 pt-1 text-[10px] italic text-slate-400"
            >
              <InlineMarkdown text={trimmed} />
            </div>
          );
        }

        // Regular paragraph
        return (
          <p key={idx} className="text-xs">
            <InlineMarkdown text={trimmed} />
          </p>
        );
      })}
    </div>
  );
}

function InlineMarkdown({ text }: { text: string }) {
  // Regex parsing for bold (**text**) and italic (*text*)
  const parts = text.split(/(\*\*.*?\*\*|\*.*?\*)/g);

  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return (
            <strong key={i} className="font-semibold text-slate-900">
              {part.slice(2, -2)}
            </strong>
          );
        }
        if (part.startsWith("*") && part.endsWith("*") && !part.startsWith("**")) {
          return (
            <em key={i} className="text-slate-600">
              {part.slice(1, -1)}
            </em>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}
