from ard.builder import build_image


def test_build_dry_run_plans_without_pack(tmp_path):
    (tmp_path / "requirements.txt").write_text("fastapi\n")
    (tmp_path / "agent.py").write_text("x = 1\n")
    res = build_image(str(tmp_path), image="acme/agent:1", dry_run=True)
    assert res.ran is False
    assert res.command[:2] == ["pack", "build"]
    assert "acme/agent:1" in res.command
    assert "--builder" in res.command
    assert "ard/python" in res.buildpacks
