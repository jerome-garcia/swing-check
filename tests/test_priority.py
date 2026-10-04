import pytest

from swingcheck.analyzers import Row, grade
from swingcheck.priority import pick_focus, tier

ORDER = ["address", "swing_plane", "takeaway", "halfway_back", "top", "downswing", "impact", "follow_through"]


@pytest.mark.parametrize("value, status, depth", [
    (5, "ok", 0.0),
    (12, "warn", 0.4),     # 2 of the 5-wide yellow band past green (10)
    (15, "warn", 1.0),     # at the red limit
    (20, "flag", 2.0),     # one more yellow-band width past red (15)
    (-12, "warn", 0.2),    # low side: 2 of the 10-wide yellow band (-10 to -20)
    (-30, "flag", 2.0),
])
def test_grade_depth(value, status, depth):
    g = grade(value, -10, 10, -20, 15)
    assert g == status and g.depth == pytest.approx(depth)


def test_one_sided_band_and_rows_pick_up_depth():
    g = grade(0.25, float("-inf"), 0.10, float("-inf"), 0.15)  # e.g. hips toward the ball
    assert g == "flag" and g.depth == pytest.approx(3.0)
    row = Row("Hips vs tush line", "x", "", g)
    assert row.status == "flag" and type(row.status) is str and row.depth == pytest.approx(3.0)
    assert Row("Plain", "x", "", "warn").depth is None  # not from grade(): no depth


def v(name, *rows):
    return {"name": name, "rows": [{"label": label, "status": st, "depth": d} for label, st, d in rows]}


def test_red_always_beats_yellow():
    focus = pick_focus([v("impact", ("Hips vs tush line", "warn", 1.0)),
                        v("takeaway", ("Trail knee flex kept", "warn", 1.0), ("Spine bend kept", "flag", 1.05))], ORDER)
    assert focus["checkpoint"] == "takeaway" and focus["row"] == "Spine bend kept" and focus["status"] == "flag"


def test_tier_outweighs_a_slightly_deeper_red():
    # Early extension just past red (1.2 x 1.5 = 1.8) beats a tier-2 position further in (1.6).
    focus = pick_focus([v("halfway_back", ("Shaft points", "flag", 1.6)),
                        v("impact", ("Hips vs tush line", "flag", 1.2))], ORDER)
    assert focus["checkpoint"] == "impact" and focus["tier"] == 1 and focus["score"] == pytest.approx(1.8)


def test_far_into_red_beats_a_higher_tier():
    focus = pick_focus([v("halfway_back", ("Shaft points", "flag", 3.0)),
                        v("impact", ("Hips vs tush line", "flag", 1.2))], ORDER)
    assert focus["checkpoint"] == "halfway_back"


def test_ties_go_to_swing_order_and_green_means_nothing():
    focus = pick_focus([v("top", ("Lead arm vs spine", "flag", 1.5)),
                        v("halfway_back", ("Shaft points", "flag", 1.5))], ORDER)
    assert focus["checkpoint"] == "halfway_back"
    assert pick_focus([v("top", ("Lead arm vs spine", "ok", 0.0))], ORDER) is None
    assert pick_focus([v("top", ("Lead arm vs spine", "error", None))], ORDER) is None


def test_tiers():
    assert tier("impact", "Hips vs tush line") == 1
    assert tier("downswing", "Clubhead vs swing plane") == 1
    assert tier("downswing", "Shallowing") == 1
    assert tier("takeaway", "Trail knee flex kept") == 3
    assert tier("top", "Lead arm vs spine") == 2


def test_grades_survive_saving():
    import json
    from swingcheck.analyzers import Verdict
    g = grade(20, -10, 10, -20, 15)
    d = Verdict(status=g, label="x", summary="", rows=[Row("a", "1", "", g)]).to_json()
    assert json.loads(json.dumps(d))["rows"][0]["depth"] == pytest.approx(2.0)
