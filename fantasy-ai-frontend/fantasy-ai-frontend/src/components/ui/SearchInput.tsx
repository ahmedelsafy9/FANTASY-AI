import { useEffect, useRef } from "react";
import { Search, X } from "lucide-react";

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  autoFocusShortcut?: boolean;
}

export function SearchInput({
  value,
  onChange,
  placeholder = "Search players, teams, positions…",
  autoFocusShortcut = true,
}: SearchInputProps) {
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!autoFocusShortcut) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "/" && document.activeElement !== ref.current) {
        e.preventDefault();
        ref.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [autoFocusShortcut]);

  return (
    <div className="group relative">
      <Search
        size={16}
        className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[#64748B] transition-colors group-focus-within:text-[#10B981]"
      />
      <input
        ref={ref}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label="Search players"
        className="w-full rounded-xl border-2 border-[#CBD5E1] bg-white py-2.5 pl-10 pr-16 text-sm font-black text-[#0F172A] placeholder:text-[#94A3B8] shadow-sm transition-all focus:border-[#10B981] focus:outline-none focus:ring-2 focus:ring-[#10B981]/20"
      />
      {value ? (
        <button
          onClick={() => onChange("")}
          aria-label="Clear search"
          className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg p-1 text-[#64748B] hover:bg-[#F1F5F9] hover:text-[#0F172A] transition-colors cursor-pointer"
        >
          <X size={15} />
        </button>
      ) : (
        autoFocusShortcut && (
          <kbd className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md border border-[#CBD5E1] bg-[#F8FAFC] px-1.5 py-0.5 font-mono text-[10px] font-black text-[#475569] shadow-sm">
            /
          </kbd>
        )
      )}
    </div>
  );
}
