import { FixtureIntelligence } from "@/sections/FixtureIntelligence";

export default function Fixtures() {
  return (
    <div className="pb-24 pt-10">
      <div className="mx-auto max-w-7xl px-5 lg:px-8">
        <h1 className="text-3xl font-semibold text-ink">Fixtures</h1>
        <p className="mt-1.5 text-sm text-ink-tertiary">
          Upcoming matchups and fixture difficulty.
        </p>
      </div>
      <FixtureIntelligence />
    </div>
  );
}
