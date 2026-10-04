"""Down-the-line checkpoint 6: downswing (shallowing).

On the frame you mark where the shaft is parallel to the ground coming down
(P6, the mirror of the takeaway), using the clubhead and hands you click:

  down the plane  the clubhead's distance from the address shaft line, square
                  to it (as at the takeaway). Coming down it should be on the
                  line or a little under it (behind the hands). Above the line
                  = over the top (steep); far under = stuck (too flat).
  shallowing      that distance minus the same distance at your takeaway: the
                  club should come down flatter than it went back (clubhead
                  further behind the line). Steeper coming down than going back
                  is the over-the-top loop. Needs the takeaway marked.

Distances are shares of torso length; bands are in [analyzers.downswing].
"""

from __future__ import annotations

import numpy as np

from swingcheck.analyzers import (REFERENCE_COLOR, STATUS_COLORS, MissingData, Overlay, Row, SwingContext, Verdict, grade,
                                  pct, register)
from swingcheck.analyzers.dtl_swing_plane import swing_plane_line
from swingcheck.analyzers.dtl_takeaway import address_line

BAND_COLOR = (150, 150, 150)
HOLD_MS = 400
ORDER = {"ok": 0, "warn": 1, "flag": 2}


@register("downswing", view="dtl", title="Downswing", phase="early_downswing")
def downswing(ctx: SwingContext) -> Verdict:
    mark = ctx.marks.checkpoint("downswing")
    if mark is None:
        raise MissingData("the downswing isn't marked yet: Edit marks → Downswing, then click the clubhead and hands")
    cfg = ctx.cfg
    f = mark.frame
    clubhead = np.asarray(mark.points["clubhead"], float)
    hands = np.asarray(mark.points["grip"], float)
    line = address_line(ctx)
    under = line.inside_by(ctx, clubhead)  # + = behind the line (under the plane), - = above it

    # 1. Down the plane.
    plane_status = grade(under, cfg["under_min"], cfg["under_max"], cfg["under_watch_min"], cfg["under_watch_max"])
    soft = plane_status == "warn"
    if plane_status == "ok":
        plane_label, plane_meaning = "Club down the swing plane", "the club is back on your swing plane line, clubhead just behind your hands"
    elif under < cfg["under_min"]:
        plane_label = "Clubhead slightly above the swing plane" if soft else "Clubhead above the swing plane"
        plane_meaning = ("the clubhead is a little above your swing plane line (steep)" if soft else
                         "the clubhead is well above your swing plane line: over the top")
    else:
        plane_label = "Clubhead well under the swing plane" if soft else "Clubhead stuck under the swing plane"
        plane_meaning = ("the clubhead is well behind your swing plane line (very shallow)" if soft else
                         "the clubhead is far behind your swing plane line: stuck, too flat")

    # 2. Shallowing vs the takeaway (same measure, going back).
    rows_extra: list[Row] = []
    take = ctx.marks.checkpoint("takeaway")
    shallowing = None
    shallow_status = None
    if take is not None:
        shallowing = under - line.inside_by(ctx, take.points["clubhead"])
        shallow_status = grade(shallowing, cfg["shallow_min"], np.inf, cfg["shallow_watch_min"], np.inf)
        if shallow_status == "ok":
            shallow_label, shallow_meaning = "Shallowed", "it comes down flatter than it went back"
        elif shallow_status == "warn":
            shallow_label, shallow_meaning = "Slightly steeper than the takeaway", "it comes down a little steeper than it went back"
        else:
            shallow_label, shallow_meaning = ("Steeper than the takeaway",
                                              "it comes down much steeper than it went back: the over-the-top loop")
        direction = "flatter" if shallowing >= 0 else "steeper"
        rows_extra.append(Row(
            "Shallowing", f"{ctx.distance_text(shallowing)} {direction}",
            f"{pct(abs(shallowing))} of torso length vs your takeaway · {shallow_label.lower()} "
            f"(green {pct(cfg['shallow_min'])} or more flatter, red past {pct(-cfg['shallow_watch_min'])} steeper)",
            shallow_status))
    else:
        rows_extra.append(Row("Shallowing", "–", "mark the takeaway to compare coming down with going back", "error"))

    statuses = [plane_status] + ([shallow_status] if shallow_status else [])
    status = max(statuses, key=ORDER.__getitem__)
    label = plane_label + (f", {shallow_label[0].lower() + shallow_label[1:]}" if shallow_status else "")
    summary = f"Coming down, {plane_meaning}" + (f", and {shallow_meaning}." if shallow_status else ".")

    # Drawing: the address shaft line with the on-plane band (under side), a square tick
    # from the clubhead to the line, and the takeaway clubhead for comparison.
    s = ctx.scale
    show = (f, min(len(ctx.pose) - 1, f + int(round(HOLD_MS * ctx.fps / 1000))))
    col = STATUS_COLORS[plane_status]
    foot = clubhead - (under * s) * line.normal
    overlays = swing_plane_line(ctx, show) + [
        Overlay("segment", [tuple(clubhead), tuple(foot)], col, "", show, 2),
        Overlay("point", [tuple(hands)], REFERENCE_COLOR, "", show, 1),
        Overlay("point", [tuple(clubhead)], col, "", show, 2),
        Overlay("text", [(float(clubhead[0]) - line.toward_golfer * 0.15 * s, float(clubhead[1]) + 0.25 * s)], col,
                plane_label, show),
    ]
    if take is not None:
        overlays.append(Overlay("point", [tuple(take.points["clubhead"])], BAND_COLOR, "clubhead at takeaway", show, 1))

    side = "under" if under >= 0 else "above"
    tips = []
    if plane_status != "ok":
        tips.append("Start down with the lower body and let your trail elbow drop toward your hip, so the club falls under the plane."
                    if under < cfg["under_min"] else
                    "Keep turning your chest through so the club can come out in front of you.")
    if shallow_status not in (None, "ok"):
        tips.append("Come down flatter than you went back: take it back less inside, or let the club drop behind you on the way down.")
    tip = " ".join(tips)

    return Verdict(
        status=status,
        label=label,
        summary=summary,
        tip=tip,
        frame=f,
        measurements={
            "clubhead_under_line": round(under, 3),
            "shallowing_vs_takeaway": round(shallowing, 3) if shallowing is not None else None,
            "downswing_frame": f,
            "units": "share of torso length, square to the address shaft line; under: + = behind the line "
                     "(golfer's side), - = above it; shallowing: + = flatter coming down than at the takeaway",
        },
        rows=[
            Row("Clubhead vs swing plane", f"{ctx.distance_text(under)} {side}",
                f"{pct(abs(under))} of torso length · {plane_label.lower()} "
                f"(green {pct(cfg['under_min'])}–{pct(cfg['under_max'])} under, "
                f"red past {pct(-cfg['under_watch_min'])} above or {pct(cfg['under_watch_max'])} under)", plane_status),
            *rows_extra,
        ],
        overlays=overlays,
    )
