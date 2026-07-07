---
name: Replit proxy relative URL fix
description: How to construct absolute URLs when API_BASE_URL is a relative path like /api.
---

`new URL('/api/health')` throws because `URL()` requires an absolute base URL.

**Rule:** When `API_BASE_URL` starts with `/`, prepend `window.location.origin` before passing to `new URL()`.

```ts
const base = API_BASE_URL.startsWith('/')
  ? `${window.location.origin}${API_BASE_URL}`
  : API_BASE_URL;
const url = new URL(`${base}${path}`);
```

Set `API_BASE_URL` default to `'/api'` so the frontend works through Replit's path proxy without needing an env var.

**Why:** On Replit, the frontend and backend share the same domain via path-based routing. Using `/api` as the base avoids hardcoding domain names and works identically in dev and deployed environments.

**How to apply:** Always apply this pattern in API client files when the backend is co-hosted on the same domain via path prefix.
