import { useEffect, useRef } from "react";
import { Search, X } from "lucide-react";

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  autoFocusShortcut?: boolean;
}

/** A premium search field. Supports "/" to focus, matching common app conventions. */
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
        className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-tertiary transition-colors group-focus-within:text-gold"
      />
      <input
        ref={ref}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label="Search players"
        className="w-full rounded-xl border border-border-soft bg-surface py-2.5 pl-10 pr-16 text-sm text-ink placeholder:text-ink-tertiary transition-colors focus:border-emerald/50 focus:outline-none"
      />
      {value ? (
        <button
          onClick={() => onChange("")}
          aria-label="Clear search"
          className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-tertiary hover:text-ink"
        >
          <X size={15} />
        </button>
      ) : (
        autoFocusShortcut && (
          <kbd className="absolute right-3 top-1/2 -translate-y-1/2 rounded border border-border-soft px-1.5 py-0.5 font-mono text-[10px] text-ink-tertiary">
            /
          </kbd>
        )
      )}
    </div>
  );
}
