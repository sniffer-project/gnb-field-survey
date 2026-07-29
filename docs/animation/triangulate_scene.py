"""A 3Blue1Brown-style explainer of the gNB triangulation pipeline.

Renders the real ``Hall 14`` survey geometry (solved by ``gnb_survey.triangulate``)
as a top-down East-North story:

    survey points  ->  range rings (no bearing!)  ->  the two-basin ambiguity
    ->  SR-LS closed-form global seed  ->  Levenberg-Marquardt refinement
    ->  1-sigma covariance error ellipse  ->  final fix.

Two scenes:
  * GnbTriangulation - the top-down geometry story.
  * GnbMath          - the math, 3b1b "derivation" style: measurement model,
                       weighted least-squares cost, non-convexity, the
                       squared-range (GTRS) global seed, LM refine, covariance.

Built for ManimGL (3b1b's engine). Render with::

    manimgl animation/triangulate_scene.py GnbTriangulation -w -l   # mp4 file
    manimgl animation/triangulate_scene.py GnbMath          -w --hd # 1080p
    manimgl animation/triangulate_scene.py GnbMath                  # interactive

Geometry constants below are the actual ENU values produced by the solver, so
the picture is faithful rather than illustrative.
"""

from __future__ import annotations

import json
import os

import numpy as np

from manimlib import *

# --- Scene data ---------------------------------------------------------------
# gnb_survey.animate.runner sets GNB_SCENE_JSON to one survey's solved geometry.
# Unset, the real Hall 14 numbers below are used, so this file still renders
# standalone as documentation.
SCENE_ENV = "GNB_SCENE_JSON"
SCENE_SCHEMA = 1


def _load_scene():
    path = os.environ.get(SCENE_ENV)
    if not path:
        return None
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if data.get("schema") != SCENE_SCHEMA:
        raise SystemExit(
            f"{path} has scene schema {data.get('schema')!r}, expected "
            f"{SCENE_SCHEMA}. Re-run `python survey.py <name> solve`."
        )
    return data


_SCENE = _load_scene()

if _SCENE is None:
    # Real solved geometry (Hall 14), local ENU metres.
    # (label, East, North, slant_distance_m, elevation_deg)
    SURVEY = [
        ("S1", 0.00, 0.00, 82.3, 17.0),
        ("S2", -8.81, 12.39, 98.2, 17.0),
        ("S3", 11.59, 27.27, 97.8, 16.0),
        ("S4", 21.30, 31.82, 95.5, 18.0),
        ("S?", 4.12, 22.41, 97.5, 17.0),   # "Sniffer optional"
        ("UE", 6.35, 4.06, 80.9, 18.0),
    ]
    SRLS_SEED_EN = (61.23, -54.76)        # closed-form global seed (E, N)
    GNB_EN = (61.58, -50.34)              # refined gNB position (E, N)
    ELLIPSE_MAJOR_M = 4.36                # 1-sigma semi-axes
    ELLIPSE_MINOR_M = 0.73
    ELLIPSE_AZIMUTH_DEG = None
    RESULT_LINES = [
        "lat  1.3524001°",
        "lon  103.6822124°",
        "alt  52.9 m",
        "SVY21  11183.6 E,  37167.6 N",
    ]
    SURVEY_NAME = "Hall 14"
else:
    SURVEY = [
        (p["label"], p["e"], p["n"], p["dist_m"], p["elev_deg"])
        for p in _SCENE["points"]
    ]
    seed = _SCENE.get("srls_seed_en")
    # None when SR-LS was degenerate and the solver fell back to a multi-start.
    # The seed beat then starts from the final fix, which is honest: there was
    # no closed-form seed to show.
    SRLS_SEED_EN = tuple(seed) if seed else tuple(_SCENE["gnb_en"])
    GNB_EN = tuple(_SCENE["gnb_en"])
    ELLIPSE_MAJOR_M = _SCENE["ellipse"]["major_m"]
    ELLIPSE_MINOR_M = _SCENE["ellipse"]["minor_m"]
    ELLIPSE_AZIMUTH_DEG = _SCENE["ellipse"]["azimuth_deg"]
    RESULT_LINES = _SCENE["result_lines"]
    SURVEY_NAME = _SCENE["survey"]

# Colours (3b1b palette).
C_POINT = BLUE_B
C_RING = "#3d6fb4"
C_SEED = YELLOW
C_GNB = "#ff4d4d"
C_RESID = GREY_B
C_ELLIPSE = GREEN_SCREEN


def horizontal_range(dist_m: float, elev_deg: float) -> float:
    """Ground-plane radius the gNB must lie on: r = d * cos(elevation)."""
    return dist_m * np.cos(np.radians(elev_deg))


class GnbTriangulation(Scene):
    def construct(self):
        self.frame.set_height(10)            # zoomed out enough to see both basins

        axes = Axes(
            x_range=(-100, 120, 20),
            y_range=(-100, 60, 20),
            width=8.8,
            height=6.4,
            axis_config=dict(stroke_color=GREY_D, stroke_width=1.5, include_tip=False),
        )
        self.axes = axes
        self.u = axes.x_axis.get_unit_size()  # scene units per metre (x == y)

        self.intro(axes)
        self.show_points(axes)
        self.one_measurement(axes)
        self.all_rings(axes)
        self.ambiguity(axes)
        self.srls_seed(axes)
        self.refine(axes)
        self.error_ellipse(axes)
        self.final_card(axes)

    # -- helpers ---------------------------------------------------------------
    def p(self, en):
        """ENU (East, North) metres -> scene point."""
        return self.axes.c2p(en[0], en[1])

    def ring(self, center_en, r_m):
        circ = Circle(radius=r_m * self.u).move_to(self.p(center_en))
        circ.set_stroke(C_RING, width=2, opacity=0.85)
        return DashedVMobject(circ, num_dashes=64)

    def caption(self, text, color=WHITE):
        c = Text(text, font_size=30, color=color)
        c.fix_in_frame()
        c.to_edge(UP, buff=0.35)
        return c

    def set_caption(self, new_text, color=WHITE):
        new = self.caption(new_text, color)
        if getattr(self, "_cap", None) is None:
            self._cap = new
            self.play(FadeIn(self._cap, shift=0.2 * DOWN), run_time=0.6)
        else:
            # Plain crossfade (no glyph morphing) keeps captions legible.
            self.play(
                FadeOut(self._cap, shift=0.2 * UP),
                FadeIn(new, shift=0.2 * UP),
                run_time=0.6,
            )
            self._cap = new

    # -- beats -----------------------------------------------------------------
    def intro(self, axes):
        title = Text("Where is the gNB?", font_size=60, weight=BOLD)
        title.fix_in_frame()
        sub = Text(
            "Locating a 5G base station from rangefinder survey points",
            font_size=28, color=GREY_B,
        )
        sub.fix_in_frame()
        sub.next_to(title, DOWN, buff=0.3)
        self.play(Write(title), run_time=1.2)
        self.play(FadeIn(sub, shift=0.2 * UP), run_time=0.8)
        self.wait(1.2)
        self.play(FadeOut(title), FadeOut(sub), run_time=0.7)

        labels = axes.get_axis_labels("E", "N")
        labels.set_color(GREY_B)
        self.play(ShowCreation(axes), FadeIn(labels), run_time=1.2)
        self.axis_labels = labels

    def show_points(self, axes):
        self.set_caption("6 survey points with known positions")
        dots = VGroup()
        tags = VGroup()
        for label, e, n, *_ in SURVEY:
            d = Dot(self.p((e, n)), radius=0.06, color=C_POINT)
            d.set_stroke(WHITE, 1)
            t = Text(label, font_size=18, color=C_POINT).next_to(d, UR, buff=0.04)
            dots.add(d)
            tags.add(t)
        self.survey_dots = dots
        self.play(
            LaggedStartMap(GrowFromCenter, dots, lag_ratio=0.15),
            LaggedStartMap(FadeIn, tags, lag_ratio=0.15),
            run_time=1.8,
        )
        self.point_tags = tags

        q = Text("?", font_size=44, color=C_GNB, weight=BOLD).move_to(self.p(GNB_EN))
        self.gnb_q = q
        self.play(FadeIn(q, scale=0.5), run_time=0.6)
        self.wait(0.6)

    def one_measurement(self, axes):
        self.set_caption("Each reading: a slant distance and an elevation angle")
        e, n, dist, elev = SURVEY[0][1], SURVEY[0][2], SURVEY[0][3], SURVEY[0][4]
        start = self.p((e, n))
        end = self.p(GNB_EN)
        beam = Line(start, end, color=C_SEED, stroke_width=3)
        readout = Tex(r"d = 82.3\,\text{m},\ \ \theta = 17^\circ", font_size=30)
        readout.fix_in_frame()
        readout.to_edge(DOWN, buff=0.5)
        self.play(ShowCreation(beam), FadeIn(readout), run_time=1.0)
        self.wait(0.6)

        # No bearing -> collapse the beam onto a full ring of possible positions.
        r = horizontal_range(dist, elev)
        ring = self.ring((e, n), r)
        formula = Tex(r"r = d\cos\theta", font_size=30)
        formula.fix_in_frame()
        formula.next_to(readout, UP, buff=0.2)
        self.set_caption("No compass bearing - the gNB lies somewhere on a ring")
        self.play(
            ReplacementTransform(beam, ring),
            FadeIn(formula),
            run_time=1.3,
        )
        self.first_ring = ring
        self.wait(0.8)
        self.play(FadeOut(readout), FadeOut(formula), run_time=0.5)

    def all_rings(self, axes):
        self.set_caption("One ring per point - trilateration")
        rings = VGroup(self.first_ring)
        new_rings = VGroup()
        for label, e, n, dist, elev in SURVEY[1:]:
            new_rings.add(self.ring((e, n), horizontal_range(dist, elev)))
        self.play(LaggedStartMap(ShowCreation, new_rings, lag_ratio=0.2), run_time=2.2)
        rings.add(*new_rings)
        self.rings = rings
        self.wait(0.6)

    def ambiguity(self, axes):
        self.set_caption("Range-only cost is non-convex: two candidate basins", C_SEED)
        # The true SE basin, plus the opposite (NW) basin. The geometric mirror
        # through the cluster centroid sits off-plot (N ~ 83 m), so we mark an
        # illustrative NW point inside the frame.
        mirror = (-52.0, 48.0)
        se = Circle(radius=0.5, color=C_SEED).move_to(self.p(GNB_EN)).set_stroke(width=3)
        nw = Circle(radius=0.5, color=C_SEED).move_to(self.p(mirror)).set_stroke(width=3)
        q2 = Text("?", font_size=40, color=C_SEED, weight=BOLD).move_to(self.p(mirror))
        self.play(ShowCreation(se), ShowCreation(nw), FadeIn(q2), run_time=1.2)
        self.wait(1.0)
        self.play(FadeOut(nw), FadeOut(q2), FadeOut(self.gnb_q), run_time=0.7)
        self.basin = se

    def srls_seed(self, axes):
        self.set_caption("SR-LS: a closed-form global seed (no initial guess)", C_SEED)
        seed = Dot(self.p(SRLS_SEED_EN), radius=0.10, color=C_SEED)
        seed.set_stroke(WHITE, 1)
        halo = Circle(radius=0.28, color=C_SEED).move_to(seed).set_stroke(width=2, opacity=0.6)
        tag = Text("SR-LS seed", font_size=22, color=C_SEED).next_to(seed, DOWN, buff=0.12)
        self.play(
            FadeOut(self.basin),
            FadeIn(seed, scale=0.4),
            ShowCreation(halo),
            FadeIn(tag),
            run_time=1.0,
        )
        self.play(halo.animate.scale(1.6).set_opacity(0), run_time=0.8)
        self.remove(halo)
        self.seed_dot = seed
        self.seed_tag = tag
        self.wait(0.5)

    def refine(self, axes):
        self.set_caption("Levenberg-Marquardt refines on true distance + elevation")
        gnb = Dot(self.p(GNB_EN), radius=0.10, color=C_GNB).set_stroke(WHITE, 1)
        # Residual spokes from every survey point to the moving estimate.
        resid = VGroup(*[
            Line(self.p((e, n)), self.seed_dot.get_center(), color=C_RESID, stroke_width=1.5)
            for _, e, n, *_ in SURVEY
        ])
        self.play(FadeIn(resid), FadeOut(self.seed_tag), run_time=0.6)

        moving = self.seed_dot
        target = gnb.get_center()
        starts = [self.p((e, n)) for _, e, n, *_ in SURVEY]

        def update_resid(group):
            for line, s in zip(group, starts):
                line.set_points_by_ends(s, moving.get_center())

        resid.add_updater(update_resid)
        self.play(
            moving.animate.move_to(target).set_color(C_GNB),
            run_time=2.0,
            rate_func=smooth,
        )
        resid.clear_updaters()
        self.gnb_dot = moving
        self.resid = resid
        self.wait(0.6)
        self.play(FadeOut(resid), run_time=0.6)

    def error_ellipse(self, axes):
        self.set_caption("Jacobian -> covariance -> 1σ error ellipse")
        if ELLIPSE_AZIMUTH_DEG is None:
            # No solved azimuth: fall back to the centroid->gNB line of sight,
            # which is roughly the major axis for a fan of range-only fixes.
            centroid = np.mean([[e, n] for _, e, n, *_ in SURVEY], axis=0)
            los = np.array(GNB_EN) - centroid
            ang = np.arctan2(los[1], los[0])
        else:
            # Solution.ellipse_azimuth_deg is a compass bearing (0 = north),
            # while manim rotates anticlockwise from +x (east).
            ang = np.radians(90.0 - ELLIPSE_AZIMUTH_DEG)

        ell = Ellipse(
            width=2 * ELLIPSE_MAJOR_M * self.u,
            height=2 * ELLIPSE_MINOR_M * self.u,
        )
        ell.set_stroke(C_ELLIPSE, width=3).set_fill(C_ELLIPSE, opacity=0.18)
        ell.rotate(ang).move_to(self.p(GNB_EN))

        # Zoom into the gNB so the (truly tiny) ellipse is legible.
        self.play(
            FadeOut(self.rings),
            FadeOut(self.survey_dots),
            FadeOut(self.point_tags),
            run_time=0.8,
        )
        # Shrink the gNB dot while zoomed in so it sits inside the (tiny)
        # ellipse instead of swamping it.
        self.play(
            self.frame.animate.set_height(1.6).move_to(self.p(GNB_EN)),
            self.gnb_dot.animate.scale(0.22),
            run_time=1.6,
        )
        self.play(ShowCreation(ell), run_time=1.0)
        size = Text("4.4 m × 0.7 m", font_size=24, color=C_ELLIPSE)
        size.fix_in_frame()
        size.to_edge(DOWN, buff=0.6)
        self.play(FadeIn(size), run_time=0.6)
        self.wait(1.2)
        self.ellipse = ell
        self.ellipse_size = size

    def final_card(self, axes):
        self.set_caption("Solved gNB position", C_GNB)
        self.play(
            self.frame.animate.set_height(10).move_to(ORIGIN),
            FadeOut(self.ellipse_size),
            FadeOut(self.ellipse),
            FadeOut(self.axis_labels),
            self.gnb_dot.animate.scale(1.3 / 0.22),   # restore + a touch larger
            run_time=1.5,
        )
        card = VGroup(*[Text(line, font_size=26) for line in RESULT_LINES])
        card.arrange(DOWN, aligned_edge=LEFT, buff=0.22)
        card.fix_in_frame()
        box = SurroundingRectangle(card, buff=0.35, color=C_GNB)
        box.set_fill(BLACK, opacity=0.6)
        group = VGroup(box, card).to_edge(RIGHT, buff=0.6)
        group.fix_in_frame()
        self.play(FadeIn(box), Write(card), run_time=1.6)
        self.play(Flash(self.gnb_dot, color=C_GNB, flash_radius=0.4), run_time=1.0)
        self.wait(2.0)


# =============================================================================
#  Companion scene: the math, 3b1b "derivation" style.
# =============================================================================
C_RANGE = "#5bc0eb"     # range / distance terms
C_ELEV = "#f4a259"      # elevation terms
C_ALPHA = YELLOW        # the squared-range substitution alpha = ||x||^2


class GnbMath(Scene):
    """Animated walk through the estimator: model -> weighted cost ->
    non-convexity -> squared-range (GTRS) global seed -> LM refine -> covariance.
    """

    def construct(self):
        self.section_label = None
        self.subs = []                       # (start_time, text) for the .srt track
        self.model()
        self.cost()
        self.nonconvex()
        self.squared_range()
        self.gtrs()
        self.bisection()
        self.refine_and_cov()
        self.recap()
        self._write_srt()

    # -- helpers ---------------------------------------------------------------
    def section(self, text, color=WHITE):
        lab = Text(text, font_size=30, color=color, weight=BOLD)
        lab.fix_in_frame()
        lab.to_edge(UP, buff=0.35)
        if self.section_label is None:
            self.section_label = lab
            self.play(FadeIn(lab, shift=0.2 * DOWN), run_time=0.5)
        else:
            self.play(
                FadeOut(self.section_label, shift=0.2 * UP),
                FadeIn(lab, shift=0.2 * UP),
                run_time=0.5,
            )
            self.section_label = lab

    def curve(self, axes, func, x0, x1, color, n=160, width=3):
        pts = [axes.c2p(x, func(x)) for x in np.linspace(x0, x1, n)]
        vm = VMobject().set_points_smoothly(pts)
        vm.set_stroke(color, width)
        return vm

    # -- plain-language narration / subtitle track -----------------------------
    def narrate(self, text):
        """Show a bottom subtitle and record it for the .srt sidecar.

        Called between plays, so the swap is instantaneous (self.add/remove, no
        animation) — that keeps every later beat's timing, and the recorded
        timestamps, exactly as before.
        """
        self.subs.append((float(self.time), text))
        cap = Text(text, font_size=20, color=WHITE)
        cap.fix_in_frame()
        cap.to_edge(DOWN, buff=0.28)
        bg = BackgroundRectangle(cap, fill_opacity=0.6, buff=0.14)
        bg.fix_in_frame()
        group = VGroup(bg, cap)
        if getattr(self, "_cap_mob", None) is not None:
            self.remove(self._cap_mob)
        self.add(group)
        self._cap_mob = group

    def _write_srt(self, path="videos/GnbMath_narration.srt"):
        import pathlib

        def fmt(t):
            ms = int(round(t * 1000))
            h, ms = divmod(ms, 3_600_000)
            m, ms = divmod(ms, 60_000)
            s, ms = divmod(ms, 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        blocks = []
        for i, (start, text) in enumerate(self.subs):
            end = self.subs[i + 1][0] if i + 1 < len(self.subs) else float(self.time)
            blocks.append(f"{i + 1}\n{fmt(start)} --> {fmt(end)}\n{text}\n")
        pathlib.Path(path).write_text("\n".join(blocks), encoding="utf-8")

    # -- beats -----------------------------------------------------------------
    def model(self):
        self.section("The measurement model")
        self.narrate("From each known spot, two readings point at the tower.")
        # Tiny geometry inset: anchor a_i, unknown x, slant line, elevation angle.
        a = Dot(LEFT * 3 + DOWN * 1.2, color=C_POINT).set_stroke(WHITE, 1)
        x = Dot(RIGHT * 2.2 + UP * 1.3, color=C_GNB).set_stroke(WHITE, 1)
        a_lab = Tex("a_i", font_size=34).next_to(a, DOWN, buff=0.15)
        x_lab = Tex("x", font_size=34, color=C_GNB).next_to(x, UP, buff=0.15)
        horiz = Line(a.get_center(), RIGHT * 2.2 + DOWN * 1.2, color=GREY_B)
        slant = Line(a.get_center(), x.get_center(), color=C_RANGE, stroke_width=4)
        d_lab = Tex("d_i", font_size=32, color=C_RANGE).next_to(slant.get_center(), UL, buff=0.05)
        ang = Arc(start_angle=0, angle=slant.get_angle(), radius=0.7, arc_center=a.get_center(), color=C_ELEV)
        th_lab = Tex(r"\theta_i", font_size=32, color=C_ELEV).next_to(ang, RIGHT, buff=0.1)
        geo = VGroup(horiz, slant, ang, a, x, a_lab, x_lab, d_lab, th_lab)
        geo.shift(DOWN * 0.3)
        self.play(ShowCreation(slant), FadeIn(a), FadeIn(x), FadeIn(a_lab), FadeIn(x_lab), run_time=1.0)
        self.play(ShowCreation(horiz), ShowCreation(ang), FadeIn(d_lab), FadeIn(th_lab), run_time=1.0)
        self.wait(0.4)

        eqs = VGroup(
            Tex(r"\lVert  x - a_i  \rVert = d_i"),
            Tex(r"\varepsilon_i(x) = \theta_i"),
        )
        eqs.arrange(DOWN, buff=0.4, aligned_edge=LEFT).to_edge(RIGHT, buff=1.0).shift(UP * 0.2)
        r_tag = Text("slant range (no bearing)", font_size=20, color=C_RANGE).next_to(eqs[0], DOWN, buff=0.1, aligned_edge=LEFT)
        e_tag = Text("elevation angle", font_size=20, color=C_ELEV).next_to(eqs[1], DOWN, buff=0.1, aligned_edge=LEFT)
        self.narrate("Distance — but no direction.")
        self.play(Write(eqs[0]), FadeIn(r_tag), run_time=1.0)
        self.narrate("Elevation: how far up we tilt to aim at it.")
        self.play(Write(eqs[1]), FadeIn(e_tag), run_time=1.0)
        self.wait(1.0)
        self.play(FadeOut(geo), FadeOut(eqs), FadeOut(r_tag), FadeOut(e_tag), run_time=0.6)

    def cost(self):
        self.section("Maximum-likelihood = weighted least squares")
        self.narrate("Score a guess by how badly it misses every reading.")
        cost = Tex(
            r"\min_{x}\ \sum_i \left(\frac{\lVert x-a_i \rVert-d_i}{\sigma_d}\right)^{2}"
            r"\;+\;\sum_i \left(\frac{\varepsilon_i(x)-\theta_i}{\sigma_\theta}\right)^{2}",
        )
        cost.set_width(min(cost.get_width(), 12.5))
        cost.move_to(ORIGIN)
        self.play(Write(cost), run_time=1.8)
        self.wait(0.4)
        # Brace + annotate the two halves.
        sig = Tex(r"\sigma_d = 1.0\,\text{m}, \quad \sigma_\theta = 0.3^\circ",
                  t2c={r"\sigma_d": C_RANGE, r"\sigma_\theta": C_ELEV}, font_size=34)
        sig.next_to(cost, DOWN, buff=0.8)
        note = Text("divide by σ → each reading weighted by its precision",
                    font_size=24, color=GREY_B).next_to(sig, DOWN, buff=0.35)
        self.narrate("Divide each miss by the sensor's error, so distance and angle count fairly.")
        self.play(FadeIn(sig, shift=0.2 * UP), run_time=0.8)
        self.play(FadeIn(note), run_time=0.6)
        self.wait(1.2)
        self.play(FadeOut(sig), FadeOut(note), cost.animate.scale(0.8).to_edge(UP, buff=1.1), run_time=0.8)
        self.cost_eq = cost

    def nonconvex(self):
        self.section("Problem: the range cost is non-convex", C_SEED)
        self.narrate("One range = a whole circle.")
        term = Tex(r"\big(\,\lVert x-a_i \rVert - d_i\,\big)^{2}", t2c={"d_i": C_RANGE})
        term.next_to(self.cost_eq, DOWN, buff=0.5)
        self.play(FadeOut(self.cost_eq), Write(term), run_time=1.0)

        # 1-D slice of the cost: an asymmetric double well -> two basins.
        axes = Axes(
            x_range=(-1.8, 1.8, 1.0), y_range=(0, 1.6, 1.0),
            width=8.5, height=3.6,
            axis_config=dict(stroke_color=GREY_D, stroke_width=1.5, include_tip=False),
        )
        axes.move_to(0.4 * DOWN)             # fixed, lifted clear of the subtitle row
        # Tilt so the TRUE gNB is the deeper, global minimum (the one SR-LS
        # finds); the wrong basin is a shallower local minimum.
        f = lambda t: 0.55 * (t * t - 1) ** 2 - 0.18 * t + 0.35
        graph = self.curve(axes, f, -1.5, 1.5, C_SEED)
        xlab = Text("gNB position along a line", font_size=20, color=GREY_B)
        xlab.next_to(axes, DOWN, buff=0.15)
        self.narrate("Clustered spots make the cost bumpy — two valleys: a real one and a ghost.")
        self.play(ShowCreation(axes), FadeIn(xlab), run_time=0.8)
        self.play(ShowCreation(graph), run_time=1.4)

        # Mark the two minima.
        left = Dot(axes.c2p(-0.95, f(-0.95)), color=C_SEED)
        right = Dot(axes.c2p(0.95, f(0.95)), color=C_GNB)
        l_tag = Text("wrong basin", font_size=20, color=C_SEED).next_to(left, UL, buff=0.05)
        r_tag = Text("true gNB (global min)", font_size=20, color=C_GNB).next_to(right, UR, buff=0.05)
        self.play(FadeIn(left, scale=0.5), FadeIn(right, scale=0.5), FadeIn(l_tag), FadeIn(r_tag), run_time=0.9)
        self.wait(0.6)
        # The subtitle now carries this punch line, so no on-canvas duplicate.
        self.narrate("A naive hill-climbing solver can slide into the wrong valley.")
        self.wait(1.8)
        self.nc_group = VGroup(term, axes, graph, xlab, left, right, l_tag, r_tag)
        self.play(FadeOut(self.nc_group), run_time=0.6)

    def squared_range(self):
        self.section("Fix: square the ranges → it becomes linear", C_ALPHA)
        self.narrate("The fix: work with the distances squared.")
        s1 = Tex(r"\lVert  x - a_i  \rVert = d_i")
        s2 = Tex(r"\lVert  x - a_i  \rVert^{2} = d_i^{2}")
        s3 = Tex(r"\lVert x \rVert^{2} - 2\,a_i^{\top} x + \lVert a_i \rVert^{2} = d_i^{2}")
        for s in (s1, s2, s3):
            s.move_to(UP * 1.2)
        self.play(Write(s1), run_time=0.8)
        self.wait(0.3)
        self.play(TransformMatchingTex(s1, s2), run_time=1.0)
        self.wait(0.3)
        self.play(TransformMatchingTex(s2, s3), run_time=1.2)
        self.wait(0.4)

        # Highlight the lone nonlinearity ||x||^2 and substitute alpha.
        box = SurroundingRectangle(s3[:4], color=C_ALPHA, buff=0.05)
        sub = Tex(r"\alpha \equiv \lVert x \rVert^{2}").set_color(C_ALPHA).next_to(s3, DOWN, buff=0.7)
        self.narrate("Only one term stays curvy — rename it as a helper called alpha.")
        self.play(ShowCreation(box), run_time=0.5)
        self.play(FadeIn(sub, shift=0.2 * UP), run_time=0.7)
        self.wait(0.5)

        lin = Tex(r"-2\,a_i^{\top} x + \alpha = d_i^{2} - \lVert a_i \rVert^{2}")
        lin.next_to(sub, DOWN, buff=0.6)
        linnote = Text("linear in the unknowns (x, α)", font_size=24, color=GREY_B)
        linnote.next_to(lin, DOWN, buff=0.3)
        self.narrate("Now every equation is a straight line — solvable exactly.")
        self.play(Write(lin), run_time=1.0)
        self.play(FadeIn(linnote), run_time=0.5)
        self.wait(0.8)

        mat = Tex(r"A\,y = b, \qquad y = \begin{bmatrix} x \\ \alpha \end{bmatrix}",
                  t2c={r"\alpha": C_ALPHA})
        mat.move_to(ORIGIN)
        self.narrate("Stack them all into one linear system: A y = b.")
        self.play(
            FadeOut(s3), FadeOut(box), FadeOut(sub), FadeOut(linnote),
            ReplacementTransform(lin, mat),
            run_time=1.0,
        )
        rows = Tex(r"A_i = (-2\,a_i^{\top},\ 1), \quad b_i = d_i^{2} - \lVert a_i \rVert^{2}",
                   font_size=34, color=GREY_B)
        rows.next_to(mat, DOWN, buff=0.5)
        self.play(FadeIn(rows), run_time=0.7)
        self.wait(1.0)
        self.play(FadeOut(rows), mat.animate.to_edge(UP, buff=1.1).scale(0.85), run_time=0.8)
        self.mat_eq = mat

    def gtrs(self):
        self.section("A GTRS — solvable to global optimality", C_ALPHA)
        self.narrate("Minimize the miss, with one rule keeping alpha honest.")
        prob = Tex(
            r"\min_{y}\ \lVert A y - b \rVert^{2}",
            r"\quad\text{s.t.}\quad",
            r"y^{\top} D y + 2 f^{\top} y = 0",
        )
        prob.next_to(self.mat_eq, DOWN, buff=0.6)
        self.play(Write(prob), run_time=1.4)
        cons = Tex(r"y^{\top} D y + 2 f^{\top} y = \lVert x \rVert^{2} - \alpha = 0",
                   font_size=34, color=GREY_B)
        cons.next_to(prob, DOWN, buff=0.45)
        defs = Tex(r"D = \mathrm{diag}(I_3, 0), \quad f = [\,0,0,0,-\tfrac12\,]^{\top}",
                   font_size=32, color=GREY_B).next_to(cons, DOWN, buff=0.3)
        self.play(FadeIn(cons), run_time=0.8)
        self.play(FadeIn(defs), run_time=0.6)
        self.wait(1.2)

        sol = Tex(r"y(\lambda) = (A^{\top}A + \lambda D)^{-1}(A^{\top}b - \lambda f)")
        sol.next_to(defs, DOWN, buff=0.6)
        self.narrate("The solution is a formula with a single knob, lambda.")
        self.play(Write(sol), run_time=1.3)
        self.wait(1.0)
        self.play(
            FadeOut(prob), FadeOut(cons), FadeOut(defs), FadeOut(self.mat_eq),
            sol.animate.to_edge(UP, buff=1.1),
            run_time=0.8,
        )
        self.sol_eq = sol

    def bisection(self):
        self.section("One unknown λ, found by bisection")
        self.narrate("Turn the knob until the honesty rule reads exactly zero.")
        phi = Tex(r"\varphi(\lambda) = y(\lambda)^{\top} D\, y(\lambda) + 2 f^{\top} y(\lambda) = 0")
        phi.next_to(self.sol_eq, DOWN, buff=0.5)
        self.play(Write(phi), run_time=1.2)

        axes = Axes(
            x_range=(0, 3, 1), y_range=(-1.2, 2.2, 1),
            width=8.0, height=3.4,
            axis_config=dict(stroke_color=GREY_D, stroke_width=1.5, include_tip=False),
        )
        axes.next_to(phi, DOWN, buff=0.5)
        g = lambda l: 3.2 * np.exp(-1.6 * (l - 0.15)) - 1.0
        graph = self.curve(axes, g, 0.05, 2.95, C_RANGE)
        self.narrate("That measure only ever goes downhill, so it crosses zero just once.")
        self.play(ShowCreation(axes), run_time=0.6)
        self.play(ShowCreation(graph), run_time=1.2)

        # Root + bracket.
        root_x = 0.15 + (1 / 1.6) * np.log(3.2 / 1.0)  # where g=0
        root = Dot(axes.c2p(root_x, 0), color=C_GNB)
        vline = DashedLine(axes.c2p(root_x, -1.2), axes.c2p(root_x, 2.2), stroke_width=2, color=GREY_B)
        lam_lab = Tex(r"\lambda^{\star}", font_size=34, color=C_GNB).next_to(root, UR, buff=0.1)
        mono = Text("φ is strictly decreasing → unique root", font_size=24, color=GREY_B)
        mono.next_to(axes, DOWN, buff=0.2)
        self.narrate("Bisection pinpoints it: one guaranteed, global answer.")
        self.play(ShowCreation(vline), FadeIn(root, scale=0.5), FadeIn(lam_lab), run_time=0.8)
        self.play(FadeIn(mono), run_time=0.5)
        self.wait(1.4)
        self.bis_group = VGroup(phi, axes, graph, root, vline, lam_lab, mono, self.sol_eq)
        self.play(FadeOut(self.bis_group), run_time=0.7)

    def refine_and_cov(self):
        self.section("Refine, then quantify the uncertainty")
        seed = Text("SR-LS gives a globally-optimal seed  x₀", font_size=26, color=C_ALPHA)
        seed.to_edge(UP, buff=1.1)
        lm = Tex(r"x_{k+1} = x_k - (J^{\top}J + \mu I)^{-1} J^{\top} r(x_k)")
        lm.next_to(seed, DOWN, buff=0.5)
        lm_note = Text("Levenberg–Marquardt on the true weighted residuals  →  the MLE",
                       font_size=22, color=GREY_B).next_to(lm, DOWN, buff=0.3)
        self.narrate("Use that guaranteed answer as a perfect starting point.")
        self.play(FadeIn(seed, shift=0.2 * DOWN), run_time=0.6)
        self.narrate("Then nudge it to match the real distances and angles.")
        self.play(Write(lm), run_time=1.4)
        self.play(FadeIn(lm_note), run_time=0.5)
        self.wait(1.2)

        cov = Tex(r"\mathrm{Cov}(\hat{x}) \approx \hat{\sigma}^{2} (J^{\top}J)^{-1}, "
                  r"\quad \hat{\sigma}^{2} = \frac{\lVert r(\hat{x}) \rVert^{2}}{m-n}")
        cov.next_to(lm_note, DOWN, buff=0.7)
        self.narrate("Finally, measure how much the answer could wiggle.")
        self.play(Write(cov), run_time=1.4)
        self.wait(0.6)

        # Eigen-decomposition -> error ellipse, drawn live at true 6:1 aspect.
        ell = Ellipse(width=2 * ELLIPSE_MAJOR_M * 0.32, height=2 * ELLIPSE_MINOR_M * 0.32)
        ell.set_stroke(C_ELLIPSE, 3).set_fill(C_ELLIPSE, 0.18).rotate(40 * DEGREES)
        ell.next_to(cov, DOWN, buff=0.7)
        ax_lab = Tex(r"\sqrt{\lambda_1}\times\sqrt{\lambda_2} = 4.4\,\text{m}\times 0.7\,\text{m}",
                     font_size=32, color=C_ELLIPSE).next_to(ell, RIGHT, buff=0.6)
        self.narrate("Long and thin: distance is pinned down, sideways stays fuzzy.")
        self.play(ShowCreation(ell), FadeIn(ax_lab), run_time=1.2)
        why = Text("elongated: ranges fix the radius, clustered anchors leave azimuth weak",
                   font_size=20, color=GREY_B).next_to(ell, DOWN, buff=0.35)
        self.play(FadeIn(why), run_time=0.6)
        self.wait(1.6)
        self.rc_group = VGroup(seed, lm, lm_note, cov, ell, ax_lab, why)
        self.play(FadeOut(self.rc_group), run_time=0.7)

    def recap(self):
        self.section("The two-stage design")
        self.narrate("Global where the math is easy; local where it must be precise.")
        chips = VGroup(
            VGroup(Dot(color=C_ALPHA), Text("SR-LS / GTRS", font_size=26, color=C_ALPHA),
                   Text("global, closed-form", font_size=20, color=GREY_B)),
            VGroup(Dot(color=C_RANGE), Text("Levenberg–Marquardt", font_size=26, color=C_RANGE),
                   Text("local, accurate (MLE)", font_size=20, color=GREY_B)),
            VGroup(Dot(color=C_ELLIPSE), Text("Covariance", font_size=26, color=C_ELLIPSE),
                   Text("honest 1σ ellipse", font_size=20, color=GREY_B)),
        )
        for row in chips:
            row.arrange(RIGHT, buff=0.3, aligned_edge=ORIGIN)
        chips.arrange(DOWN, buff=0.6, aligned_edge=LEFT).move_to(ORIGIN)
        line = Text("global where convexifiable · local where accurate",
                    font_size=24, color=GREY_B).next_to(chips, DOWN, buff=0.7)
        for row in chips:
            self.play(FadeIn(row, shift=0.2 * RIGHT), run_time=0.6)
        self.play(Write(line), run_time=1.0)
        self.wait(2.5)


# =============================================================================
#  Interstitial divider, used when stitching the two parts into one film.
# =============================================================================
class Divider(Scene):
    def construct(self):
        part = Text("PART II", font_size=30, color=C_SEED, weight=BOLD)
        title = Text("The Mathematics", font_size=64, weight=BOLD)
        sub = Text("from rangefinder readings to a covariance ellipse",
                   font_size=28, color=GREY_B)
        part.next_to(title, UP, buff=0.45)
        sub.next_to(title, DOWN, buff=0.45)
        rule = Line(LEFT, RIGHT, color=GREY_D).set_width(title.get_width() + 1.0)
        rule.next_to(sub, DOWN, buff=0.45)
        self.play(FadeIn(part, shift=0.2 * DOWN), Write(title), run_time=1.2)
        self.play(FadeIn(sub, shift=0.2 * UP), ShowCreation(rule), run_time=0.8)
        self.wait(1.6)
        self.play(*[FadeOut(m) for m in (part, title, sub, rule)], run_time=0.7)
        self.wait(0.2)
