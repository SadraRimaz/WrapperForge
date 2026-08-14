# Python implementation guide

Practical, opinionated defaults for `wrappers/<api-name>/python/`. These
are steering choices for a proof-of-concept pipeline — optimize for
simple, minimal-dependency, readable code over completeness or
production hardening.

## Client library (`lib/`)

- **HTTP client: `requests`.** It's the simplest, most common choice
  for a synchronous client library, has no exotic dependencies, and is
  what most hand-written Python API wrappers use. Don't reach for
  `httpx` or `aiohttp` unless `stage_plan.md` specifically calls for
  async behavior — it won't, since stage_plan.md is language-agnostic.
- **One class per resource area, typed methods per operation.**
  OpenAI-SDK-style: `client.create(...)`, `client.get(id)`,
  `client.list(done=None)`, etc. — not a single generic `client.call(op, **kwargs)`
  dispatcher. Method names should read naturally against `contract.md`'s
  operation names.
- **Type hints throughout.** Use `dataclasses` or plain typed dicts for
  the resource shape (e.g. `Task`) — no need for `pydantic` in the
  client library itself; that's more dependency than a thin client
  needs. (The mock backend uses pydantic because it's a FastAPI server;
  the *client* doesn't need it.)
- **Errors:** raise typed exceptions for the not-found and
  invalid-input cases `stage_plan.md` describes (e.g. a
  `TaskNotFoundError(Exception)`, a `TaskValidationError(Exception)`)
  rather than returning `None`/error codes. Idiomatic Python favors
  exceptions over sentinel returns.
- **Partial-failure operations** (e.g. a bulk operation): return a
  small typed result object with `succeeded` / `failed` lists rather
  than raising on partial failure — raising would force the caller to
  catch an exception just to get the partial results, which defeats
  the point of "some succeeded." Only raise if the *whole call*
  fails (e.g. the request itself errors, not an individual item).
- **No retries, no connection pooling config, no auth layer** unless
  `contract.md` or `stage_plan.md` calls for it — this is a
  proof-of-concept wrapper against a mock backend, not a production
  SDK. Keep it to what the contract actually requires.

## QC-facing server (`server/`)

- **Framework: FastAPI.** Minimal boilerplate, built-in request
  validation, and it's already a dependency of this repo's mock
  backend, so no new tooling to install. Run with `uvicorn`.
- **One route per operation, matching `qc_interface.openapi.json`
  exactly** — same paths, methods, status codes. The server should be a
  thin shim: each route handler calls the client library and translates
  its result/exception into the HTTP response `qc_interface.md`
  describes. No business logic belongs in the server layer.
- **`PORT` env var, not a hardcoded port.** Read it at startup
  (`int(os.environ.get("PORT", "8000"))` as a fallback default is fine
  for local dev, but the real value always comes from the env var).
- **`GET /health`** returns `200` once the app is ready to serve. Keep
  it trivial — no dependency checks, just confirms the process is up.
- **Translating client exceptions to HTTP:** a `TaskNotFoundError` from
  the client library becomes the 404 response `qc_interface.md`
  specifies; a `TaskValidationError` becomes the 4xx invalid-input
  response. This mapping should be centralized (e.g. a FastAPI
  exception handler) rather than repeated in every route.

## Suggested layout

```
wrappers/<api-name>/python/
├── .venv/                 # dedicated venv for this wrapper — created with `uv venv`, never the backend's .venv
├── lib/
│   ├── __init__.py
│   ├── client.py          # the client class + typed methods
│   ├── models.py          # Task-like dataclasses / typed dicts
│   └── errors.py          # TaskNotFoundError, TaskValidationError, etc.
├── server/
│   └── main.py            # FastAPI app, one route per qc_interface.openapi.json entry
└── requirements.txt       # requests, fastapi, uvicorn — nothing else unless justified
```

## Environment & dependencies

This wrapper gets its **own** virtual environment, isolated from
`backend/mock_api/`'s. Never install into or run the server from the
backend's `.venv` — the two are separate Python projects with separate
`requirements.txt` files, and the backend keeps running as its own
out-of-band process throughout.

1. **Create the venv** at `wrappers/<api-name>/python/.venv`, pinned to
   Python 3.12, using `uv`:
   ```bash
   cd wrappers/<api-name>/python
   uv venv --python 3.12
   ```
2. **Write `requirements.txt`** to what's actually used — nothing more:
   ```
   requests
   fastapi
   uvicorn
   ```
   Don't add `pydantic` explicitly (FastAPI pulls it in transitively) or
   anything else without a concrete reason tied to `stage_plan.md`.
3. **Install into that venv** with `uv pip install`, not plain `pip`:
   ```bash
   uv pip install -r requirements.txt --python .venv
   ```
4. **Run the server from this venv**, never from the backend's or the
   system interpreter:
   ```bash
   .venv/bin/uvicorn server.main:app --port "$PORT"
   ```
   (or `.venv\Scripts\uvicorn.exe` on Windows). Any smoke test or QC
   run against this language's server assumes the process was started
   this way.
