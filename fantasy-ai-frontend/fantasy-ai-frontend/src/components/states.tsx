import { AlertTriangle, Inbox } from "lucide-react";
import { Button, Skeleton } from "@/components/ui/primitives";

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-chunky-lg border-2 border-red-200 bg-red-50 px-6 py-12 text-center shadow-soft">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-[#DC2626] shadow-sm">
        <AlertTriangle size={22} />
      </div>
      <p className="max-w-sm text-sm font-bold text-[#0F172A]">{message}</p>
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
    <div className="flex flex-col items-center justify-center gap-3 rounded-chunky-lg border-2 border-dashed border-[#CBD5E1] bg-white px-6 py-12 text-center shadow-soft">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#F1F5F9] text-[#64748B]">
        <Inbox size={22} />
      </div>
      <p className="font-bold text-[#0F172A]">{title}</p>
      {description && (
        <p className="max-w-sm text-sm font-medium text-[#64748B]">{description}</p>
      )}
    </div>
  );
}

export function PlayerCardSkeleton() {
  return (
    <div className="flex flex-col overflow-hidden rounded-chunky-lg border border-[#E2E8F0] bg-white shadow-card">
      <div className="h-1 w-full bg-gradient-to-r from-[#10B981] via-[#84CC16] to-[#F59E0B]" />
      <div className="flex items-start gap-3 p-4 pb-3">
        <Skeleton className="h-6 w-6 rounded-full" />
        <Skeleton className="h-16 w-16 rounded-full" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-32 rounded-md" />
          <div className="flex gap-2">
            <Skeleton className="h-6 w-6 rounded-md" />
            <Skeleton className="h-4 w-10 rounded-md" />
          </div>
        </div>
        <div className="space-y-1 text-right">
          <Skeleton className="ml-auto h-2 w-6 rounded-md" />
          <Skeleton className="ml-auto h-8 w-12 rounded-lg" />
        </div>
      </div>
      <div className="border-t border-[#E2E8F0] px-4 py-2.5">
        <Skeleton className="h-8 w-36 rounded-lg" />
      </div>
      <div className="grid grid-cols-3 gap-px border-t border-[#E2E8F0] bg-[#E2E8F0]">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="bg-white px-3 py-2.5 space-y-1.5">
            <Skeleton className="h-2 w-10 rounded-md" />
            <Skeleton className="h-4 w-12 rounded-md" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function RankRowSkeleton() {
  return (
    <div className="flex items-center gap-3 rounded-chunky-lg border border-[#E2E8F0] bg-white px-4 py-3 shadow-soft">
      <Skeleton className="h-7 w-7 rounded-full" />
      <Skeleton className="h-11 w-11 rounded-full" />
      <div className="flex-1 space-y-1.5">
        <Skeleton className="h-4 w-28 rounded-md" />
        <Skeleton className="h-3 w-20 rounded-md" />
      </div>
      <Skeleton className="h-6 w-10 rounded-lg" />
    </div>
  );
}

export function PlayerProfileSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-4 rounded-chunky-lg bg-white p-5 shadow-card">
        <Skeleton className="h-24 w-24 rounded-full" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-6 w-40 rounded-md" />
          <Skeleton className="h-4 w-28 rounded-md" />
        </div>
      </div>
      <div className="rounded-chunky-lg border border-[#E2E8F0] bg-white p-5 shadow-card">
        <Skeleton className="h-3 w-20 mb-2 rounded-md" />
        <Skeleton className="h-12 w-24 rounded-lg" />
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="rounded-xl border border-[#E2E8F0] bg-white p-3 space-y-1.5 shadow-soft">
            <Skeleton className="h-2 w-14 rounded-md" />
            <Skeleton className="h-4 w-10 rounded-md" />
          </div>
        ))}
      </div>
      <div className="rounded-chunky-lg border border-[#E2E8F0] bg-white p-5 shadow-card">
        <Skeleton className="h-3 w-28 mb-3 rounded-md" />
        <Skeleton className="h-40 w-full rounded-xl" />
      </div>
    </div>
  );
}
