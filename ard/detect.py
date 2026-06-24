"""Environment detection — the read side of "build at desk based on user env".

Mirrors what the CNB buildpacks' ``bin/detect`` scripts decide, but as a Python
helper the ``ard`` CLI uses to *explain* (``ard detect``) which buildpacks apply
before delegating the real build to the CNB lifecycle (``pack``).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

PY_MARKERS = ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg")
PY_FRAMEWORKS = ("fastapi", "flask", "starlette", "uvicorn", "mcp")
NODE_FRAMEWORKS = ("express", "fastify", "@modelcontextprotocol/sdk")


@dataclass
class EnvContext:
    """What we found in a project directory."""

    root: str
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    entrypoint: str | None = None

    def applies(self, language: str) -> bool:
        return language in self.languages

    @property
    def buildpacks(self) -> list[str]:
        """Names of the ard CNB buildpacks that would claim this project."""
        return [f"ard/{lang}" for lang in self.languages if lang in ("python", "node")]

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "languages": self.languages,
            "frameworks": self.frameworks,
            "files": self.files,
            "entrypoint": self.entrypoint,
            "buildpacks": self.buildpacks,
        }


def _exists(root: str, *names: str) -> list[str]:
    return [n for n in names if os.path.exists(os.path.join(root, n))]


def _read(root: str, name: str) -> str:
    try:
        with open(os.path.join(root, name), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _has_ext(root: str, ext: str) -> bool:
    try:
        return any(n.endswith(ext) for n in os.listdir(root))
    except OSError:
        return False


def _first_existing(root: str, *names: str) -> str | None:
    for n in names:
        if os.path.exists(os.path.join(root, n)):
            return n
    return None


def detect(root: str) -> EnvContext:
    """Inspect ``root`` and report languages, frameworks and an entrypoint guess."""
    root = os.path.abspath(root)
    languages: list[str] = []
    frameworks: list[str] = []
    files: list[str] = []
    entrypoint: str | None = None

    py_markers = _exists(root, *PY_MARKERS)
    if py_markers or _has_ext(root, ".py"):
        languages.append("python")
        files += py_markers
        deps = _read(root, "pyproject.toml") + "\n" + _read(root, "requirements.txt")
        frameworks += [fw for fw in PY_FRAMEWORKS if re.search(rf"\b{re.escape(fw)}\b", deps, re.I)]
        entrypoint = _first_existing(root, "agent.py", "main.py", "app.py", "server.py")

    if _exists(root, "package.json"):
        languages.append("node")
        files.append("package.json")
        try:
            pj = json.loads(_read(root, "package.json") or "{}")
            all_deps = {**pj.get("dependencies", {}), **pj.get("devDependencies", {})}
        except json.JSONDecodeError:
            all_deps = {}
        frameworks += [fw for fw in NODE_FRAMEWORKS if fw in all_deps]
        entrypoint = entrypoint or _first_existing(root, "agent.js", "index.js", "server.js", "index.mjs")

    if _exists(root, "go.mod"):
        languages.append("go")
        files.append("go.mod")

    return EnvContext(root=root, languages=languages, frameworks=frameworks, files=files, entrypoint=entrypoint)
