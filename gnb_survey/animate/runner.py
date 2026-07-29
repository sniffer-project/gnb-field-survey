"""Invoke manimgl on the scene file, pointing it at one survey's scene data.

manimgl has no mechanism for forwarding unrecognised arguments to the Scene
being rendered -- its own argparse rejects them -- so the scene path travels
in an environment variable instead. Flags below are from manimgl's documented
CLI: -w (write file), -l/-m/--hd/--uhd (quality), --video_dir.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

from . import availability
from .availability import Renderer

MANIM_BINARY: str = availability.BINARY
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
_INSTALL_HINT: str = availability.INSTALL_HINT

RunnerFn = Callable[[list[str], dict[str, str]], int]


class ManimUnusable(RuntimeError):
    """manimgl is not on PATH, or is on PATH and will not start."""


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


def _unusable_message(state: Renderer, *, argv: list[str], scene_json: Path) -> str:
    if state.on_path:
        headline = (
            f"{MANIM_BINARY} is installed but will not start: {state.start_error}\n"
            f"Reinstall the animation extras with:"
        )
    else:
        headline = (
            f"{MANIM_BINARY} is not installed. Install the animation extras with:"
        )
    return (
        f"{headline}\n"
        f"    {_INSTALL_HINT}\n"
        f"then run:\n"
        f"    {SCENE_ENV}={scene_json} {' '.join(argv)}"
    )


def render(
    *,
    scene_json: Path,
    scene_name: str,
    quality: str,
    video_dir: Path,
    output_fn: Callable[[str], None],
    scene_file: Path | None = None,
    runner_fn: RunnerFn | None = None,
    renderer: Renderer | None = None,
) -> int:
    """Render one scene and return manimgl's exit code.

    The renderer is probed rather than merely located, so a manimgl that
    cannot import its own dependencies is refused here with the reason
    instead of being spawned to reprint its traceback. The probe is cached,
    so the menu having already asked makes this free.
    """
    state = renderer if renderer is not None else availability.current()
    if not state.ready:
        argv = build_argv(
            scene_file=scene_file or SCENE_FILE,
            scene_name=scene_name,
            quality=quality,
            video_dir=video_dir,
        )
        raise ManimUnusable(
            _unusable_message(state, argv=argv, scene_json=scene_json)
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
