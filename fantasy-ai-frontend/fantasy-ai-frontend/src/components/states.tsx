import { AlertTriangle, Inbox } from "lucide-react";
import { Button, Skeleton } from "@/components/ui/primitives";

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-coral/20 bg-coral/[0.04] px-6 py-12 text-center">
      <div className="flex h-11 w-11 items-center justify-center rounded-full bg-coral/10 text-coral">
        <AlertTriangle size={20} />
      </div>
      <p className="max-w-sm text-sm font-medium text-ink">{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

interface EmptyStateProps {
  title: string;
  description?: string;
}

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border-medium bg-surface/50 px-6 py-12 text-center">
      <div className="flex h-11 w-11 items-center justify-center rounded-full bg-white/5 text-ink-tertiary">
        <Inbox size={20} />
      </div>
      <p className="font-medium text-ink">{title}</p>
      {description && (
        <p className="max-w-sm text-sm text-ink-tertiary">{description}</p>
      )}
    </div>
  );
}

/** Skeleton for the redesigned PlayerCard */
export function PlayerCardSkeleton() {
  return (
    <div className="flex flex-col overflow-hidden rounded-xl border border-border-soft bg-surface shadow-card">
      {/* Accent stripe */}
      <div className="h-0.5 w-full bg-gradient-to-r from-white/5 via-white/3 to-transparent" />
      {/* Header */}
      <div className="flex items-start gap-3 p-4 pb-3">
        <Skeleton className="h-6 w-6 rounded-md" />
        <Skeleton className="h-16 w-16 rounded-full" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-32" />
          <div className="flex gap-2">
            <Skeleton className="h-6 w-6 rounded-md" />
            <Skeleton className="h-4 w-10 rounded" />
          </div>
        </div>
        <div className="space-y-1 text-right">
          <Skeleton className="ml-auto h-2 w-6" />
          <Skeleton className="ml-auto h-8 w-12" />
        </div>
      </div>
      {/* Fixture row */}
      <div className="border-t border-border-soft px-4 py-2.5">
        <Skeleton className="h-8 w-36 rounded-lg" />
      </div>
      {/* Stats footer */}
      <div className="grid grid-cols-3 gap-px border-t border-border-soft bg-border-soft">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="bg-surface px-3 py-2.5 space-y-1.5">
            <Skeleton className="h-2 w-10" />
            <Skeleton className="h-4 w-12" />
          </div>
        ))}
      </div>
    </div>
  );
}

/** Skeleton for the PredictionRank rows */
export function RankRowSkeleton() {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-border-soft bg-surface px-4 py-3">
      <Skeleton className="h-7 w-7 rounded-lg" />
      <Skeleton className="h-11 w-11 rounded-full" />
      <div className="flex-1 space-y-1.5">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-3 w-20" />
      </div>
      <Skeleton className="h-6 w-10" />
    </div>
  );
}

/** Skeleton for a full player profile page */
export function PlayerProfileSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      {/* Hero */}
      <div className="flex items-center gap-4 rounded-xl bg-surface p-5">
        <Skeleton className="h-24 w-24 rounded-full" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-28" />
        </div>
      </div>
      {/* Points */}
      <div className="rounded-xl border border-border-soft bg-surface p-5">
        <Skeleton className="h-3 w-20 mb-2" />
        <Skeleton className="h-12 w-24" />
      </div>
      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="rounded-lg border border-border-soft bg-surface p-3 space-y-1.5">
            <Skeleton className="h-2 w-14" />
            <Skeleton className="h-4 w-10" />
          </div>
        ))}
      </div>
      {/* Chart */}
      <div className="rounded-xl border border-border-soft bg-surface p-5">
        <Skeleton className="h-3 w-28 mb-3" />
        <Skeleton className="h-40 w-full rounded-lg" />
      </div>
    </div>
  );
}
