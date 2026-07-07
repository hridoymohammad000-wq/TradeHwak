---
name: Python on Replit Nix
description: How to install Python packages on Replit's Nix environment where system pip is blocked.
---

Nix marks its Python install as "externally managed" and blocks `pip install` to the system store.

**Rule:** Always create a `.venv/` virtualenv inside the artifact directory and install packages there.

```bash
python3 -m venv artifacts/my-service/.venv
artifacts/my-service/.venv/bin/pip install -r requirements.txt
```

In the startup script, check/create the venv before installing:
```bash
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -r requirements.txt --quiet
exec .venv/bin/python3 -m uvicorn ...
```

**Why:** The Nix store is immutable. `pip install --user` is also blocked. A local venv at a writable workspace path bypasses the restriction.

**How to apply:** Any time you're adding a Python service as an artifact — use this pattern in the startup script. The venv persists across restarts since it's in the workspace.
