"""Squared-Range Least Squares (SR-LS): a globally optimal position seed.

The plain range cost ``Σ(‖x − aᵢ‖ − dᵢ)²`` is non-convex and traps iterative
solvers in local minima. Beck, Stoica & Li (IEEE TSP 2008) show that the
*squared*-range cost ``Σ(‖x − aᵢ‖² − dᵢ²)²`` can be solved to global optimality
by introducing α = ‖x‖² and recognising the result as a Generalised Trust
Region Subproblem (GTRS):

    minimise ‖A y − b‖²   subject to   yᵀ D y + 2 fᵀ y = 0

with y = [x; α], rows of A = [−2 aᵢᵀ, 1], b_i = dᵢ² − ‖aᵢ‖²,
D = diag(I_n, 0) and f = [0, …, 0, −1/2]. The solution is
y(λ) = (AᵀA + λD)⁻¹(Aᵀb − λf), where λ is the unique root of
φ(λ) = y(λ)ᵀ D y(λ) + 2 fᵀ y(λ) = 0 on the interval where (AᵀA + λD) ≻ 0.
φ is strictly decreasing there, so a bisection finds the global solution with
no initial guess.

We use this purely to *seed* the full weighted distance+elevation refinement.
"""

from __future__ import annotations

import numpy as np
from scipy.linalg import eigh


def srls_position(anchors: np.ndarray, ranges: np.ndarray) -> np.ndarray:
    """Globally optimal SR-LS estimate of the source position.

    Args:
        anchors: (m, n) known point coordinates (ENU metres), n = 2 or 3.
        ranges:  (m,) measured slant distances to the source.

    Returns:
        (n,) estimated source position.

    Raises:
        ValueError: if the geometry is degenerate (AᵀA singular).
    """
    anchors = np.asarray(anchors, dtype=float)
    ranges = np.asarray(ranges, dtype=float)
    m, n = anchors.shape

    A = np.hstack([-2.0 * anchors, np.ones((m, 1))])
    b = ranges ** 2 - np.sum(anchors ** 2, axis=1)
    D = np.zeros((n + 1, n + 1))
    D[:n, :n] = np.eye(n)
    f = np.zeros(n + 1)
    f[-1] = -0.5

    G = A.T @ A
    Atb = A.T @ b
    if np.linalg.cond(G) > 1e12:
        raise ValueError("degenerate anchor geometry for SR-LS")

    # AᵀA + λD ≻ 0  ⟺  λ > −1/γ_max, where γ are the generalised eigenvalues
    # of D x = γ G x.
    gen_eigs = eigh(D, G, eigvals_only=True)
    gamma_max = float(np.max(gen_eigs))
    if not np.isfinite(gamma_max) or gamma_max <= 0:
        raise ValueError("no valid GTRS interval for SR-LS")
    lambda_low = -1.0 / gamma_max

    def y_of(lam: float) -> np.ndarray:
        return np.linalg.solve(G + lam * D, Atb - lam * f)

    def phi(lam: float) -> float:
        y = y_of(lam)
        return float(y @ D @ y + 2.0 * f @ y)

    # Bracket the root just above lambda_low (where φ → +∞) and at a large λ
    # (where φ < 0), then bisect the strictly-decreasing φ.
    eps = 1e-6 * (abs(lambda_low) + 1.0)
    lo = lambda_low + eps
    while phi(lo) <= 0 and lo - lambda_low > 1e-15:
        lo = lambda_low + (lo - lambda_low) * 0.5
    hi = lo + 1.0
    for _ in range(200):
        if phi(hi) < 0:
            break
        hi = lambda_low + (hi - lambda_low) * 2.0

    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if phi(mid) > 0:
            lo = mid
        else:
            hi = mid

    return y_of(0.5 * (lo + hi))[:n]
