This directory's active backend is the Python FastAPI service.

Active runtime files:
- `app/`
- `migrations/`
- `requirements.txt`
- `start.sh`

The older TypeScript/Express backend scaffolding that previously lived here has
been retired so it cannot be mistaken for the deploy target. Render must keep
using this same directory with the existing Python entrypoint:

- `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Do not reintroduce a second backend runtime inside this folder.
