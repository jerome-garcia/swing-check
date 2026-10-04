"""Which fault to work on first: importance tiers combined with how far into red.

Every graded row on a checkpoint card carries a severity (Row.depth): 0 in the
green, 0-1 across the yellow band, and 1 plus how far past the red limit
(in widths of the yellow band) once red. Each row also has an importance tier:

  1  costs shots directly: the club over the top / stuck coming down (and
     coming down steeper than it went back), early extension and standing up /
     dipping at impact
  2  positions (the default): setup, the club at each checkpoint
  3  contributors: posture and trail knee kept through the backswing and
     downswing (the impact posture row is tier 1)

The score is severity x the tier's weight. A red row always outranks a yellow
one, so "Work on first" is always a red when there is one; within the same
color the higher score wins, and swing order breaks ties.
"""

from __future__ import annotations

from typing import Any

TIER_WEIGHT = {1: 1.5, 2: 1.0, 3: 0.6}

# (checkpoint, row label) -> tier. Rows not listed are tier 2.
TIERS: dict[tuple[str, str], int] = {
    ("downswing", "Clubhead vs swing plane"): 1,
    ("downswing", "Shallowing"): 1,  # coming down steeper than going back: the over-the-top loop
    ("impact", "Hips vs tush line"): 1,
    ("impact", "Spine bend kept"): 1,
    ("takeaway", "Spine bend kept"): 3,
    ("halfway_back", "Spine bend kept"): 3,
    ("top", "Spine bend kept"): 3,
    ("downswing", "Spine bend kept"): 3,
    ("takeaway", "Trail knee flex kept"): 3,
    ("halfway_back", "Trail knee flex kept"): 3,
}


def tier(checkpoint: str, row_label: str) -> int:
    return TIERS.get((checkpoint, row_label), 2)


def pick_focus(verdicts: list[dict[str, Any]], order: list[str]) -> dict[str, Any] | None:
    """The row to work on first, from verdicts as saved (to_json), or None when nothing
    is yellow or red. `order` is the checkpoints' swing order (analyzer names)."""
    best, best_key = None, None
    for v in verdicts:
        name = v.get("name")
        position = order.index(name) if name in order else len(order)
        for r in v.get("rows") or []:
            status, depth = r.get("status"), r.get("depth")
            if status not in ("warn", "flag") or depth is None:
                continue
            t = tier(name, r.get("label", ""))
            score = depth * TIER_WEIGHT[t]
            key = (status == "flag", score, -position)
            if best_key is None or key > best_key:
                best_key = key
                best = {"checkpoint": name, "row": r.get("label"), "status": status, "tier": t,
                        "depth": round(depth, 3), "score": round(score, 3)}
    return best
