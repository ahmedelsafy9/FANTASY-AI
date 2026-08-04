import { CalendarX } from "lucide-react";

/**
 * The backend (see the API's router files) exposes no fixtures endpoint —
 * there is no `/fixtures` route, and no fixture list, kickoff time, or
 * fixture-difficulty rating in any response schema. Rather than fabricate
 * fixture data, this section is honestly built as a "not yet available"
 * state, ready to be swapped for real fixture cards the moment the backend
 * adds that endpoint — no redesign required.
 */
export function FixtureIntelligence() {
  return (
    <section className="mx-auto max-w-7xl px-5 py-14 lg:px-8">
      <div className="mb-8">
        <h2 className="text-2xl font-semibold text-ink sm:text-3xl">Fixture Intelligence</h2>
        <p className="mt-1.5 max-w-xl text-sm text-ink-tertiary">
          Upcoming fixtures, home/away context, and difficulty ratings.
        </p>
      </div>

      <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border-medium bg-surface/50 px-6 py-16 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white/5 text-ink-tertiary">
          <CalendarX size={20} />
        </div>
        <p className="font-medium text-ink">Fixture data isn't available yet</p>
        <p className="max-w-sm text-sm text-ink-tertiary">
          The current backend doesn't expose an upcoming-fixtures endpoint, so
          this section can't show real matchups yet. It's built and ready to
          populate the moment that data is available — no redesign needed.
        </p>
      </div>
    </section>
  );
}
