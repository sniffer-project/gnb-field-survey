"""Solve-then-render must use the same scene filename at both ends."""

from __future__ import annotations

import argparse
from pathlib import Path

from gnb_survey.cli import actions
from gnb_survey.triangulate.discovery import SurveyFiles


def test_animate_with_a_report_name_uses_the_stable_survey_scene_path(
    tmp_path: Path, monkeypatch
) -> None:
    files = SurveyFiles(
        name="20260716",
        mappro=tmp_path / "survey.csv",
        exports=(),
        binoc=tmp_path / "sightings.xlsx",
    )
    args = argparse.Namespace(
        name="Cetran",
        scene="GnbTriangulation",
        quality="low",
    )
    rendered: dict[str, Path] = {}

    def fake_solve(*_args, output_dir, **_kwargs):
        (output_dir / "20260716_scene.json").write_text("{}", encoding="utf-8")
        return 0

    def fake_render(**kwargs):
        rendered["scene_json"] = kwargs["scene_json"]
        return 0

    monkeypatch.setattr(actions, "do_solve", fake_solve)
    monkeypatch.setattr(actions.runner, "render", fake_render)

    code = actions.do_animate(
        files,
        args,
        output_dir=tmp_path,
        output_fn=lambda _: None,
    )

    assert code == 0
    assert rendered["scene_json"] == tmp_path / "20260716_scene.json"
