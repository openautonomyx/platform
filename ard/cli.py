"""``ard`` CLI — the build-at-desk entrypoint for the ecosystem.

  ard detect [path]                          what env / which buildpacks apply
  ard build  [path] --image REF [--env K=V]  bake an OCI image via CNB ("the box")
  ard deploy --image REF --card FILE [...]    run it as a pod (tool/skill server)
  ard pods                                    list managed pods + status
  ard stop NAME
  ard serve [--host --port]                   run the discovery registry
  ard discover [--skill --tag --kind] [--url] query discovery
  ard card validate FILE
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

from .builder import DEFAULT_BUILDER, build_image
from .card import AgentCard, CardError
from .detect import detect
from .pod import LocalDockerRuntime, ManifestRuntime, PodManager, PodSpec
from .registry import Registry
from .server import serve


def _state_dir() -> str:
    d = os.environ.get("ARD_HOME") or os.path.join(os.path.expanduser("~"), ".ard")
    os.makedirs(d, exist_ok=True)
    return d


def _registry() -> Registry:
    return Registry(path=os.path.join(_state_dir(), "registry.json"))


def _podmgr(runtime) -> PodManager:
    return PodManager(runtime=runtime, state_path=os.path.join(_state_dir(), "pods.json"), registry=_registry())


def _kv(pairs: list[str]) -> dict[str, str]:
    out = {}
    for p in pairs or []:
        k, _, v = p.partition("=")
        out[k] = v
    return out


# --- commands -------------------------------------------------------------


def cmd_detect(args) -> int:
    print(json.dumps(detect(args.path).to_dict(), indent=2))
    return 0


def cmd_build(args) -> int:
    res = build_image(args.path, image=args.image, builder=args.builder, env=_kv(args.env), dry_run=args.dry_run)
    print(json.dumps({
        "image": res.image,
        "ran": res.ran,
        "buildpacks": res.buildpacks,
        "command": " ".join(res.command),
        "detail": res.detail,
    }, indent=2))
    return 0 if res.ran or args.dry_run or args.dry_run is None else 1


def cmd_deploy(args) -> int:
    try:
        with open(args.card, encoding="utf-8") as f:
            card = AgentCard.from_json(f.read())
    except (OSError, CardError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    runtime = LocalDockerRuntime() if args.runtime == "docker" else ManifestRuntime()
    mgr = _podmgr(runtime)
    spec = PodSpec(name=args.name or card.name, image=args.image, card=card, kind=card.kind, port=args.port)
    if args.runtime == "manifest":
        print(json.dumps(mgr.manifests(spec), indent=2))
    pod = mgr.deploy(spec)
    print(json.dumps({"deployed": pod.to_dict(), "runtime": runtime.name}, indent=2))
    return 0 if pod.status == "running" else 1


def cmd_pods(args) -> int:
    mgr = _podmgr(ManifestRuntime())
    pods = [mgr.status(p.name).to_dict() for p in mgr.list()]
    print(json.dumps(pods, indent=2))
    return 0


def cmd_stop(args) -> int:
    mgr = _podmgr(ManifestRuntime())
    ok = mgr.stop(args.name)
    print(f"{'stopped' if ok else 'no such pod'}: {args.name}")
    return 0 if ok else 1


def cmd_serve(args) -> int:
    serve(_registry(), host=args.host, port=args.port)
    return 0


def cmd_discover(args) -> int:
    if args.url:
        q = {k: v for k, v in (("skill", args.skill), ("tag", args.tag), ("kind", args.kind)) if v}
        url = args.url.rstrip("/") + "/agents?" + urllib.parse.urlencode(q)
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310 (user-supplied registry URL)
            print(resp.read().decode())
        return 0
    cards = _registry().query(skill=args.skill, tag=args.tag, kind=args.kind)
    print(json.dumps([c.to_dict() for c in cards], indent=2))
    return 0


def cmd_card(args) -> int:
    try:
        with open(args.file, encoding="utf-8") as f:
            AgentCard.from_json(f.read()).validate()
    except (OSError, CardError) as exc:
        print(f"invalid: {exc}", file=sys.stderr)
        return 1
    print(f"valid: {args.file}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ard", description="Make agents discoverable: build → deploy → register → discover.")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("detect", help="show env + applicable buildpacks")
    d.add_argument("path", nargs="?", default=".")
    d.set_defaults(func=cmd_detect)

    b = sub.add_parser("build", help="bake an OCI image via CNB (the box)")
    b.add_argument("path", nargs="?", default=".")
    b.add_argument("--image", required=True, help="OCI image ref to produce, e.g. ghcr.io/acme/agent:0.1")
    b.add_argument("--builder", default=DEFAULT_BUILDER)
    b.add_argument("--env", action="append", default=[], metavar="K=V")
    b.add_argument("--dry-run", dest="dry_run", action="store_true", default=None, help="plan only")
    b.set_defaults(func=cmd_build)

    dep = sub.add_parser("deploy", help="run a built image as a tool/skill server pod")
    dep.add_argument("--image", required=True)
    dep.add_argument("--card", required=True, help="path to the agent card JSON")
    dep.add_argument("--name", default=None)
    dep.add_argument("--port", type=int, default=8080)
    dep.add_argument("--runtime", choices=["manifest", "docker"], default="manifest")
    dep.set_defaults(func=cmd_deploy)

    pods = sub.add_parser("pods", help="list managed pods + status")
    pods.set_defaults(func=cmd_pods)

    st = sub.add_parser("stop", help="stop a pod")
    st.add_argument("name")
    st.set_defaults(func=cmd_stop)

    sv = sub.add_parser("serve", help="run the discovery registry")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8080)
    sv.set_defaults(func=cmd_serve)

    disc = sub.add_parser("discover", help="query discovery (local registry or a remote --url)")
    disc.add_argument("--skill")
    disc.add_argument("--tag")
    disc.add_argument("--kind", choices=["skill", "tool"])
    disc.add_argument("--url", help="a remote ard registry base URL")
    disc.set_defaults(func=cmd_discover)

    c = sub.add_parser("card", help="agent card utilities")
    csub = c.add_subparsers(dest="card_cmd", required=True)
    cv = csub.add_parser("validate", help="validate an agent card file")
    cv.add_argument("file")
    cv.set_defaults(func=cmd_card)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
