import numpy as np
import pytest

from swingcheck.geometry import (
    along,
    angle_deg,
    classify_in_wedge,
    line_in_frame,
    ray_in_frame,
    signed_distance,
    target_sign,
    to_body_units,
)

# A right-handed DTL setup in a 720x1280 frame: ball low right, lines rising
# up-left toward the golfer. The shoulder line is steeper than the shaft line.
BALL = np.array([600.0, 1180.0])
SHAFT_DIR = np.array([-230.0, -290.0])     # clubhead -> grip
SHOULDER_DIR = np.array([-330.0, -700.0])  # ball -> trail shoulder


def mirror(p, width=720):
    p = np.asarray(p, dtype=float)
    return np.array([width - 1 - p[0], p[1]])


def mirror_dir(d):
    return np.array([-d[0], d[1]])


def zone(p, tol=0.0, ball=BALL, shaft=SHAFT_DIR, shoulder=SHOULDER_DIR):
    return classify_in_wedge(p, ball, shoulder, shaft, tol).zone


def test_points_on_each_side_of_the_plane_wedge():
    bisector = SHAFT_DIR / np.linalg.norm(SHAFT_DIR) + SHOULDER_DIR / np.linalg.norm(SHOULDER_DIR)
    on_plane = BALL + 200 * bisector
    steep = BALL + np.array([-100.0, -700.0])    # more upright than the shoulder line
    shallow = BALL + np.array([-450.0, -250.0])  # flatter than the shaft line
    assert zone(on_plane) == "inside"
    assert zone(steep) == "beyond_a"     # a = shoulder line -> steep / over
    assert zone(shallow) == "beyond_b"   # b = shaft line -> shallow / under


def test_left_handed_mirror_gives_same_zones():
    for p, want in [
        (BALL + np.array([-280.0, -500.0]), "inside"),
        (BALL + np.array([-100.0, -700.0]), "beyond_a"),
        (BALL + np.array([-450.0, -250.0]), "beyond_b"),
    ]:
        got = zone(mirror(p), ball=mirror(BALL), shaft=mirror_dir(SHAFT_DIR), shoulder=mirror_dir(SHOULDER_DIR))
        assert got == want


def test_line_order_does_not_matter_for_inside():
    p = BALL + np.array([-280.0, -500.0])
    assert classify_in_wedge(p, BALL, SHAFT_DIR, SHOULDER_DIR).zone == "inside"


def test_tolerance_band():
    # A point just past the shaft line by 5 px.
    n = np.array([SHAFT_DIR[1], -SHAFT_DIR[0]]) / np.linalg.norm(SHAFT_DIR)
    inside_n = n if np.dot(n, SHOULDER_DIR) > 0 else -n
    p = BALL + SHAFT_DIR * 1.5 - inside_n * 5
    assert zone(p, tol=0.0) == "beyond_b"
    assert zone(p, tol=10.0) == "inside"
    res = classify_in_wedge(p, BALL, SHOULDER_DIR, SHAFT_DIR, 0.0)
    assert res.margin_b == pytest.approx(-5.0)


def test_margins_scale_with_image():
    p = BALL + np.array([-450.0, -250.0])
    r1 = classify_in_wedge(p, BALL, SHOULDER_DIR, SHAFT_DIR)
    r2 = classify_in_wedge(p * 2, BALL * 2, SHOULDER_DIR, SHAFT_DIR)
    assert r2.margin_b == pytest.approx(2 * r1.margin_b)
    # ...so in body units (scale doubles too) they're identical.
    assert to_body_units(r2.margin_b, 520) == pytest.approx(to_body_units(r1.margin_b, 260))


def test_parallel_lines_rejected():
    with pytest.raises(ValueError):
        classify_in_wedge((0, 0), (1, 1), (1, 1), (2, 2))


def test_signed_distance_and_along():
    assert abs(signed_distance((0, 5), (0, 0), (1, 0))) == pytest.approx(5)
    assert signed_distance((0, 5), (0, 0), (1, 0)) == -signed_distance((0, -5), (0, 0), (1, 0))
    assert along((3, 4), (1, 0)) == pytest.approx(3)
    assert along((3, 4), (-2, 0)) == pytest.approx(-3)


def test_body_units():
    assert to_body_units(130, 260) == pytest.approx(0.5)
    with pytest.raises(ValueError):
        to_body_units(1, 0)


def test_angle_deg_uses_screen_up():
    assert angle_deg((1, 0)) == pytest.approx(0)
    assert angle_deg((0, -1)) == pytest.approx(90)  # pointing up the screen
    assert angle_deg((-1, -1)) == pytest.approx(135)


def test_line_and_ray_in_frame():
    seg = line_in_frame(BALL, SHAFT_DIR, 720, 1280)
    assert seg is not None
    for x, y in seg:
        assert 0 <= x <= 719 and 0 <= y <= 1279
    ray = ray_in_frame(BALL, SHAFT_DIR, 720, 1280)
    assert ray[0] == (600, 1180)
    assert ray[1][1] < 1180  # heads up the screen
    assert line_in_frame((-100, -100), (1, 0), 720, 1280) is None


def test_target_sign():
    assert target_sign("fo", "right") == 1
    assert target_sign("fo", "left") == -1
    assert target_sign("fo", "right", "left") == -1
    with pytest.raises(ValueError):
        target_sign("dtl", "right")
