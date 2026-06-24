from ard.detect import detect


def _w(p, name, content=""):
    (p / name).write_text(content)


def test_python_project(tmp_path):
    _w(tmp_path, "pyproject.toml", "[project]\ndependencies = ['fastapi']\n")
    _w(tmp_path, "agent.py", "print('hi')\n")
    ctx = detect(str(tmp_path))
    assert "python" in ctx.languages
    assert "ard/python" in ctx.buildpacks
    assert "fastapi" in ctx.frameworks
    assert ctx.entrypoint == "agent.py"


def test_node_project(tmp_path):
    _w(tmp_path, "package.json", '{"dependencies":{"express":"^4"},"main":"index.js"}')
    ctx = detect(str(tmp_path))
    assert "node" in ctx.languages
    assert "ard/node" in ctx.buildpacks
    assert "express" in ctx.frameworks


def test_polyglot(tmp_path):
    _w(tmp_path, "requirements.txt", "mcp\n")
    _w(tmp_path, "package.json", "{}")
    ctx = detect(str(tmp_path))
    assert set(ctx.languages) >= {"python", "node"}
    assert "mcp" in ctx.frameworks


def test_empty_dir(tmp_path):
    ctx = detect(str(tmp_path))
    assert ctx.languages == []
    assert ctx.buildpacks == []
