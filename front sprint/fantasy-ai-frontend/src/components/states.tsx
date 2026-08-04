import type { ReactNode } from "react";
import { AlertTriangle, Inbox, RotateCcw } from "lucide-react";
import { Button, Skeleton } from "@/components/ui/primitives";

/* -------------------------------------------------------------------------- */
/* Error state                                                                 */
/* -------------------------------------------------------------------------- */

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-border-soft bg-surface px-6 py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-coral/10 text-coral">
        <AlertTriangle size={22} />
      </div>
      <div>
        <p className="font-medium text-ink">Fantasy-AI couldn't reach the prediction engine.</p>
        {message && <p className="mt-1 max-w-sm text-sm text-ink-tertiary">{message}</p>}
      </div>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          <RotateCcw size={14} /> Try again
        </Button>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Empty state                                                                 */
/* -------------------------------------------------------------------------- */

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: ReactNode;
}

export function EmptyState({ title, description, icon }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border-medium px-6 py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white/5 text-ink-tertiary">
        {icon ?? <Inbox size={20} />}
      </div>
      <p className="font-medium text-ink">{title}</p>
      {description && <p className="max-w-sm text-sm text-ink-tertiary">{description}</p>}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Skeletons                                                                   */
/* -------------------------------------------------------------------------- */

export function PlayerCardSkeleton() {
  return (
    <div className="flex flex-col overflow-hidden rounded-2xl border border-border-soft bg-surface">
      <div className="flex items-center gap-3 border-b border-border-soft p-5">
        <Skeleton className="h-11 w-11 rounded-full" />
        <div className="flex flex-col gap-2">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-3 w-16" />
        </div>
      </div>
      <div className="flex items-center justify-between p-5">
        <Skeleton className="h-10 w-20" />
        <Skeleton className="h-6 w-16 rounded-full" />
      </div>
      <div className="grid grid-cols-3 gap-2 border-t border-border-soft p-5">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
      </div>
    </div>
  );
}

export function RankRowSkeleton() {
  return (
    <div className="flex items-center gap-4 rounded-xl border border-border-soft bg-surface px-4 py-3">
      <Skeleton className="h-8 w-8 rounded-md" />
      <Skeleton className="h-9 w-9 rounded-full" />
      <div className="flex-1">
        <Skeleton className="h-4 w-32" />
      </div>
      <Skeleton className="h-6 w-10" />
    </div>
  );
}

export function ChartSkeleton() {
  return (
    <div className="rounded-2xl border border-border-soft bg-surface p-5">
      <Skeleton className="mb-4 h-4 w-32" />
      <Skeleton className="h-48 w-full" />
    </div>
  );
}

export function PlayerProfileSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-4">
        <Skeleton className="h-16 w-16 rounded-full" />
        <div className="flex flex-col gap-2">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-4 w-24" />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full rounded-xl" />
        ))}
      </div>
      <ChartSkeleton />
    </div>
  );
}
