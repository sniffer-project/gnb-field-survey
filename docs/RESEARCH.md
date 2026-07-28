# The Math of gNB Triangulation: Research Report

*Generated: 2026-06-29 | Sources: 18 | Confidence: High*

Validates (and stress-tests) the method used in this `claude/` build: weighted
nonlinear least-squares position estimation from rangefinder distance +
elevation, with no azimuth.

## Executive Summary

Everything we implemented is textbook-standard **range-based source
localization**. The cost function (sum of squared range residuals), the
Levenberg–Marquardt solver, the multi-start to escape local minima, the
`(JᵀJ)⁻¹·σ²` covariance, and the error ellipse are each the canonical approach
in the GNSS / sensor-network / robotics literature. Two findings matter most:
(1) the **multi-start was not optional** — range localization is genuinely
non-convex and single-start solvers provably converge to wrong minima; and
(2) the elongated error ellipse and the left/right ambiguity are a **named,
well-understood geometric effect** (the baseline line-of-symmetry / flip
ambiguity), whose textbook fix is exactly the azimuth reading we recommended.
A stronger alternative to multi-start also exists: closed-form *globally
optimal* trilateration via a squared-range reformulation (Beck SR-LS / the
eigenvalue method).

---

## 1. The core formulation is canonical

Our `solver.py` minimizes, over the gNB position **x̃**, the squared range
residuals. This is verbatim the standard "location from range measurements"
nonlinear least-squares (NLLS) problem:

> minimize Σᵢ (‖x̃ − aᵢ‖ − ρᵢ)²,  with residual fᵢ(x) = ‖x − aᵢ‖ − ρᵢ

— Vandenberghe, *ECE133A Nonlinear Least Squares*, UCLA, lecture 13.2–13.3
([UCLA notes](https://www.seas.ucla.edu/~vandenbe/133A/lectures/nlls.pdf)).
The same formulation appears in GNSS trilateration ([TU Delft MUDE
textbook](https://mude.citg.tudelft.nl/book/2025/observation_theory/07_Notebook_NLSQ.html))
and UWB/IoT localization ([Beuchat et al., IEEE IoT-J
2019](https://doi.org/10.1109/jiot.2019.2904559)).

Solving it with **Levenberg–Marquardt** (our `scipy ... method="lm"`) is the
recommended default: LM regularizes the Gauss–Newton step so it works "when
columns of the Jacobian are linearly dependent" and "when the Gauss–Newton
update does not reduce ‖f(x)‖²" (UCLA, 13.18) — i.e. exactly the ill-conditioned
clustered-geometry case we hit. Gauss–Newton/LM is "well suited for solving
(small residual) non-linear problems and most commonly applied in positioning"
([Yan, Tiberius et al., IEEE/ION PLANS 2008](https://doi.org/10.1109/plans.2008.4569986)).

**Our elevation residual** adds an angle constraint per point. This matches the
GNSS design-matrix convention, where each measurement row in the local ENU frame
is `[cos(el)·sin(az), cos(el)·cos(az), sin(el), 1]`
([Navipedia, *Positioning Error*](https://gssc.esa.int/navipedia/index.php?title=Positioning_Error),
footnote 2) — elevation and azimuth are the natural angular observables.

## 2. The local-minima problem is real — multi-start was necessary

This is the single most important validation. Range-based NLLS is **non-convex**
and has genuine local minima; a single starting point can converge to the wrong
one:

- UCLA's worked 5-anchor example: starting at (1.8, 3.5) and (3.0, 1.5) finds
  the true minimum (1.18, 0.82), but **"started at (2.2, 3.5) converges to a
  non-optimal point"** (UCLA, 13.22). This is precisely the failure our
  noise-free synthetic test reproduced before multi-start was added.
- "The non-linear inverse problem possibly features local minima next to the
  sought-for global one, and the position estimator is inherently biased …
  extra care needs to be taken" — and the paper's remedy is literally a scheme
  "to obtain a good initial guess" ([Yan et al.,
  2008](https://doi.org/10.1109/plans.2008.4569986)).
- "In the absence of a good initial guess, commonly used iterative solvers can
  get stuck in these local minima resulting in poor estimation accuracy"
  ([Range-Only Trajectory Estimation, arXiv:2309.09011](https://arxiv.org/html/2309.09011v2)).
- "Solution quality is effectively determined by which basin the NLS solver is
  initialized within" ([MIT 16.485, *Least Squares Optimization*
  notes](https://vnav.mit.edu/material/17-18-NonLinearLeastSquares-notes.pdf)).

Our ring of 24 azimuth seeds is a standard "sample multiple basins, keep the
lowest cost" strategy that directly targets this.

## 3. The elongated ellipse + L/R ambiguity is a named geometric effect

The two distinctive features of our results — a very stretched error ellipse and
an inherent left/right ambiguity without azimuth — are well documented:

- **Baseline line-of-symmetry / flip ambiguity.** "The baseline containing the
  centers of the circles is a line of symmetry. The correct and ambiguous
  solutions are perpendicular to and equally distant from (on opposite sides of)
  the baseline" ([Wikipedia, *True-range
  multilateration*](https://en.wikipedia.org/wiki/True_range_multilateration)).
  The recommended resolver: "a crude measurement of vehicle heading is
  sufficient" — i.e. **one bearing/azimuth**, exactly our future-survey
  recommendation. The phenomenon is also called *flip ambiguity*: "a kind of
  mirror is created to reflect positions … in noisy channels"
  ([Sensors 2017, robust UWB trilateration](https://www.mdpi.com/1424-8220/17/4/795)).
- **Clustered ≈ near-collinear = ill-conditioned.** "The accuracy of LS and WLS
  significantly degrades when the anchors are approaching collinear … because
  these algorithms involve matrix inversions which inject significant error when
  the matrix is ill-conditioned. The best performance is given when anchor nodes
  are well separated around the target" ([Hadzic, *RSS-based Near-Collinear
  Anchor Positioning*](https://exa.ai/library/publication/v16ghgpx51r)). The
  collinear case is literally called the "pathological" case. Our points span
  only ~30–80 m versus 80–290 m range, so the perpendicular (cross-range)
  direction is poorly observed — exactly the long axis of our ellipse.

This is **GDOP** (Geometric Dilution of Precision): "GDOP is the error gain …
errors in position are usually GDOP multiplied by measurement error; a smaller
GDOP results in a more exact position"
([Kumar et al., 2022](https://doi.org/10.1155/2022/6772077)).

## 4. The covariance and error ellipse are computed the standard way

Our `(JᵀJ)⁻¹ · (RSS/dof)` covariance is the established estimator:

- Unweighted: `P = σ²(GᵀG)⁻¹`; weighted: `P = (GᵀR⁻¹G)⁻¹`
  ([Navipedia](https://gssc.esa.int/navipedia/index.php?title=Positioning_Error),
  eqs. 1, 8). The general weighted form is
  `Q = (Jₓᵀ(J_d C_d J_dᵀ)⁻¹ Jₓ)⁻¹`
  ([Wikipedia, *Dilution of precision*](https://en.wikipedia.org/wiki/Dilution_of_precision_(navigation))).
- The TU Delft notebook computes it identically:
  `Sigma_x_hat = inv(J.T @ inv_Sigma_y @ J)`
  ([MUDE](https://mude.citg.tudelft.nl/book/2025/observation_theory/07_Notebook_NLSQ.html)).
- **Error ellipse semi-axes** are the eigenvalues of the 2×2 horizontal
  covariance block — equivalently Navipedia eq. 6:
  `σ_major = sqrt((P_ee+P_nn)/2 + sqrt(((P_ee−P_nn)/2)² + P_en²))`. Our code
  takes the eigen-decomposition of that block, which yields the same axes.
- **Weighting "happens automatically."** Dividing residuals by σ_d and σ_θ (our
  approach) is the standard mechanism: "As R is the covariance of measurement
  errors, this weighting of the measurements happens automatically within the
  least-squares process" ([Inside GNSS, *How measurement errors
  propagate*](https://www.insidegnss.com/wp-content/uploads/2018/01/IGM_julaug14-solutions.pdf)).

The `(JᵀJ)⁻¹σ²` covariance is also the inverse Fisher information / **Cramér–Rao
lower bound** approximation for the estimate
([CRLB for range systems, multiple sources](https://www.mdpi.com/2076-3417/13/3/2008)) —
so our reported σ's are the best-case achievable accuracy for this geometry.

## 5. Stronger alternative: closed-form *globally optimal* trilateration

Our multi-start gives high confidence of finding the global optimum, but does
not *guarantee* it. Two lines of work do, by reformulating in **squared ranges**:

- **SR-LS (squared-range least squares).** Despite nonconvexity, the squared-
  range problem "can be solved globally and efficiently after transforming it
  into a quadratic minimization with a single quadratic constraint" — an exact
  procedure, no iteration, no initial guess ([Beck, Stoica & Li, *Exact and
  Approximate Solutions of Source Localization Problems*, IEEE TSP
  2008](https://doi.org/10.1109/tsp.2007.909342); [Beck, Teboulle, Chikishev,
  SIAM J. Optim. 2008](https://doi.org/10.1137/070698014)).
- **Eigenvalue method.** "The globally optimal solution corresponds to the
  largest real eigenvalue" — fast, numerically stable, handles degenerate cases
  ([Larsson et al., *Single-Source Localization as an Eigenvalue Problem*,
  arXiv:2502.18135, 2025](https://arxiv.org/pdf/2502.18135); their earlier
  *Optimal Trilateration is an Eigenvalue Problem*, ICASSP 2019).

Note: SR-LS optimizes squared-distance residuals, which is "no longer optimal
under additive Gaussian noise on the distance"
([Frisch, MFI 2025](https://isas.iar.kit.edu/pdf/MFI25_Frisch.pdf)). Common
practice: use SR-LS/eigenvalue as a **guaranteed-global initializer**, then one
Gauss–Newton/LM refinement on the true (unsquared) residuals — combining global
optimality with the correct noise model. That would make our `_initial_guesses`
ring redundant and remove any residual local-minimum risk.

## Key Takeaways

1. **The implementation is methodologically sound** — it matches the standard
   GNSS/sensor-network NLLS localization pipeline end to end.
2. **Multi-start was required, not defensive.** Range NLLS provably has local
   minima; textbook examples converge to wrong points from bad seeds. Keep it
   (or replace with a closed-form global initializer).
3. **The big error ellipse is physics, not a bug.** Clustered (near-collinear)
   points = high GDOP = weak cross-range observability. Reporting the ellipse is
   the honest thing to do.
4. **One azimuth reading is the literature-endorsed fix** for the baseline flip
   ambiguity and the dominant cross-range uncertainty. Strongest single
   improvement for future surveys.
5. **Optional upgrade:** swap the 24-seed multi-start for Beck SR-LS or the
   eigenvalue trilateration to *guarantee* the global optimum, then LM-refine.

## Sources

1. [UCLA ECE133A — Nonlinear Least Squares](https://www.seas.ucla.edu/~vandenbe/133A/lectures/nlls.pdf) — canonical range-localization NLLS + LM; local-minima example.
2. [TU Delft MUDE — Gauss-Newton GNSS Trilateration notebook](https://mude.citg.tudelft.nl/book/2025/observation_theory/07_Notebook_NLSQ.html) — identical Jacobian + covariance code.
3. [Navipedia — Positioning Error](https://gssc.esa.int/navipedia/index.php?title=Positioning_Error) — formal covariance, error-ellipse formula, ENU design matrix, DOP.
4. [Wikipedia — True-range multilateration](https://en.wikipedia.org/wiki/True_range_multilateration) — baseline symmetry / ambiguity, HDOP geometry.
5. [Wikipedia — Dilution of precision](https://en.wikipedia.org/wiki/Dilution_of_precision_(navigation)) — Q=(AᵀA)⁻¹, weighted general form, GDOP/PDOP.
6. [Yan, Tiberius et al., IEEE/ION PLANS 2008](https://doi.org/10.1109/plans.2008.4569986) — feasibility of Gauss-Newton indoor positioning; local minima, bias, initial-guess schemes.
7. [Range-Only Trajectory Estimation, arXiv:2309.09011](https://arxiv.org/html/2309.09011v2) — non-convex cost, need for good init, SDP relaxations.
8. [MIT 16.485 — Least Squares Optimization notes](https://vnav.mit.edu/material/17-18-NonLinearLeastSquares-notes.pdf) — basins of convergence, initialization.
9. [Beck, Stoica & Li, IEEE TSP 2008 — Exact/Approximate Source Localization](https://doi.org/10.1109/tsp.2007.909342) — SR-LS global solution.
10. [Beck, Teboulle, Chikishev, SIAM J. Optim. 2008](https://doi.org/10.1137/070698014) — globally solvable single-source localization.
11. [Larsson et al., Single-Source Localization as an Eigenvalue Problem, arXiv:2502.18135 (2025)](https://arxiv.org/pdf/2502.18135) — global optimum = largest eigenvalue; degenerate cases.
12. [Hadzic — RSS-based Near-Collinear Anchor Positioning](https://exa.ai/library/publication/v16ghgpx51r) — collinear/clustered ill-conditioning; anchor placement.
13. [Sensors 2017 — Robust UWB Trilateration](https://www.mdpi.com/1424-8220/17/4/795) — two-intersection uncertainty, flip ambiguity.
14. [Kumar et al., 2022 — GPS DOP analysis](https://doi.org/10.1155/2022/6772077) — GDOP as error gain.
15. [Inside GNSS — How measurement errors propagate](https://www.insidegnss.com/wp-content/uploads/2018/01/IGM_julaug14-solutions.pdf) — automatic weighting via R; geometry vs accuracy.
16. [Beuchat et al., IEEE IoT-J 2019](https://doi.org/10.1109/jiot.2019.2904559) — NLLS UWB localization, approximate anchor positions.
17. [Frisch, MFI 2025](https://isas.iar.kit.edu/pdf/MFI25_Frisch.pdf) — squared-range reformulation is non-optimal under Gaussian range noise.
18. [MATEC 2016 — Location ambiguity, GDOP, station layout](https://www.matec-conferences.org/articles/matecconf/pdf/2016/07/matecconf_iceice2016_01036.pdf) — two-intersection ambiguity vs station layout.

## Methodology

Searched 5 query clusters across Exa and Firecrawl (web + academic): NLLS range
formulation, range-only local minima / closed-form initialization, GDOP /
covariance / error ellipse, CRLB for range localization, and trilateration
ambiguity / collinear geometry. ~30 sources screened, 18 retained; two primary
sources (UCLA NLLS notes, Navipedia Positioning Error) read in full for exact
formulas. Sub-questions: (1) is the NLLS formulation standard? (2) are local
minima real and is multi-start justified? (3) how should covariance/ellipse be
computed? (4) is the no-azimuth ambiguity a known effect with a known fix?
(5) is there a better/global method?
