"""Invoke manimgl on the scene file, pointing it at one survey's scene data.

manimgl has no mechanism for forwarding unrecognised arguments to the Scene
being rendered -- its own argparse rejects them -- so the scene path travels
in an environment variable instead. Flags below are from manimgl's documented
CLI: -w (write file), -l/-m/--hd/--uhd (quality), --video_dir.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable

MANIM_BINARY: str = "manimgl"
SCENE_ENV: str = "GNB_SCENE_JSON"
SCENE_FILE: Path = (
    Path(__file__).resolve().parents[2] / "docs" / "animation" / "trilaterate_scene.py"
)
QUALITY_FLAGS: dict[str, str] = {
    "low": "-l",
    "medium": "-m",
    "hd": "--hd",
    "uhd": "--uhd",
}
_INSTALL_HINT: str = 'pip install -e ".[animation]"'

RunnerFn = Callable[[list[str], dict[str, str]], int]
WhichFn = Callable[[str], str | None]


class ManimMissing(RuntimeError):
    """manimgl is not on PATH."""


def build_argv(
    *, scene_file: Path, scene_name: str, quality: str, video_dir: Path
) -> list[str]:
    try:
        quality_flag = QUALITY_FLAGS[quality]
    except KeyError:
        raise ValueError(
            f"unknown quality {quality!r}; expected one of "
            f"{', '.join(QUALITY_FLAGS)}"
        ) from None
    return [
        MANIM_BINARY,
        str(scene_file),
        scene_name,
        "-w",
        quality_flag,
        "--video_dir",
        str(video_dir),
    ]


def _default_runner(argv: list[str], env: dict[str, str]) -> int:
    return subprocess.call(argv, env=env)


def render(
    *,
    scene_json: Path,
    scene_name: str,
    quality: str,
    video_dir: Path,
    output_fn: Callable[[str], None],
    scene_file: Path | None = None,
    runner_fn: RunnerFn | None = None,
    which_fn: WhichFn | None = None,
) -> int:
    """Render one scene and return manimgl's exit code."""
    which_fn = which_fn or shutil.which
    if which_fn(MANIM_BINARY) is None:
        argv = build_argv(
            scene_file=scene_file or SCENE_FILE,
            scene_name=scene_name,
            quality=quality,
            video_dir=video_dir,
        )
        raise ManimMissing(
            f"{MANIM_BINARY} is not installed. Install the animation extras with:\n"
            f"    {_INSTALL_HINT}\n"
            f"then run:\n"
            f"    {SCENE_ENV}={scene_json} {' '.join(argv)}"
        )

    argv = build_argv(
        scene_file=scene_file or SCENE_FILE,
        scene_name=scene_name,
        quality=quality,
        video_dir=video_dir,
    )
    env = dict(os.environ)
    env[SCENE_ENV] = str(scene_json)
    Path(video_dir).mkdir(parents=True, exist_ok=True)

    output_fn(f"  Rendering {scene_name} at {quality} quality...")
    code = (runner_fn or _default_runner)(argv, env)
    if code == 0:
        output_fn(f"  Video written under {video_dir}")
    else:
        output_fn(f"  {MANIM_BINARY} exited {code}; see its output above.")
    return code
