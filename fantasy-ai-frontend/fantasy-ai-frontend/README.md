# Fantasy-AI — Frontend

The user-facing interface for Fantasy-AI: a premium, dark-first React
application that consumes the real Fantasy-AI FastAPI backend (built in
Sprints 1–9) and presents its predictions honestly — no invented players,
fixtures, or stats.

## Tech stack

React 18 · Vite · TypeScript (strict) · Tailwind CSS · Framer Motion ·
Lucide React · Axios · Recharts · React Router

## Setup

```bash
cd fantasy-ai-frontend
npm install
cp .env.example .env
npm run dev
```

Frontend: **http://localhost:5173**
Backend must be running at the URL in `.env` (default **http://localhost:8000**).

## Running the backend

From the backend repo:

```bash
pip install -r requirements.txt
uvicorn src.api.main:app --reload
```

The backend needs its data pipeline already run at least once
(`scripts.run_historical_ingestion`, `run_preprocessing`,
`run_feature_engineering`, `run_training`) or its data-dependent
endpoints return `503` — the frontend renders this as a clear error
state with a retry button, not a crash or fake data.

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_URL` | Base URL of the FastAPI backend | `http://localhost:8000` |
| `VITE_USE_MOCKS` | `true` to develop against bundled mock data instead of a live backend | unset (off) |

Mock mode is clearly banner'd in the UI whenever active (see
`src/components/MockBanner.tsx`) and is never used as a silent fallback —
a real request failure always shows an error state, never fake data.

## API endpoints consumed

Every one maps 1:1 to a real backend route (see `src/api/endpoints.ts`):

| Frontend call | Backend route |
|---|---|
| `getHealth()` | `GET /` |
| `getPlayer(id)` | `GET /player/{player_id}` |
| `getPredictions(id?)` | `GET /predict` (optional `?player_id=`) |
| `getTopPlayers(limit)` | `GET /top_players?limit=` |
| `getCaptain()` | `GET /captain` |

No endpoint is invented. There is currently no backend route for a
dedicated player list or fixtures — the **Players** page is built from
`/predict`'s full player set (it already returns every tracked player),
and the **Fixtures** page/section honestly shows a "not available yet"
state (see `src/sections/FixtureIntelligence.tsx`) rather than fabricate
matchups.

## Project structure

```
src/
├── api/            client.ts (axios instance), endpoints.ts (typed calls), mocks.ts (opt-in dev mocks)
├── types/          api.ts — types mirroring the real backend response shapes
├── lib/            format.ts, insights.ts (honest, field-derived AI insight tags), utils.ts
├── hooks/          useAsync.ts, useApi.ts — typed data-fetching hooks
├── components/
│   ├── ui/         primitives.tsx (Button/Badge/Card/Skeleton/Tooltip), overlays.tsx (Modal/Drawer/Tabs/Dropdown), SearchInput.tsx
│   ├── charts/      RollingWindowChart.tsx
│   ├── identity.tsx      PlayerAvatar, TeamBadge
│   ├── stats.tsx          Stat, ConfidenceBar (signature data-readout style)
│   ├── PlayerCard.tsx, PredictionRank.tsx, PlayerDetailPanel.tsx
│   ├── GameweekBadge.tsx, Navigation.tsx, Footer.tsx, MockBanner.tsx
│   └── states.tsx   ErrorState, EmptyState, and matching skeleton loaders
├── sections/        Hero, GameweekOverview, TopPredictions, FixtureIntelligence, PlayerSpotlight, AIInsights, HowItWorks
└── pages/           Home, Dashboard, Predictions, Players, PlayerDetails, Fixtures, About
```

## Known limitations (see the in-app About page for the full, honest writeup)

- **Next-Gameweek prediction is a proxy.** The backend predicts using each
  player's most recently played match, not true upcoming-fixture data
  (real opponent, home/away for that specific match, injury news). This
  is a backend limitation, documented in both the backend's own README
  and this frontend's About page — not hidden.
- **No fixtures endpoint exists yet.** The Fixtures page/section is
  honestly built as a "not available" state.
- **No player photos or team crests** are provided by the backend —
  `PlayerAvatar`/`TeamBadge` render deterministic initials/color marks
  from the real name/team string instead of fabricating images.
- **No explicit "confidence" score** exists in the backend. Where the UI
  shows a confidence-style bar, it's clearly derived from real recent-
  minutes data (see `derivePlayingTimeReliability` in `lib/insights.ts`)
  and labeled honestly, not presented as a raw model output.

## Build-verification note (please read)

This frontend was built in a sandboxed environment with **no internet
access** — `npm install` could not be run there (confirmed: registry
requests returned `403`), so **`vite`, `tsc`, and `eslint` were never
actually executed against this code**. In lieu of that, the following
were done and can be independently reproduced:

- A custom static checker resolved all 107 internal `import` statements
  across all 40 source files and confirmed every named/default import
  matches a real export in its target file.
- Every file was checked for balanced brackets/braces/parens.
- A `React.ReactNode` type error (missing import) was caught this way
  and fixed in `App.tsx` and `components/states.tsx`.

None of this replaces a real `npm install && npm run build` (which runs
`tsc -b`). **Please run that once in your own environment before
treating this as verified** — it is very likely correct, but "very
likely" is not the same as "confirmed by a compiler," and that
distinction matters.
