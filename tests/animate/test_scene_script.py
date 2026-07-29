"""The standalone scene validates JSON before it needs ManimGL."""

from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest


def test_invalid_scene_data_exits_clearly_before_importing_manimgl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scene_json = tmp_path / "malformed.json"
    scene_json.write_text(
        json.dumps(
            {
                "schema": 1,
                "survey": "x",
                "origin": {"lat": 0.0, "lon": 0.0, "alt_m": 0.0},
                "points": [
                    {
                        "label": "Pt1",
                        "e": 0.0,
                        "n": 0.0,
                        "dist_m": 1.0,
                        "elev_deg": 0.0,
                    }
                ],
                "gnb_en": [0.0, 0.0],
                "srls_seed_en": [],
                "ellipse": {
                    "major_m": 1.0,
                    "minor_m": 1.0,
                    "azimuth_deg": None,
                },
                "result_lines": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GNB_SCENE_JSON", str(scene_json))
    scene_file = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "animation"
        / "triangulate_scene.py"
    )

    with pytest.raises(SystemExit, match="srls_seed_en"):
        runpy.run_path(str(scene_file))
