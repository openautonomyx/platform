import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_toml(rel):
    tomllib = pytest.importorskip("tomllib")  # py3.11+; structural check only
    with open(os.path.join(ROOT, rel), "rb") as f:
        return tomllib.load(f)


def test_buildpack_tomls_valid():
    for bp in ("ard-python", "ard-node"):
        data = _load_toml(f"buildpacks/{bp}/buildpack.toml")
        assert data["api"]
        assert data["buildpack"]["id"].startswith("ard/")
        assert data["buildpack"]["version"]
        assert data["stacks"]


def test_builder_toml_defines_the_box():
    data = _load_toml("builder.toml")
    assert {b["id"] for b in data["buildpacks"]} == {"ard/python", "ard/node"}
    assert "order" in data
    assert data["stack"]["id"]
    assert data["stack"]["build-image"]


def test_bin_scripts_present_and_executable():
    for bp in ("ard-python", "ard-node"):
        for script in ("detect", "build"):
            p = os.path.join(ROOT, "buildpacks", bp, "bin", script)
            assert os.path.exists(p), f"missing {p}"
            assert os.access(p, os.X_OK), f"not executable: {p}"
