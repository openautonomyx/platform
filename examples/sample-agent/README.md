# sample-agent — a discoverable echo skill server

End-to-end ard loop with this folder:

```bash
# 1. what does ard see here?
ard detect .

# 2. build it into an OCI image with the box (needs `pack` + a container runtime)
ard build . --image ghcr.io/acme/echo-agent:0.1
#   no pack installed? add --dry-run to print the exact plan.

# 3. run it as a pod (manifest runtime prints kubectl-ready JSON; docker runs it)
ard deploy --image ghcr.io/acme/echo-agent:0.1 --card card.json --runtime manifest

# 4. discover it
ard serve &                 # registry on :8080
ard discover --skill echo --kind skill
```

Or just run the server directly and view its card:

```bash
pip install ard
python agent.py
curl localhost:8080/.well-known/agent.json
```
