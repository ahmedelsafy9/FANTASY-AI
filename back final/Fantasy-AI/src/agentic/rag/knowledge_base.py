"""Knowledge base: curated FPL rules and strategy documents.

Documents are stored as structured Python objects rather than files
on disk, making them portable and testable.  Each document has a
source identifier so the agent can distinguish retrieved knowledge
from live FPL data.

The knowledge base is deliberately separate from live player data.
It contains ONLY static/semi-static information:
- FPL rules
- Transfer rules
- Chip rules
- Captaincy strategies
- General fantasy football strategy
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from src.config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class KnowledgeDocument:
    """A single knowledge document with metadata.

    Attributes:
        title: Short title for the document.
        content: Full text content.
        category: Category tag (e.g. "rules", "strategy", "chips").
        source: Source identifier for citation.
    """

    title: str
    content: str
    category: str
    source: str = "fantasy_ai_knowledge_base"

    @property
    def doc_id(self) -> str:
        """Deterministic ID derived from title + category."""
        raw = f"{self.category}:{self.title}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]


@dataclass(frozen=True)
class KnowledgeChunk:
    """A chunk of a knowledge document for retrieval.

    Attributes:
        text: The chunk text.
        doc_id: The parent document's ID.
        chunk_index: Position within the parent document.
        title: Title of the parent document.
        category: Category of the parent document.
        source: Source identifier.
    """

    text: str
    doc_id: str
    chunk_index: int
    title: str
    category: str
    source: str = "fantasy_ai_knowledge_base"


def chunk_document(
    doc: KnowledgeDocument,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[KnowledgeChunk]:
    """Split a document into overlapping text chunks.

    Args:
        doc: The document to chunk.
        chunk_size: Target chunk size in characters.
        overlap: Character overlap between consecutive chunks.

    Returns:
        List of :class:`KnowledgeChunk` objects.
    """
    text = doc.content.strip()
    if not text:
        return []

    # Split on paragraph boundaries first, then recombine
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[KnowledgeChunk] = []
    current_text = ""
    chunk_idx = 0

    for para in paragraphs:
        if len(current_text) + len(para) + 2 > chunk_size and current_text:
            chunks.append(
                KnowledgeChunk(
                    text=current_text.strip(),
                    doc_id=doc.doc_id,
                    chunk_index=chunk_idx,
                    title=doc.title,
                    category=doc.category,
                    source=doc.source,
                )
            )
            chunk_idx += 1
            # Keep overlap from end of previous chunk
            if overlap > 0 and len(current_text) > overlap:
                current_text = current_text[-overlap:] + "\n\n" + para
            else:
                current_text = para
        else:
            current_text = (current_text + "\n\n" + para).strip()

    # Final chunk
    if current_text.strip():
        chunks.append(
            KnowledgeChunk(
                text=current_text.strip(),
                doc_id=doc.doc_id,
                chunk_index=chunk_idx,
                title=doc.title,
                category=doc.category,
                source=doc.source,
            )
        )

    return chunks


# ---------------------------------------------------------------
# Built-in knowledge documents
# ---------------------------------------------------------------

FPL_RULES = KnowledgeDocument(
    title="FPL Rules and Mechanics",
    category="rules",
    content="""\
Fantasy Premier League (FPL) Rules and Mechanics:

Squad Composition: Each FPL squad consists of 15 players — 2 Goalkeepers (GKP), 5 Defenders (DEF), 5 Midfielders (MID), and 3 Forwards (FWD). The starting XI must include exactly 1 GKP and at least 3 DEF, 2 MID, and 1 FWD. Valid formations include 3-4-3, 3-5-2, 4-3-3, 4-4-2, 4-5-1, 5-3-2, 5-4-1.

Budget: Total squad budget is £100.0m. Player prices change based on transfers in/out. Selling price is the purchase price plus half of any price rise (rounded down).

Scoring System: Goals scored — FWD: 4pts, MID: 5pts, GKP/DEF: 6pts. Assists: 3pts. Clean sheets — GKP/DEF: 4pts, MID: 1pt. Saves (GKP): 1pt per 3 saves. Penalty saves: 5pts. Bonus points: 1-3 pts based on BPS.

Captaincy: The captain earns double points. The vice-captain replaces the captain at 2x only if the captain does not play (0 minutes). Captaincy is the single highest-leverage decision each gameweek.

Auto-substitution: If a starting player does not play, bench players are substituted in order (maintaining valid formation). Bench order matters.

Transfers: 1 free transfer per gameweek, rolling up to a maximum of 5 (as of 2024-25 season rules). Additional transfers cost -4 points each (a 'hit'). Transfers are made before the gameweek deadline.

Deadlines: Each gameweek has a specific deadline. All transfers, captaincy, and team selection must be finalized before the deadline.

Points deductions: Yellow card: -1pt. Red card: -3pts. Own goal: -2pts. Penalty miss: -2pts. Every 2 goals conceded by GKP/DEF: -1pt.
""",
)

TRANSFER_STRATEGY = KnowledgeDocument(
    title="Transfer Strategy Guide",
    category="strategy",
    content="""\
Transfer Strategy in FPL:

Free Transfers: Save free transfers when possible. Having 2+ free transfers provides flexibility. Rolling a transfer is often better than making a marginal move.

When to Take Hits: Only take -4 hits when the expected points gain from the incoming player minus the outgoing player exceeds 4 points over the planning horizon (typically 4-6 gameweeks). Hits for injured/suspended players who will score 0 are almost always worthwhile.

Transfer Timing: Make transfers as close to the deadline as possible to avoid losing value on price drops and to have the latest team news. Exception: if a player is about to rise in price and you want to capture that value.

Planning Horizon: Think 4-6 gameweeks ahead for transfers. A player with slightly lower expected points this week but much better fixtures over 5 weeks is often the better transfer.

Selling Declining Assets: Sell players who are: losing their starting spot, injured long-term, facing a terrible fixture run, or dropping in price significantly. Don't hold a player just because you bought them at a high price (sunk cost fallacy).

Replacement Selection: When replacing a player, consider: predicted points (short and medium-term), fixture difficulty, ownership and effective ownership, minutes security, price trajectory, and how they fit your squad structure.

Kneejerking: Avoid making transfers based on one gameweek's performance. Form over 3-5 games is more reliable than a single haul or blank.

Structure vs. Moves: Maintain a well-structured squad. Don't chase points by breaking your squad structure (e.g., having too many players from one team or one position).
""",
)

CAPTAINCY_STRATEGY = KnowledgeDocument(
    title="Captaincy Strategy Guide",
    category="strategy",
    content="""\
Captaincy Strategy in FPL:

The Golden Rule: Captain the player with the highest expected points, adjusted for risk. The captain decision is worth double, so small edges matter enormously over a season.

Key Factors for Captaincy:
1. Fixture difficulty (home advantage, weak opponent defense)
2. Recent form (last 3-5 gameweeks of returns)
3. Underlying statistics (xG, xA, shots in box, big chances)
4. Availability and minutes security (100% fit, nailed starter)
5. Set-piece responsibility (penalties, free kicks, corners)
6. Historical record against the opponent

Risk vs. Safety: In most gameweeks, pick the safest high-ceiling option. The 'template' captain (highest-owned premium) protects your rank. Differential captaincy (low-ownership pick) is higher variance — use it when chasing rank or in cup matches.

Home vs. Away: Home fixtures generally produce higher returns due to the crowd effect, tactical approach, and set-piece advantage. Weight home fixtures more heavily in captaincy decisions.

Premium vs. Mid-Range: Premium players (£10m+) are premiums for a reason — they have the highest floor AND ceiling. Captaining a £5m midfielder requires a much stronger case than a £12m forward.

Avoiding Traps: Don't captain a player just because they blanked last week (revenge captaincy). Don't captain a doubtful player — even 75% chance of playing means a 25% chance of your captain scoring 0 (vice-captain takes over, but at 2x not your planned pick). Don't captain based on 'gut feeling' over data.

Double Gameweek Captaincy: In double gameweeks, captain the player with 2 fixtures who has the best combined expected points. Two easy fixtures > one easy fixture. But a single excellent fixture can beat two mediocre ones.
""",
)

CHIP_STRATEGY = KnowledgeDocument(
    title="Chip Strategy Guide",
    category="strategy",
    content="""\
FPL Chip Strategy:

Available Chips (one use each per season):
- Wildcard (x2): Unlimited free transfers for one gameweek. First must be used by GW20, second by GW38.
- Free Hit: Make unlimited transfers for one gameweek only — squad reverts to pre-Free Hit state afterward.
- Bench Boost: All 15 players score points (not just starting XI).
- Triple Captain: Captain earns 3x points instead of 2x.

Wildcard Timing:
- Use the first wildcard when your squad needs 4+ transfers to be competitive, or when there's a clear fixture swing for many teams.
- Common triggers: international break injuries, major fixture swings, falling team value, poor squad structure.
- The second wildcard is often best saved for the late-season double/blank gameweek period (GW34-37).

Free Hit Strategy:
- Best used in blank gameweeks (when many teams don't play) to field a full XI.
- Also effective in double gameweeks where you want a different squad structure for just one week.
- Don't waste it on a normal gameweek — its value comes from the temporary nature.

Bench Boost Strategy:
- Maximize value by using in a double gameweek when most of your bench has two fixtures.
- Ensure all 15 players are fit starters before activating.
- A Bench Boost in a single gameweek typically adds 8-16 points. In a double, it can add 15-30+.

Triple Captain Strategy:
- Best used on a premium attacker in a double gameweek with two excellent home fixtures.
- The player must be 100% fit with zero rotation risk.
- A single-gameweek triple captain is risky but can pay off for a premium with an elite fixture.

Chip Combinations:
- Wildcard → Bench Boost is the classic combo: wildcard to build the perfect 15-man squad, then Bench Boost the following GW.
- Free Hit → normal GW is common in blank/double sequences.
- Don't use two chips in the same gameweek (not allowed anyway).

When NOT to Use Chips:
- Don't panic-wildcard after one bad week.
- Don't Bench Boost when half your bench is doubtful.
- Don't Triple Captain a 75%-chance-of-playing player.
- Don't Free Hit in a normal gameweek just because you're frustrated.
""",
)

GENERAL_STRATEGY = KnowledgeDocument(
    title="General FPL Strategy Principles",
    category="strategy",
    content="""\
General FPL Strategy Principles:

Value vs. Premium: The best FPL strategies balance 2-3 premium players (£10m+) with strong value picks (£5-7m) who overperform their price. 'Enablers' (£4-5m bench fodder) free up budget for premiums.

Fixtures Over Form (Medium-Term): While form matters for the next gameweek, fixtures are more predictive over 4-6 weeks. Target fixture swings — when a team moves from hard to easy fixtures.

Effective Ownership (EO): Your captain's EO determines whether they help or hurt your rank. Captaining a player with 80% EO protects your rank but limits gains. Captaining a 5% EO player is a huge differential — massive gain if they haul, massive loss if they blank.

Diversification: Don't have more than 3 players from one team (the FPL max). Diversification across fixtures protects against blank gameweeks and rotation.

The Template: The 'template' is the most commonly owned set of players. Being close to the template protects your rank. Deviating from it is how you gain rank — but only if your differential picks outperform.

Early Season vs. Late Season: Early season (GW1-8): Rely more on pre-season fixtures and known quantities. Mid-season (GW9-25): Data is rich — use form and underlying stats heavily. Late season (GW30+): Chip strategy becomes critical, and motivation/relegation/title context matters.

Points Per Million (PPM): Evaluate players by their predicted points per £1m of value. A £5m player predicted 5pts (1.0 PPM) is better value than a £12m player predicted 8pts (0.67 PPM), though the premium has a higher absolute ceiling.

Bench Strategy: Your bench should be the cheapest possible players who still start for their teams. Bench order matters for auto-substitution — put the most likely sub first.

Set-and-Forget vs. Active Management: The best managers make fewer, higher-quality moves. Resist the urge to tinker every week. Trust your squad structure and make transfers only when the case is clearly strong.
""",
)

DIFFERENTIAL_STRATEGY = KnowledgeDocument(
    title="Differential Picks Strategy",
    category="strategy",
    content="""\
Differential Picks Strategy:

What is a Differential? A differential is a player with low ownership (typically under 10%) who you believe will outscore higher-owned alternatives. Differentials are how you gain rank on the competition.

When to Target Differentials:
- When you're behind in your mini-league and need to make up ground.
- When a player's fixtures are about to improve dramatically.
- When a player is returning from injury and managers haven't brought them in yet.
- When a newly promoted team's player is being overlooked.
- When a position change or tactical shift gives a player more attacking output.

Evaluating Differentials:
1. Underlying numbers: High xG/xA relative to actual goals/assists suggests the player is 'due' returns.
2. Minutes security: A differential who gets rotated is worthless.
3. Price: Low price = low risk. A £5m differential who blanks costs you less than a £10m one.
4. Fixture run: Even a great player is a bad differential against top-6 defenses.
5. Set pieces: Players on penalties, corners, and free kicks have a higher floor.

Risk Management: Don't fill your squad with differentials. 1-3 differential picks is optimal. The rest of your squad should be safe, high-floor template picks.

Category Tiers:
- Elite Differential: Top predicted points + very low ownership. The dream pick.
- Value Differential: Good predicted points at bargain price. High PPM.
- Emerging Differential: Rising form, about to break out. Higher risk but highest reward.
""",
)


# All built-in knowledge documents
KNOWLEDGE_DOCUMENTS: list[KnowledgeDocument] = [
    FPL_RULES,
    TRANSFER_STRATEGY,
    CAPTAINCY_STRATEGY,
    CHIP_STRATEGY,
    GENERAL_STRATEGY,
    DIFFERENTIAL_STRATEGY,
]


def get_all_chunks(chunk_size: int = 500, overlap: int = 50) -> list[KnowledgeChunk]:
    """Chunk all built-in knowledge documents.

    Args:
        chunk_size: Target chunk size in characters.
        overlap: Character overlap between chunks.

    Returns:
        All chunks from all documents.
    """
    all_chunks: list[KnowledgeChunk] = []
    for doc in KNOWLEDGE_DOCUMENTS:
        all_chunks.extend(chunk_document(doc, chunk_size, overlap))

    logger.info(
        "Knowledge base: %d documents → %d chunks",
        len(KNOWLEDGE_DOCUMENTS),
        len(all_chunks),
    )
    return all_chunks
