"""The runner builds a correct manimgl command and fails helpfully without it."""

from __future__ import annotations

from pathlib import Path

import pytest

from gnb_survey.animate import availability, runner


def test_argv_uses_the_documented_flags():
    argv = runner.build_argv(
        scene_file=Path("/p/docs/animation/trilaterate_scene.py"),
        scene_name="GnbTrilateration",
        quality="hd",
        video_dir=Path("/p/data/output"),
    )

    assert argv[0] == "manimgl"
    assert argv[1] == "/p/docs/animation/trilaterate_scene.py"
    assert argv[2] == "GnbTrilateration"
    assert "-w" in argv
    assert "--hd" in argv
    assert "--video_dir" in argv
    assert argv[argv.index("--video_dir") + 1] == "/p/data/output"


@pytest.mark.parametrize(
    "quality,flag",
    [("low", "-l"), ("medium", "-m"), ("hd", "--hd"), ("uhd", "--uhd")],
)
def test_every_quality_maps_to_a_real_flag(quality, flag):
    argv = runner.build_argv(
        scene_file=Path("/s.py"),
        scene_name="GnbMath",
        quality=quality,
        video_dir=Path("/out"),
    )
    assert flag in argv


def test_an_unknown_quality_is_refused():
    with pytest.raises(ValueError, match="quality"):
        runner.build_argv(
            scene_file=Path("/s.py"),
            scene_name="GnbMath",
            quality="cinematic",
            video_dir=Path("/out"),
        )


def test_missing_manimgl_raises_with_the_install_hint(tmp_path):
    scene_json = tmp_path / "s.json"
    scene_json.write_text("{}", encoding="utf-8")

    with pytest.raises(runner.ManimUnusable) as excinfo:
        runner.render(
            scene_json=scene_json,
            scene_name="GnbTrilateration",
            quality="hd",
            video_dir=tmp_path,
            output_fn=lambda _: None,
            runner_fn=None,
            renderer=availability.MISSING,
        )

    message = str(excinfo.value)
    assert "manimgl" in message
    assert "animation" in message


def test_a_manimgl_that_cannot_start_is_refused_before_it_is_spawned(tmp_path):
    """Spawning it would only reprint the traceback the probe already read."""
    scene_json = tmp_path / "s.json"
    scene_json.write_text("{}", encoding="utf-8")
    spawned: list[list[str]] = []

    with pytest.raises(runner.ManimUnusable) as excinfo:
        runner.render(
            scene_json=scene_json,
            scene_name="GnbTrilateration",
            quality="hd",
            video_dir=tmp_path,
            output_fn=lambda _: None,
            runner_fn=lambda argv, env: spawned.append(argv) or 0,
            renderer=availability.broken("ModuleNotFoundError: no 'pyaudioop'"),
        )

    assert spawned == []
    message = str(excinfo.value)
    assert "pyaudioop" in message
    assert "animation" in message


def test_render_passes_the_scene_path_through_the_environment(tmp_path):
    scene_json = tmp_path / "s.json"
    scene_json.write_text("{}", encoding="utf-8")
    seen: dict = {}

    def fake_runner(argv, env):
        seen["argv"] = argv
        seen["env"] = env
        return 0

    code = runner.render(
        scene_json=scene_json,
        scene_name="GnbTrilateration",
        quality="low",
        video_dir=tmp_path,
        output_fn=lambda _: None,
        runner_fn=fake_runner,
        renderer=availability.READY,
    )

    assert code == 0
    assert seen["env"][runner.SCENE_ENV] == str(scene_json)
    assert "-l" in seen["argv"]
