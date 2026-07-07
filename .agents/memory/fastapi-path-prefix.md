---
name: FastAPI under path prefix for Replit
description: How to configure FastAPI so Replit's path proxy routes /api/* correctly.
---

Replit's path proxy forwards `/api/*` to the backend service without rewriting the path. The backend receives the full path including `/api/`.

**Rule:** Mount all routes with `app.include_router(api_router, prefix="/api")` and update FastAPI's docs URLs to match:

```python
app = FastAPI(
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    ...
)
app.include_router(api_router, prefix="/api")
```

Also update the health check path in `artifact.toml` to `/api/health` (not `/api/healthz` which is the Node.js scaffold default).

**Why:** Replit's proxy does NOT strip the path prefix before forwarding. A route registered at `/health` would never be hit because the proxy sends `/api/health` and FastAPI only knows `/health`.

**How to apply:** Any time a Python FastAPI service is placed behind Replit's `/api` path proxy.
