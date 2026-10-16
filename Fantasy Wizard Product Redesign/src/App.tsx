import { useEffect, useRef, useState } from "react"
import { type Player, type Match } from "./data"
import { padGameweek } from "./api/adapters"
import { isMockMode } from "./api/config"
import { useWizardData } from "./hooks/useWizardData"

const pages = [
  "Home",
  "Player Predictions",
  "Match Predictions",
  "Squad Builder",
  "Captain Picks",
  "AI Assistant",
]
function Mark({ small = false }: { small?: boolean }) {
  return (
    <svg
      className={small ? "mark small" : "mark"}
      viewBox="0 0 48 48"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M24 3 42 13v21L24 45 6 34V13Z"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="m24 12 10 7-4 12H18l-4-12 10-7Zm0 0V3M14 19l-8-6m12 18L6 34m24-3 12 3M34 19l8-6M24 31v14"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="m36 1 2.5 6.5L45 10l-6.5 2.5L36 19l-2.5-6.5L27 10l6.5-2.5Z"
        fill="currentColor"
        stroke="var(--green)"
        strokeWidth="2"
      />
    </svg>
  )
}
function Arrow() {
  return <span aria-hidden="true">↗</span>
}
function Status({ value }: { value: string }) {
  return (
    <span className={`status ${value.toLowerCase()}`}>
      <span aria-hidden="true">●</span> {value}
    </span>
  )
}
function Points({ player }: { player: Player }) {
  return (
    <div className="points">
      <strong>{player.points == null ? "—" : Math.round(player.points)}</strong>
      <span>
        Predicted
        <br />
        points
      </span>
    </div>
  )
}
function Portrait({
  player,
  className = "",
}: {
  player: Player
  className?: string
}) {
  return (
    <img
      className={`portrait ${className}`}
      src={player.photo}
      alt={player.name}
      onError={(e) => {
        e.currentTarget.style.visibility = "hidden"
      }}
    />
  )
}
function PlayerCard({
  player,
  onClick,
  selected = false,
}: {
  player: Player
  onClick: () => void
  selected?: boolean
}) {
  return (
    <button
      className={`player-card ${selected ? "selected" : ""}`}
      onClick={onClick}
    >
      <div className="player-visual">
        <span className="position">{player.position}</span>
        <Status value={player.status} />
        <div className="jersey-number">
          {String(player.id).padStart(2, "0")}
        </div>
        <Portrait player={player} />
        <Points player={player} />
      </div>
      <div className="player-info">
        <span className="muted small-text">{player.club}</span>
        <h3>{player.name}</h3>
        <div className="player-bottom">
          <span>
            Next · <b>{player.fixture}</b>
          </span>
          <span className="circle-arrow">↗</span>
        </div>
      </div>
    </button>
  )
}
function Probability({ match }: { match: Match }) {
  return (
    <div className="probabilities">
      <div className="prob-labels">
        {["Home win", "Draw", "Away win"].map((label, i) => (
          <div key={label}>
            <span>{label}</span>
            <strong>
              {match.probabilities[i]}
              <small>%</small>
            </strong>
          </div>
        ))}
      </div>
      <div
        className="prob-bar"
        aria-label={`Home ${match.probabilities[0]}%, draw ${match.probabilities[1]}%, away ${match.probabilities[2]}%`}
      >
        {match.probabilities.map((p, i) => (
          <span key={i} style={{ flex: p }} />
        ))}
      </div>
    </div>
  )
}
function Teams({ match }: { match: Match }) {
  const homeCrest =
    match.homeCrest ||
    `https://resources.premierleague.com/premierleague/badges/70/t${match.crests[0]}.png`
  const awayCrest =
    match.awayCrest ||
    `https://resources.premierleague.com/premierleague/badges/70/t${match.crests[1]}.png`
  return (
    <div className="teams">
      <div>
        <img
          src={homeCrest}
          alt=""
        />
        <h3>{match.home}</h3>
        <small>HOME</small>
      </div>
      <span className="versus">vs</span>
      <div>
        <img
          src={awayCrest}
          alt=""
        />
        <h3>{match.away}</h3>
        <small>AWAY</small>
      </div>
    </div>
  )
}
function App() {
  const wizard = useWizardData()
  const players = wizard.players
  const matches = wizard.matches
  const scenario = wizard.scenario
  const [page, setPage] = useState(() =>
    pages.includes(decodeURIComponent(location.hash.slice(1)))
      ? decodeURIComponent(location.hash.slice(1))
      : "Home",
  )
  const [mobile, setMobile] = useState(false),
    [detail, setDetail] = useState<Player | null>(null),
    [query, setQuery] = useState(""),
    [position, setPosition] = useState("All positions"),
    [club, setClub] = useState("All clubs"),
    [availability, setAvailability] = useState("All availability"),
    [sort, setSort] = useState("Predicted points"),
    [gw, setGw] = useState(String(scenario.target)),
    [matchIndex, setMatchIndex] = useState(0),
    [captain, setCaptain] = useState(wizard.captainId),
    [squad, setSquad] = useState<number[]>(wizard.squadIds),
    [slot, setSlot] = useState<number | null>(null)
  const [messages, setMessages] = useState<{
      role: string
      text: string
      kind?: string
    }[]>([]),
    [draft, setDraft] = useState(""),
    [loading, setLoading] = useState(false),
    [error, setError] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null),
    end = useRef<HTMLDivElement>(null),
    dialog = useRef<HTMLDialogElement>(null)
  const navigate = (p: string) => {
    setPage(p)
    location.hash = p
    setMobile(false)
    setGw(String(scenario.target))
    window.scrollTo({ top: 0, behavior: "instant" })
  }
  useEffect(() => {
    const change = () => {
      const p = decodeURIComponent(location.hash.slice(1))
      if (pages.includes(p)) setPage(p)
    }
    window.addEventListener("hashchange", change)
    return () => window.removeEventListener("hashchange", change)
  }, [])
  useEffect(() => {
    if (detail) dialog.current?.showModal()
    else dialog.current?.close()
  }, [detail])
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" })
  }, [messages, loading])
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current)
    },
    [],
  )
  const send = (text: string) => {
    if (!text.trim() || loading) return
    setMessages((m) => [...m, { role: "user", text: text.trim() }])
    setDraft("")
    setError(false)
    setLoading(true)
    timer.current = setTimeout(() => {
      setLoading(false)
      if (text.toLowerCase().includes("error")) {
        setError(true)
        return
      }
      const kind = /avail|injur/i.test(text)
        ? "availability"
        : /compar/i.test(text)
          ? "comparison"
          : /budget|transfer|squad/i.test(text)
            ? "transfer"
            : "captain"
      const answer =
        kind === "availability"
          ? "Availability deserves a final check. In this illustrative scenario, Son is doubtful and João Pedro is injured. Unknown status is not the same as available."
          : kind === "comparison"
            ? "Haaland leads our sample projection with 9 points; Salah follows with 8. Both are available in this scenario. Salah costs £2.5m less, while Haaland offers the higher illustrative points ceiling."
            : kind === "transfer"
              ? "A measured move beats a rushed transfer. Eze is a sample midfield option at £6.9m with 5 predicted points and 9.1% ownership. Check your available budget, club limits and availability before making a change."
              : "Haaland is the leading captain candidate in this sample: 9 predicted points, with Newcastle away next. Salah is a close alternative at 8 points. These are projections, not guaranteed returns."
      setMessages((m) => [...m, { role: "assistant", text: answer, kind }])
    }, 1100)
  }
  const filtered = players
    .filter(
      (p) =>
        p.name.toLowerCase().includes(query.toLowerCase()) &&
        (position === "All positions" || p.position === position) &&
        (club === "All clubs" || p.club === club) &&
        (availability === "All availability" || p.status === availability),
    )
    .sort((a, b) =>
      sort === "Price: low to high"
        ? a.price - b.price
        : (b.points ?? -1) - (a.points ?? -1),
    )
  const picked = players.find((p) => p.id === captain)!
  const weekSelect = (
    <label className="week-select">
      <span>Target round</span>
      <select
        aria-label="Target gameweek"
        value={gw}
        onChange={(e) => setGw(e.target.value)}
      >
        <option value="6">Gameweek 6</option>
        <option value="7">Gameweek 7</option>
      </select>
    </label>
  )
  const heading = (eyebrow: string, title: string, description: string) => (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {weekSelect}
    </div>
  )
  const sectionHead = (
    tag: string,
    title: string,
    action?: string,
    destination?: string,
  ) => (
    <div className="section-heading">
      <div>
        <div className="eyebrow">{tag}</div>
        <h2>{title}</h2>
      </div>
      {action && (
        <button className="text-button" onClick={() => navigate(destination!)}>
          {action} <Arrow />
        </button>
      )}
    </div>
  )
  return (
    <>
      <header className="site-header">
        <div className="nav-wrap">
          <button
            className="brand"
            onClick={() => navigate("Home")}
            aria-label="Fantasy Wizard home"
          >
            <Mark />
            <span>
              FANTASY
              <span className="wordmark-bottom">
                WIZARD<span className="brand-dot">.</span>
              </span>
            </span>
          </button>
          <nav className={mobile ? "open" : ""} aria-label="Main navigation">
            {pages.map((p, i) => (
              <button
                key={p}
                className={`${page === p ? "active" : ""} ${
                  i === 5 ? "assistant-nav" : ""
                }`}
                onClick={() => navigate(p)}
                aria-current={page === p ? "page" : undefined}
              >
                {i === 5 && <Mark small />}
                {p}
              </button>
            ))}
          </nav>
          <div className="profile" title="Demo manager">
            JD
          </div>
          <button
            className="menu-toggle"
            onClick={() => setMobile(!mobile)}
            aria-label="Toggle navigation"
            aria-expanded={mobile}
          >
            {mobile ? "✕" : "☰"}
          </button>
        </div>
      </header>
      <div className="scenario-bar">
        <div>
          <span className="scenario-dot" /> THE NEXT MOVE IS YOURS{" "}
          <span className="scenario-divider">/</span>
          <span>
            GW{scenario.completed} completed{" "}
            <span className="inline-arrow">→</span>{" "}
            <b>GW{scenario.target} predictions</b>
          </span>
        </div>
        <span className="demo-tag">
          ILLUSTRATIVE PROTOTYPE · {scenario.season}
        </span>
      </div>
      <main
        key={page}
        className={page === "AI Assistant" ? "assistant-main" : ""}
      >
        {page === "Home" && (
          <>
            <section className="hero">
              <div className="hero-background" />
              <div className="hero-content">
                <div className="eyebrow gold">
                  <span className="short-line" /> YOUR EDGE. EVERY GAMEWEEK.
                </div>
                <h1>
                  Every gameweek.
                  <br />A <em>smarter</em> move.
                </h1>
                <p>
                  Football instinct. Intelligent insight.
                  <br />
                  Make your next FPL decision your best one.
                </p>
                <div className="hero-actions">
                  <button
                    className="button gold-button"
                    onClick={() => navigate("Player Predictions")}
                  >
                    Explore player predictions <Arrow />
                  </button>
                  <button
                    className="button ghost-button"
                    onClick={() => navigate("AI Assistant")}
                  >
                    <Mark small /> Ask the Wizard
                  </button>
                </div>
                <div className="hero-footnote">
                  <span className="tiny-pitch" /> Built for the beautiful game.
                  Designed for your next move.
                </div>
              </div>
              <div className="hero-index">
                <span>THE GAMEWEEK EDIT</span>
                <strong>06</strong>
                <span>INTELLIGENCE, NOT GUESSWORK</span>
              </div>
              <div className="photo-credit">
                STADIUM PHOTOGRAPHY · VIENNA REYES / UNSPLASH
              </div>
            </section>
            <div className="content home-content">
              <div className="editorial-intro">
                <div>
                  <span className="eyebrow">THE GAMEWEEK BRIEFING</span>
                  <h2>
                    A little insight.
                    <br />A real advantage.
                  </h2>
                </div>
                <p>
                  Your next captain. Your next transfer. Your next big call.
                  <br />
                  Start with the picks that matter for Gameweek 6.
                </p>
                <div className="round-stamp">
                  <span>TARGET ROUND</span>
                  <strong>GW 06</strong>
                  <small>Sample predictions</small>
                </div>
              </div>
              <div className="home-feature-grid">
                <section className="featured-player">
                  <div className="feature-text">
                    <div className="eyebrow gold">THE STANDOUT PICK</div>
                    <span className="small-text muted-light">
                      MAN CITY · FORWARD
                    </span>
                    <h2>
                      Erling
                      <br />
                      Haaland<span className="gold">.</span>
                    </h2>
                    <Status value="Available" />
                    <div className="feature-points">
                      <Points player={players[0]} />
                      <span>
                        Next fixture
                        <br />
                        <b>NEW (A)</b>
                      </span>
                    </div>
                    <button
                      className="text-button light"
                      onClick={() => setDetail(players[0])}
                    >
                      Explore player <Arrow />
                    </button>
                  </div>
                  <span className="feature-watermark">09</span>
                  <Portrait player={players[0]} />
                  <span className="feature-caption">
                    A difference-maker. On your side.
                  </span>
                </section>
                <section className="home-match">
                  <div className="card-topline">
                    <span className="eyebrow">FIXTURE IN FOCUS</span>
                    <span className="small-text">GW 06</span>
                  </div>
                  <div className="fixture-time">{matches[0].time}</div>
                  <Teams match={matches[0]} />
                  <Probability match={matches[0]} />
                  <button
                    className="text-button"
                    onClick={() => navigate("Match Predictions")}
                  >
                    Explore match predictions <Arrow />
                  </button>
                </section>
              </div>
              {sectionHead(
                "THE SHORTLIST",
                "Big potential. Better decisions.",
                "All player predictions",
                "Player Predictions",
              )}
              <div className="player-grid home-players">
                {players.slice(1, 5).map((p) => (
                  <PlayerCard
                    key={p.id}
                    player={p}
                    onClick={() => setDetail(p)}
                  />
                ))}
              </div>
              <section className="assistant-invite">
                <div className="invite-symbol">
                  <Mark />
                </div>
                <div>
                  <span className="eyebrow gold">MEET YOUR NEW STRATEGIST</span>
                  <h2>Good questions. Smarter football.</h2>
                  <p>
                    Captain dilemmas, transfer thoughts, and the bigger picture.
                    <br />
                    Think it through with your personal FPL strategist.
                  </p>
                </div>
                <button
                  className="button gold-button"
                  onClick={() => navigate("AI Assistant")}
                >
                  Ask the Wizard <Arrow />
                </button>
              </section>
            </div>
          </>
        )}
        {page === "Player Predictions" && (
          <div className="content">
            {heading(
              "THE PLAYER ROOM",
              "Find your next difference-maker.",
              "Portraits first. Predictions that matter. Explore the sample Gameweek 6 shortlist.",
            )}
            <div className="filters">
              <label className="search-field">
                <span aria-hidden="true">⌕</span>
                <input
                  aria-label="Search players"
                  placeholder="Search for a player..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </label>
              <select
                aria-label="Position"
                value={position}
                onChange={(e) => setPosition(e.target.value)}
              >
                {["All positions", "GK", "DEF", "MID", "FWD"].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
              <select
                aria-label="Club"
                value={club}
                onChange={(e) => setClub(e.target.value)}
              >
                {["All clubs", ...new Set(players.map((p) => p.club))].map(
                  (x) => (
                    <option key={x}>{x}</option>
                  ),
                )}
              </select>
              <select
                aria-label="Availability"
                value={availability}
                onChange={(e) => setAvailability(e.target.value)}
              >
                {[
                  "All availability",
                  ...new Set(players.map((p) => p.status)),
                ].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
              <select
                aria-label="Sort players"
                value={sort}
                onChange={(e) => setSort(e.target.value)}
              >
                <option>Predicted points</option>
                <option>Price: low to high</option>
              </select>
            </div>
            <div className="results-meta">
              <span>
                {gw === "6" ? filtered.length : 0} players · illustrative
                predictions
              </span>
              <span>Points rounded to the nearest whole number</span>
            </div>
            {gw !== "6" || !filtered.length ? (
              <div className="empty-state">
                <Mark />
                <h2>
                  {gw !== "6"
                    ? "Next round, still to come."
                    : "No players match your search."}
                </h2>
                <p>
                  {gw !== "6"
                    ? "This prototype contains predictions for Gameweek 6 only."
                    : "Try another name or adjust your filters."}
                </p>
                <button
                  className="button dark-button"
                  onClick={() => {
                    setGw("6")
                    setQuery("")
                    setPosition("All positions")
                    setClub("All clubs")
                    setAvailability("All availability")
                  }}
                >
                  Reset view
                </button>
              </div>
            ) : (
              <div className="player-grid">
                {filtered.map((p) => (
                  <PlayerCard
                    key={p.id}
                    player={p}
                    onClick={() => setDetail(p)}
                  />
                ))}
              </div>
            )}
          </div>
        )}
        {page === "Match Predictions" && (
          <div className="content">
            {heading(
              "READ THE GAME",
              "Every fixture. A clearer picture.",
              "Three outcomes. One balanced view. Explore illustrative match probabilities.",
            )}
            {gw !== "6" ? (
              <div className="empty-state">
                <h2>Predictions not available yet.</h2>
                <p>Choose Gameweek 6 to explore the sample fixtures.</p>
              </div>
            ) : (
              <>
                <section className="match-feature">
                  <div className="card-topline">
                    <span className="eyebrow gold">
                      FIXTURE SPOTLIGHT · GW 06
                    </span>
                    <span>{matches[matchIndex].time}</span>
                  </div>
                  <Teams match={matches[matchIndex]} />
                  <div className="venue">
                    {matches[matchIndex].venue} · All times UK
                  </div>
                  <Probability match={matches[matchIndex]} />
                  <p className="prediction-note">
                    Illustrative outcome probabilities. Football always has the
                    final say.
                  </p>
                </section>
                {sectionHead("THE FULL PICTURE", "Around the grounds.")}
                <div className="match-grid">
                  {matches.map((m, i) => (
                    <button
                      key={m.home}
                      className={`match-card ${
                        matchIndex === i ? "selected" : ""
                      }`}
                      onClick={() => {
                        setMatchIndex(i)
                        window.scrollTo({ top: 150, behavior: "smooth" })
                      }}
                    >
                      <div className="card-topline">
                        <span>{m.time}</span>
                        <span>
                          {matchIndex === i ? "SELECTED" : "EXPLORE ↗"}
                        </span>
                      </div>
                      <Teams match={m} />
                      <Probability match={m} />
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
        {page === "Captain Picks" && (
          <div className="content">
            {heading(
              "LEAD FROM THE FRONT",
              "The armband is a big decision.",
              "A focused shortlist, based on sample predicted points. Your final call.",
            )}
            {gw === "6" ? (
              <>
                <div className="captain-layout">
                  <section className="featured-player captain-feature">
                    <div className="feature-text">
                      <div className="eyebrow gold">
                        ILLUSTRATIVE CAPTAIN PICK
                      </div>
                      <span className="small-text muted-light">
                        {picked.club} · {picked.position}
                      </span>
                      <h2>
                        {picked.name.split(" ").slice(0, -1).join(" ")}
                        <br />
                        {picked.name.split(" ").at(-1)}
                        <span className="gold">.</span>
                      </h2>
                      <Status value={picked.status} />
                      <div className="feature-points">
                        <Points player={picked} />
                        <span>
                          Next fixture
                          <br />
                          <b>{picked.fixture}</b>
                        </span>
                      </div>
                      <button
                        className="text-button light"
                        onClick={() => setDetail(picked)}
                      >
                        View player details <Arrow />
                      </button>
                    </div>
                    <Portrait player={picked} />
                    <span className="captain-badge">C</span>
                  </section>
                  <aside className="captain-reason">
                    <span className="eyebrow">
                      THE THINKING BEHIND THE PICK
                    </span>
                    <h2>
                      Potential,
                      <br />
                      not promises.
                    </h2>
                    <p>
                      {picked.name} projects {Math.round(picked.points!)} points
                      in our illustrative GW6 scenario and is marked available.
                    </p>
                    <div className="reason-row">
                      <span>01</span>
                      <div>
                        <b>Start with the projection</b>
                        <p>
                          Compare expected returns before doubling your
                          captain’s points.
                        </p>
                      </div>
                    </div>
                    <div className="reason-row">
                      <span>02</span>
                      <div>
                        <b>Keep the fixture in focus</b>
                        <p>
                          {picked.fixture} is the next test. Opponent and venue
                          are part of the decision.
                        </p>
                      </div>
                    </div>
                    <div className="reason-row">
                      <span>03</span>
                      <div>
                        <b>Check before the deadline</b>
                        <p>Sample status is not a live team-news update.</p>
                      </div>
                    </div>
                    <span className="selection-confirmation">
                      Current prototype captain: {picked.name}
                    </span>
                  </aside>
                </div>
                {sectionHead(
                  "YOUR ALTERNATIVES",
                  "Different players. Different possibilities.",
                )}
                <div className="player-grid">
                  {players.slice(0, 4).map((p) => (
                    <PlayerCard
                      key={p.id}
                      player={p}
                      selected={captain === p.id}
                      onClick={() => setCaptain(p.id)}
                    />
                  ))}
                </div>
              </>
            ) : (
              <div className="empty-state">
                <h2>No captain shortlist for this round.</h2>
                <p>
                  Return to Gameweek 6 for the illustrative recommendations.
                </p>
              </div>
            )}
          </div>
        )}
        {page === "Squad Builder" && (
          <div className="content">
            {heading(
              "THE TACTICAL ROOM",
              "Your squad. Your signature.",
              "Explore a sample 3–5–2 formation. Select a player to inspect or replace them.",
            )}
            {gw === "6" ? (
              <div className="squad-layout">
                <div>
                  <div className="pitch">
                    <div className="pitch-lines" />
                    <div className="formation-label">
                      STARTING XI <span>3 — 5 — 2</span>
                    </div>
                    {[
                      ["GK", [8]],
                      ["DEF", [6, 7, 10]],
                      ["MID", [1, 2, 3, 5, 13]],
                      ["FWD", [0, 4]],
                    ].map(([pos, ids]) => (
                      <div className="pitch-row" key={pos as string}>
                        {(ids as number[]).map((index) => {
                          const p = players.find((p) => p.id === squad[index])!
                          return (
                            <button
                              key={index}
                              className={`pitch-player ${
                                slot === index ? "selected" : ""
                              }`}
                              onClick={() => setSlot(index)}
                            >
                              <div className="pitch-photo">
                                <Portrait player={p} />
                                {p.id === captain && (
                                  <span className="mini-captain">C</span>
                                )}
                              </div>
                              <b>{p.name.split(" ").at(-1)}</b>
                              <span>
                                {p.points === null ? "—" : Math.round(p.points)}{" "}
                                pts · {p.fixture}
                              </span>
                              <small>{p.status}</small>
                            </button>
                          )
                        })}
                      </div>
                    ))}
                  </div>
                  <div className="bench">
                    <span className="eyebrow">THE BENCH</span>
                    <div>
                      {[9, 11, 12, 14].map((index) => {
                        const p = players.find((p) => p.id === squad[index])!
                        return (
                          <button
                            key={index}
                            onClick={() => setSlot(index)}
                            className={slot === index ? "selected" : ""}
                          >
                            <b>{p.name}</b>
                            <span>
                              {p.position} · {p.status}
                            </span>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                </div>
                <aside className="squad-panel">
                  <span className="eyebrow">SQUAD NOTES</span>
                  <h2>
                    A plan for
                    <br />
                    the next whistle.
                  </h2>
                  <div className="squad-total">
                    <span>Illustrative squad cost</span>
                    <strong>
                      £
                      {squad
                        .reduce(
                          (sum, id) =>
                            sum + players.find((p) => p.id === id)!.price,
                          0,
                        )
                        .toFixed(1)}
                      <small>m</small>
                    </strong>
                  </div>
                  <p>
                    This is an exploratory squad, not a validated FPL entry.
                    Budget and club limits are not enforced.
                  </p>
                  {slot === null ? (
                    <div className="selection-hint">
                      Select a shirt on the pitch or a bench player to explore
                      your options.
                    </div>
                  ) : (
                    (() => {
                      const p = players.find((p) => p.id === squad[slot])!
                      const alternatives = players.filter(
                        (x) =>
                          x.position === p.position && !squad.includes(x.id),
                      )
                      return (
                        <div className="slot-panel">
                          <span className="eyebrow">
                            SELECTED · {p.position}
                          </span>
                          <h3>{p.name}</h3>
                          <Status value={p.status} />
                          <button
                            className="button dark-button"
                            onClick={() => setDetail(p)}
                          >
                            Player details <Arrow />
                          </button>
                          <button
                            className="text-button"
                            onClick={() => setCaptain(p.id)}
                          >
                            Make captain {captain === p.id ? "✓" : "→"}
                          </button>
                          <h4>Explore a replacement</h4>
                          {alternatives.length ? (
                            alternatives.map((x) => (
                              <button
                                className="replacement"
                                key={x.id}
                                onClick={() =>
                                  setSquad((s) =>
                                    s.map((id, i) => (i === slot ? x.id : id)),
                                  )
                                }
                              >
                                {x.name}
                                <span>
                                  £{x.price.toFixed(1)}m · {x.status}
                                </span>
                              </button>
                            ))
                          ) : (
                            <p>
                              All sample {p.position} players are already in
                              your squad. This small dataset has no unused
                              replacements.
                            </p>
                          )}
                          <button
                            className="text-button"
                            onClick={() => {
                              const other = squad.findIndex(
                                (id) =>
                                  players.find((x) => x.id === id)?.position ===
                                    p.position && id !== p.id,
                              )
                              if (other >= 0)
                                setSquad((s) =>
                                  s.map((id, i) =>
                                    i === slot
                                      ? s[other]
                                      : i === other
                                        ? s[slot]
                                        : id,
                                  ),
                                )
                            }}
                          >
                            Swap with another {p.position} →
                          </button>
                        </div>
                      )
                    })()
                  )}
                </aside>
              </div>
            ) : (
              <div className="empty-state">
                <h2>Your sample squad targets GW6.</h2>
                <p>Choose Gameweek 6 to return to the tactical room.</p>
              </div>
            )}
          </div>
        )}
        {page === "AI Assistant" && (
          <div className="content assistant-content">
            <div className="assistant-top">
              <span className="eyebrow gold">THE WIZARD’S ROOM</span>
              <button
                className="text-button light"
                onClick={() => {
                  if (timer.current) clearTimeout(timer.current)
                  setMessages([])
                  setError(false)
                  setLoading(false)
                  setDraft("")
                }}
              >
                ＋ New conversation
              </button>
            </div>
            <div className="assistant-title">
              <Mark />
              <div>
                <h1>
                  A little football wisdom.
                  <br />A <em>smarter</em> next move.
                </h1>
                <p>
                  Your personal FPL thinking partner. Explore the possibilities,
                  then make the call.
                </p>
              </div>
            </div>
            <div className="assistant-disclaimer">
              <span className="scenario-dot" /> DEMO STRATEGIST{" "}
              <span>
                Simulated responses · Illustrative GW6 data · No live AI
                connection
              </span>
            </div>
            <div className="conversation" aria-live="polite">
              {!messages.length && (
                <>
                  <h2>What’s on your mind, manager?</h2>
                  <div className="prompt-grid">
                    {[
                      "Who should I captain this gameweek?",
                      "Compare Haaland and Salah.",
                      "Check the availability of my target players.",
                      "Help me improve my squad.",
                      "Which transfer fits a £7m budget?",
                    ].map((t, i) => (
                      <button key={t} onClick={() => send(t)}>
                        <span className="prompt-number">0{i + 1}</span>
                        <span>{t}</span>
                        <Arrow />
                      </button>
                    ))}
                  </div>
                  <p className="assistant-tip">
                    A good decision starts with a good question.
                  </p>
                </>
              )}
              {messages.map((m, i) => (
                <article key={i} className={`message ${m.role}`}>
                  <div className="message-label">
                    {m.role === "user" ? (
                      "YOU"
                    ) : (
                      <>
                        <Mark small /> FANTASY WIZARD <span>SIMULATED</span>
                      </>
                    )}
                  </div>
                  <p>{m.text}</p>
                  {m.kind && (
                    <div className="response-players">
                      {(m.kind === "availability"
                        ? [players[5], players[12]]
                        : m.kind === "transfer"
                          ? [players[13]]
                          : players.slice(0, 2)
                      ).map((p) => (
                        <button key={p.id} onClick={() => setDetail(p)}>
                          <Portrait player={p} />
                          <div>
                            <b>{p.name}</b>
                            <Status value={p.status} />
                          </div>
                          <strong>
                            {p.points === null ? "—" : Math.round(p.points)}
                            <small>pred. pts</small>
                          </strong>
                        </button>
                      ))}
                    </div>
                  )}
                </article>
              ))}
              {loading && (
                <div className="thinking" role="status">
                  <Mark small />
                  <span>Thinking through the possibilities</span>
                  <span className="loading-dots">···</span>
                </div>
              )}
              {error && (
                <div className="error-state" role="alert">
                  <p>
                    The demo response couldn’t be completed. Your message is
                    safe.
                  </p>
                  <button
                    className="button gold-button"
                    onClick={() =>
                      send(
                        messages
                          .filter((m) => m.role === "user")
                          .at(-1)
                          ?.text.replace(/error/gi, "captain") ||
                          "Who should I captain?",
                      )
                    }
                  >
                    Retry demo response
                  </button>
                </div>
              )}
              <div ref={end} />
            </div>
            <form
              className="composer"
              onSubmit={(e) => {
                e.preventDefault()
                send(draft)
              }}
            >
              <textarea
                aria-label="Message the Wizard"
                rows={2}
                placeholder="Ask about your next move..."
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault()
                    send(draft)
                  }
                }}
              />
              <button
                className="send-button"
                type="submit"
                disabled={!draft.trim() || loading}
                aria-label="Send message"
              >
                ↑
              </button>
            </form>
            <p className="composer-note">
              Your judgement. Our perspective. Always check team news before the
              deadline.{" "}
              <span>Enter to send · Shift + Enter for a new line</span>
            </p>
          </div>
        )}
      </main>
      <footer className="site-footer">
        <div className="footer-brand">
          <Mark small />
          <span>FANTASY WIZARD</span>
          <span className="muted">A smarter way to play.</span>
        </div>
        <p>
          Independent FPL concept. All data is illustrative, not live or
          verified.
        </p>
        <span>THE BEAUTIFUL GAME. A BETTER PERSPECTIVE.</span>
      </footer>
      <dialog
        ref={dialog}
        className="player-dialog"
        onCancel={() => setDetail(null)}
        onClick={(e) => {
          if (e.target === e.currentTarget) setDetail(null)
        }}
      >
        {detail && (
          <>
            <button
              className="dialog-close"
              aria-label="Close player details"
              onClick={() => setDetail(null)}
            >
              ✕
            </button>
            <div className="detail-visual">
              <Portrait player={detail} />
              <span className="eyebrow gold">THE PLAYER PROFILE · GW6</span>
              <Points player={detail} />
            </div>
            <div className="detail-body">
              <span className="eyebrow">
                {detail.club} · {detail.position}
              </span>
              <h2>{detail.name}</h2>
              <Status value={detail.status} />
              <div className="detail-stats">
                <div>
                  <span>Next fixture</span>
                  <b>{detail.fixture}</b>
                </div>
                <div>
                  <span>Price</span>
                  <b>£{detail.price.toFixed(1)}m</b>
                </div>
                <div>
                  <span>Ownership</span>
                  <b>{detail.ownership}%</b>
                </div>
              </div>
              <p>
                {detail.points === null
                  ? "No prediction is available for this player."
                  : `A sample projection of ${Math.round(detail.points)} points. Predictions are rounded for display; underlying sample value: ${detail.points}.`}
              </p>
              {detail.ownership < 10 &&
                detail.points !== null &&
                detail.points >= 5 && (
                  <div className="differential-note">
                    A different angle · Less than 10% sample ownership
                  </div>
                )}
              <p className="small-text muted">
                Illustrative scenario only. Availability is not live team news.
              </p>
              <button
                className="button dark-button"
                onClick={() => {
                  setDetail(null)
                  navigate("AI Assistant")
                  setDraft(`Tell me about ${detail.name}`)
                }}
              >
                Discuss with the Wizard <Arrow />
              </button>
            </div>
          </>
        )}
      </dialog>
    </>
  )
}
export default App
