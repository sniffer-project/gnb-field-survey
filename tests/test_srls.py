"""SR-LS global initializer recovers the source without any initial guess."""

import math

import numpy as np
import pytest

from gnb_triangulate.srls import srls_position


def _anchors_3d():
    # Non-coplanar anchors so the 3-D range problem is well posed.
    return np.array(
        [
            [0.0, 0.0, 0.0],
            [50.0, 0.0, 2.0],
            [0.0, 60.0, -1.0],
            [40.0, 55.0, 3.0],
            [10.0, 20.0, 30.0],
        ]
    )


def test_recovers_source_noise_free():
    anchors = _anchors_3d()
    true = np.array([12.0, 34.0, 25.0])
    ranges = np.linalg.norm(anchors - true, axis=1)
    est = srls_position(anchors, ranges)
    assert np.linalg.norm(est - true) < 1e-4


def test_global_regardless_of_geometry_offset():
    anchors = _anchors_3d() + np.array([1000.0, -500.0, 5.0])  # translate far away
    true = np.array([1012.0, -466.0, 30.0])
    ranges = np.linalg.norm(anchors - true, axis=1)
    est = srls_position(anchors, ranges)
    assert np.linalg.norm(est - true) < 1e-3


def test_robust_to_small_noise():
    rng = np.random.default_rng(1)
    anchors = _anchors_3d()
    true = np.array([12.0, 34.0, 25.0])
    errs = []
    for _ in range(20):
        ranges = np.linalg.norm(anchors - true, axis=1) + rng.normal(0, 0.5, len(anchors))
        est = srls_position(anchors, ranges)
        errs.append(np.linalg.norm(est - true))
    assert np.median(errs) < 3.0


def test_degenerate_geometry_raises():
    # All anchors collinear -> AᵀA ill-conditioned -> SR-LS should refuse.
    anchors = np.array([[float(i), 0.0, 0.0] for i in range(5)])
    true = np.array([2.0, 0.0, 0.0])
    ranges = np.linalg.norm(anchors - true, axis=1)
    with pytest.raises(ValueError):
        srls_position(anchors, ranges)
