import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MessageSquare, X, Send, Loader2, Bot, User, Sparkles, AlertTriangle } from "lucide-react";
import { sendChatMessage, getChatbotStatus } from "@/api/endpoints";
import type { ChatMessage, ChatStatusResponse } from "@/types/api";

const SUGGESTIONS = [
  { label: "🏆 Captain pick", message: "Who should I captain this gameweek?" },
  { label: "🔥 Top players", message: "Who are the top predicted players this week?" },
  { label: "🤕 Injuries", message: "Which key players are injured or doubtful?" },
  { label: "💎 Differentials", message: "Give me some good differential picks" },
  { label: "⚽ Best mids", message: "Who are the best midfielders to pick this week?" },
  { label: "🛡️ Best defs", message: "Who are the best defenders to pick this week?" },
];

const SUGGESTIONS_AR = [
  { label: "🏆 كابتن", message: "مين أكابتن الجولة دي؟" },
  { label: "🔥 أفضل لاعبين", message: "مين أفضل اللاعبين المتوقعين الأسبوع ده؟" },
  { label: "🤕 إصابات", message: "مين اللاعبين المصابين أو المشكوك في مشاركتهم؟" },
  { label: "💎 Differentials", message: "اقترح عليا differential picks كويسة" },
];

export default function ChatWidget() {
  const [showArabicSuggestions, setShowArabicSuggestions] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<ChatStatusResponse | null>(null);
  const [statusChecked, setStatusChecked] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Check chatbot status on mount
  useEffect(() => {
    getChatbotStatus()
      .then((s) => { setStatus(s); setStatusChecked(true); })
      .catch(() => setStatusChecked(true));
  }, []);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [isOpen]);

  const handleSend = useCallback(async (messageText?: string) => {
    const text = (messageText || input).trim();
    if (!text || isLoading) return;

    const userMsg: ChatMessage = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await sendChatMessage(text, messages);
      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: response.response,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const errorMsg: ChatMessage = {
        role: "assistant",
        content: "Sorry, I couldn't process that request. Please try again.",
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, messages]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Don't show widget if chatbot is disabled
  if (statusChecked && status && !status.enabled) return null;

  return (
    <>
      {/* Floating toggle button */}
      <AnimatePresence>
        {!isOpen && (
          <motion.button
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setIsOpen(true)}
            className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-emerald-700 text-white shadow-lg shadow-emerald-500/30 transition-shadow hover:shadow-xl hover:shadow-emerald-500/40"
            aria-label="Open Fantasy AI Assistant"
            id="chat-toggle-btn"
          >
            <MessageSquare className="h-6 w-6" />
            <span className="absolute -top-1 -right-1 flex h-4 w-4">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-300 opacity-75" />
              <span className="relative inline-flex h-4 w-4 rounded-full bg-emerald-400" />
            </span>
          </motion.button>
        )}
      </AnimatePresence>

      {/* Chat panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
            className="fixed bottom-4 right-4 z-50 flex h-[600px] w-[420px] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl md:bottom-6 md:right-6"
            id="chat-panel"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-slate-100 bg-gradient-to-r from-emerald-600 to-emerald-700 px-5 py-4">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/20 backdrop-blur-sm">
                  <Bot className="h-5 w-5 text-white" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white">Fantasy AI Assistant</h3>
                  <p className="text-xs text-emerald-100">
                    {status?.configured ? "AI-powered analysis" : "Data-powered insights"}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-white/80 transition-colors hover:bg-white/20 hover:text-white"
                aria-label="Close chat"
                id="chat-close-btn"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Messages area */}
            <div className="flex-1 overflow-y-auto px-4 py-4" id="chat-messages">
              {messages.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center">
                  <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-50">
                    <Sparkles className="h-8 w-8 text-emerald-500" />
                  </div>
                  <h4 className="mb-1 text-base font-semibold text-slate-800">
                    Fantasy AI Assistant
                  </h4>
                  <p className="mb-6 max-w-[280px] text-center text-xs text-slate-500">
                    Ask me about player predictions, captain picks, injuries,
                    differentials, or any FPL question.
                  </p>
                  {/* Language toggle for suggestions */}
                  <div className="mb-3 flex items-center gap-1.5 rounded-lg bg-slate-100 p-0.5 text-[11px]">
                    <button
                      type="button"
                      onClick={() => setShowArabicSuggestions(false)}
                      className={`rounded-md px-2.5 py-0.5 font-medium transition-all ${
                        !showArabicSuggestions
                          ? "bg-white text-emerald-700 shadow-xs"
                          : "text-slate-500 hover:text-slate-700"
                      }`}
                    >
                      English
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowArabicSuggestions(true)}
                      className={`rounded-md px-2.5 py-0.5 font-medium transition-all ${
                        showArabicSuggestions
                          ? "bg-white text-emerald-700 shadow-xs"
                          : "text-slate-500 hover:text-slate-700"
                      }`}
                    >
                      العربية
                    </button>
                  </div>
                  {/* Suggestion chips */}
                  <div className="flex flex-wrap justify-center gap-2 px-2">
                    {(showArabicSuggestions ? SUGGESTIONS_AR : SUGGESTIONS).map((s) => (
                      <button
                        key={s.message}
                        onClick={() => handleSend(s.message)}
                        className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm transition-all hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-700 hover:shadow"
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  {messages.map((msg, i) => (
                    <ChatBubble key={i} message={msg} />
                  ))}
                  {isLoading && (
                    <div className="flex items-start gap-2.5">
                      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-emerald-100">
                        <Bot className="h-4 w-4 text-emerald-600" />
                      </div>
                      <div className="rounded-2xl rounded-tl-md bg-slate-100 px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          <Loader2 className="h-3.5 w-3.5 animate-spin text-emerald-600" />
                          <span className="text-xs text-slate-500">Analyzing...</span>
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            {/* Not-configured warning */}
            {statusChecked && status && !status.configured && (
              <div className="flex items-center gap-2 border-t border-amber-100 bg-amber-50 px-4 py-2">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-600" />
                <p className="text-[10px] text-amber-700">
                  AI mode requires an API key. Using data-only mode.
                </p>
              </div>
            )}

            {/* Input area */}
            <div className="border-t border-slate-100 bg-white px-4 py-3">
              <div className="flex items-center gap-2">
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask about players, predictions, injuries..."
                  disabled={isLoading}
                  className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-800 placeholder-slate-400 outline-none transition-colors focus:border-emerald-400 focus:bg-white focus:ring-2 focus:ring-emerald-100 disabled:opacity-50"
                  id="chat-input"
                />
                <button
                  onClick={() => handleSend()}
                  disabled={!input.trim() || isLoading}
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-600 text-white shadow-sm transition-all hover:bg-emerald-700 hover:shadow disabled:cursor-not-allowed disabled:opacity-40"
                  aria-label="Send message"
                  id="chat-send-btn"
                >
                  {isLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

// ---------------------------------------------------------------
// Chat bubble component
// ---------------------------------------------------------------

function ChatBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex items-start gap-2.5 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${
          isUser ? "bg-slate-700" : "bg-emerald-100"
        }`}
      >
        {isUser ? (
          <User className="h-4 w-4 text-white" />
        ) : (
          <Bot className="h-4 w-4 text-emerald-600" />
        )}
      </div>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
          isUser
            ? "rounded-tr-md bg-emerald-600 text-white"
            : "rounded-tl-md bg-slate-100 text-slate-800"
        }`}
      >
        <FormattedMessage text={message.content} isUser={isUser} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------
// Simple markdown-like formatter for assistant messages
// ---------------------------------------------------------------

function FormattedMessage({ text, isUser }: { text: string; isUser: boolean }) {
  if (isUser) return <>{text}</>;

  // Basic formatting: **bold**, split by newlines
  const lines = text.split("\n");
  return (
    <div className="space-y-1.5">
      {lines.map((line, i) => {
        if (!line.trim()) return <div key={i} className="h-1" />;

        // Bold text
        const formatted = line.split(/(\*\*.*?\*\*)/).map((part, j) => {
          if (part.startsWith("**") && part.endsWith("**")) {
            return (
              <strong key={j} className="font-semibold">
                {part.slice(2, -2)}
              </strong>
            );
          }
          return part;
        });

        // Bullet points
        if (line.trim().startsWith("- ") || line.trim().startsWith("• ")) {
          return (
            <div key={i} className="flex gap-1.5 pl-1">
              <span className="text-emerald-500">•</span>
              <span>{formatted}</span>
            </div>
          );
        }

        return <p key={i}>{formatted}</p>;
      })}
    </div>
  );
}
