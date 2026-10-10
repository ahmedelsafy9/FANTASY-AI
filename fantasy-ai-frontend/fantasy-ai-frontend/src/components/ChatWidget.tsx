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
            className="fixed bottom-5 right-5 z-50 flex h-14 items-center gap-2.5 rounded-full bg-[#452477] px-4 py-3 text-white shadow-xl shadow-[#452477]/30 ring-1 ring-[#7041C5]/40 transition-all hover:bg-[#381B62] hover:shadow-2xl"
            aria-label="Open Fantasy AI Assistant"
            id="chat-toggle-btn"
          >
            <div className="relative flex h-8 w-8 items-center justify-center rounded-full bg-white/15 text-[#B9DDF5]">
              <Shield className="h-4.5 w-4.5 fill-[#B9DDF5]/20 text-[#B9DDF5]" />
              <span className="absolute -top-0.5 -right-0.5 flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#B9DDF5] opacity-75" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[#B9DDF5]" />
              </span>
            </div>
            <div className="hidden flex-col items-start pr-1 sm:flex">
              <span className="text-xs font-bold tracking-wide text-white">Fantasy AI</span>
              <span className="text-[10px] font-medium text-[#EEE7FA]/80">FPL Assistant</span>
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
            className="fixed inset-x-3 bottom-3 top-auto z-50 flex h-[620px] max-h-[90vh] flex-col overflow-hidden rounded-2xl border border-[#E8E3ED] bg-white shadow-2xl sm:bottom-6 sm:right-6 sm:inset-x-auto sm:w-[430px]"
            id="chat-panel"
          >
            {/* Header: EPL Deep Purple Studio */}
            <header className="relative flex items-center justify-between border-b border-[#452477]/20 bg-gradient-to-r from-[#452477] to-[#381B62] px-4 py-3.5 text-white">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/15 border border-white/20 text-[#B9DDF5]">
                  <Shield className="h-5 w-5 fill-[#B9DDF5]/20 text-[#B9DDF5]" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-black tracking-tight text-white">Fantasy AI</h3>
                    <span className="inline-flex items-center gap-1 rounded-full bg-white/15 px-1.5 py-0.5 text-[10px] font-bold text-[#EEE7FA]">
                      <span className="h-1.5 w-1.5 rounded-full bg-[#B9DDF5] animate-pulse" />
                      Live
                    </span>
                  </div>
                  <p className="text-[11px] text-[#EEE7FA]/75 font-medium">Your FPL Co-pilot</p>
                </div>
              </div>

              <div className="flex items-center gap-1.5">
                {/* Language Switcher */}
                <button
                  type="button"
                  onClick={() => setIsArabic((v) => !v)}
                  className="rounded-lg px-2 py-1 text-[11px] font-bold text-[#EEE7FA]/80 hover:bg-white/10 hover:text-white transition-colors"
                  title="Toggle Arabic / English suggestions"
                >
                  {isArabic ? "English" : "العربية"}
                </button>

                {/* Close Button */}
                <button
                  onClick={() => setIsOpen(false)}
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-[#EEE7FA]/80 hover:bg-white/10 hover:text-white transition-colors"
                  aria-label="Close chat"
                  id="chat-close-btn"
                >
                  <X className="h-4.5 w-4.5" />
                </button>
              </div>
            </header>

            {/* Conversation Surface */}
            <div
              className="flex-1 overflow-y-auto bg-[#F8F7FA] p-4 text-[#19171D]"
              id="chat-messages"
            >
              {messages.length === 0 ? (
                /* Welcome Experience */
                <div className="flex h-full flex-col justify-between py-2">
                  <div className="pt-2">
                    <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-[#EEE7FA] text-[#452477]">
                      <Trophy className="h-5 w-5 text-[#452477]" />
                    </div>
                    <h4 className="text-base font-black tracking-tight text-[#19171D]">
                      {isArabic ? "قرارات الفانتازي تبدأ من هنا." : "Your next FPL decision starts here."}
                    </h4>
                    <p className="mt-1 text-xs text-[#6F6A76] font-medium leading-relaxed">
                      {isArabic
                        ? "تحليلات دقيقة للاعبين، نصائح الانتقالات، خيارات الكابتنة، وتقييم شامل للتشكيلة."
                        : "Get player insights, transfer advice, captain picks, and squad analysis."}
                    </p>
                  </div>

                  {/* 3 Compact Action Cards */}
                  <div className="my-auto space-y-2 py-4">
                    <p className="text-[11px] font-bold uppercase tracking-wider text-[#6F6A76]">
                      {isArabic ? "ابدأ بسؤال سريع" : "Suggested questions"}
                    </p>
                    {suggestionCards.map((card, idx) => {
                      const Icon = card.icon;
                      return (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => handleSend(card.prompt)}
                          className="group flex w-full items-center justify-between rounded-xl border border-[#E8E3ED] bg-white p-3 text-left transition-all hover:border-[#7041C5] hover:bg-[#EEE7FA]/30 hover:shadow-xs focus:outline-none focus:ring-2 focus:ring-[#7041C5]/20 cursor-pointer"
                        >
                          <div className="flex items-center gap-3">
                            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#EEE7FA] text-[#452477] transition-colors group-hover:bg-[#D4C3ED]">
                              <Icon className="h-4 w-4" />
                            </div>
                            <div>
                              <div className="text-xs font-bold text-[#19171D] group-hover:text-[#452477]">
                                {card.title}
                              </div>
                              <div className="text-[11px] text-[#6F6A76]">
                                {card.desc}
                              </div>
                            </div>
                          </div>
                          <ChevronRight className="h-4 w-4 text-[#6F6A76] transition-transform group-hover:translate-x-0.5 group-hover:text-[#7041C5]" />
                        </button>
                      );
                    })}
                  </div>

                  <div className="rounded-lg bg-[#FDF8EC] border border-[#E5D08E] p-2.5 text-[11px] text-[#8C680E] font-medium">
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
                      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#EEE7FA] text-[#452477]">
                        <Shield className="h-3.5 w-3.5" />
                      </div>
                      <div className="flex items-center gap-2 rounded-2xl rounded-tl-sm border border-[#E8E3ED] bg-white px-3.5 py-2.5 shadow-xs">
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-[#7041C5]" />
                        <span className="text-xs font-medium text-[#6F6A76]">
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
                        className="inline-flex items-center gap-1.5 rounded-lg border border-[#E8E3ED] bg-white px-2.5 py-1 text-xs font-bold text-[#6F6A76] hover:bg-[#F8F7FA] hover:text-[#19171D] transition-colors"
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
              <div className="flex items-center gap-2 border-t border-[#E5D08E] bg-[#FDF8EC] px-4 py-1.5">
                <AlertTriangle className="h-3 w-3 shrink-0 text-[#8C680E]" />
                <p className="text-[10px] text-[#8C680E] font-medium">
                  Using local predictive models & verified FPL data.
                </p>
              </div>
            )}

            {/* Chat Composer */}
            <footer className="border-t border-[#E8E3ED] bg-white p-3">
              <div className="relative flex items-end rounded-xl border border-[#E8E3ED] bg-[#F8F7FA] transition-all focus-within:border-[#7041C5] focus-within:bg-white focus-within:ring-2 focus-within:ring-[#7041C5]/20">
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
                  className="max-h-24 flex-1 resize-none bg-transparent px-3.5 py-2.5 text-xs text-[#19171D] placeholder-[#6F6A76] outline-none disabled:opacity-50"
                  id="chat-input"
                />
                <button
                  onClick={() => handleSend()}
                  disabled={!input.trim() || isLoading}
                  className="m-1.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#7041C5] text-white transition-all hover:bg-[#5D32A8] disabled:cursor-not-allowed disabled:opacity-30 cursor-pointer"
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
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-xs font-black ${
          isUser
            ? "bg-[#452477] text-white"
            : "bg-[#EEE7FA] text-[#452477]"
        }`}
      >
        {isUser ? "You" : <Shield className="h-3.5 w-3.5" />}
      </div>

      <div
        className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed ${
          isUser
            ? "rounded-tr-xs bg-[#452477] text-white font-normal shadow-xs"
            : "rounded-tl-xs border border-[#E8E3ED] bg-white text-[#19171D] shadow-xs"
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
              className="mt-2.5 mb-1 flex items-center gap-1.5 border-b border-[#E8E3ED] pb-1 text-xs font-black text-[#452477]"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-[#7041C5]" />
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
              className="my-1.5 rounded-xl border border-[#E5D08E] bg-[#FDF8EC] p-2 text-xs font-semibold text-[#8C680E]"
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
              className="my-1.5 rounded-xl border border-[#E5D08E] bg-[#FDF8EC] p-2 text-[11px] text-[#8C680E] font-medium"
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
              <span className="font-black text-[#7041C5] shrink-0">•</span>
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
              className="mt-1.5 border-t border-[#E8E3ED] pt-1 text-[10px] italic text-[#6F6A76]"
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
