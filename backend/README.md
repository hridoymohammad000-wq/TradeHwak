# Legacy backend — not deployed

This `backend/` directory is **not** the Render deployment source.

The active backend is:

`artifacts/api-server/`

`render.yaml` builds and starts the FastAPI application from that directory. This legacy backend has different authentication, routing, persistence, runtime-store, schema, and service-wiring behavior.

Rules for recovery work:

- Do not apply production fixes here.
- Do not copy complete files from this directory into `artifacts/api-server/`.
- Port behavior only after checking constructor signatures, API paths, schemas, persistence, trade registration, and execution flow.
- Keep this directory unchanged until the canonical backend has passed integration tests and a separate cleanup is approved.

The Phase 1 ATR/swing-stop and weighted-scoring PR was merged into this non-deployed directory. Those changes must be reviewed and adapted to the canonical architecture before they can affect the live application.
