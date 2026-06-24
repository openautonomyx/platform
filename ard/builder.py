"""Drive the Cloud Native Buildpacks lifecycle to bake an agent OCI image.

``ard build`` shells out to ``pack`` with the ard builder ("the box"). When
``pack`` isn't present (CI, this sandbox), it returns a *plan* — the exact
command plus which ard buildpacks would claim the project — so the flow is
inspectable everywhere and the image bakes for real at the user's desk.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

from .detect import detect

DEFAULT_BUILDER = "ard/box"


@dataclass
class BuildResult:
    image: str
    ran: bool
    command: list[str]
    buildpacks: list[str]
    detail: str


def pack_available() -> bool:
    return shutil.which("pack") is not None


def build_image(
    app_dir: str,
    image: str,
    builder: str = DEFAULT_BUILDER,
    env: dict[str, str] | None = None,
    dry_run: bool | None = None,
) -> BuildResult:
    """Bake (or plan) an OCI image for the agent in ``app_dir`` via the CNB lifecycle."""
    ctx = detect(app_dir)
    cmd = ["pack", "build", image, "--builder", builder, "--path", app_dir]
    for k, v in (env or {}).items():
        cmd += ["--env", f"{k}={v}"]

    if dry_run is None:
        dry_run = not pack_available()

    if dry_run:
        return BuildResult(
            image=image, ran=False, command=cmd, buildpacks=ctx.buildpacks,
            detail="`pack` not found — plan only. Run the command above at your desk to bake the image.",
        )

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return BuildResult(
        image=image, ran=proc.returncode == 0, command=cmd, buildpacks=ctx.buildpacks,
        detail=(proc.stdout + proc.stderr)[-4000:],
    )
