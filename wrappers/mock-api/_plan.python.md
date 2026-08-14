# Implementation Plan: Tasks API — Python

Source: core/mock-api/{contract.md, stage_plan.md, qc_interface.md,
qc_interface.openapi.json}

## Approach

- Client: `requests.Session`-based client class, typed exceptions
  (`TaskNotFoundError`, `TaskValidationError`) for not-found / invalid-input,
  `dataclasses` for the `Task` shape. One class with typed methods per
  operation (`create`, `get`, `list`, `update`, `delete`, `bulk_update`) —
  not a generic dispatcher.
- Server: FastAPI + `uvicorn`, thin shim over the client library, one route
  per `qc_interface.openapi.json` entry, centralized exception→HTTP mapping
  via a FastAPI exception handler. Binds to `PORT` env var, exposes
  `GET /health` → 200.
- Dependencies: `requests`, `fastapi`, `uvicorn` — nothing else.

## Operations

| Operation (stage_plan.md) | Client method | Server route (qc_interface.openapi.json) |
|---|---|---|
| create | `client.create(title, due_date) -> Task` | `POST /wrapper/create` |
| get | `client.get(id) -> Task` | `GET /wrapper/get/{id}` |
| list | `client.list(done=None) -> list[Task]` | `GET /wrapper/list` |
| update | `client.update(id, **fields) -> Task` | `PATCH /wrapper/update/{id}` |
| delete | `client.delete(id) -> None` | `DELETE /wrapper/delete/{id}` |
| bulk_update | `client.bulk_update(items) -> BulkUpdateResult` | `POST /wrapper/bulk_update` |
| (process convention) | — | `GET /health` |

`update`'s partial-field semantics: the client method accepts `title`,
`done`, `due_date` as independent optional keyword arguments (default
unset/`None`-sentinel so `done=False` can still be sent), and only builds
the JSON body from whichever were actually passed — matching "any subset,
empty body legal" from `qc_interface.md`.

## Partial-failure representation

`bulk_update` returns a typed result object (not a raised exception), per
`language_notes.md`'s fixed default for Python: a small dataclass
`BulkUpdateResult` with `succeeded: list[Task]` and
`failed: list[BulkUpdateFailure]` (`BulkUpdateFailure` = `{id: str, error: str}`).
The call only raises if the request itself fails at the transport level —
individual item failures are always returned, never raised. The server
route passes the client's `succeeded`/`failed` lists straight through into
the `200` body `qc_interface.md` specifies (`error` text included on the
wire even though `audit.py`'s comparison allowlist ignores it).

## Open questions / judgment calls

- `client.update`'s "unset vs. explicitly-passed" distinction for optional
  fields (so `done=False` isn't dropped as "not provided") needs a sentinel
  default rather than plain `None` defaults, since `None` isn't a valid
  value for any of `title`/`done`/`due_date` anyway. Using a module-level
  `_UNSET` sentinel object for this. Not specified by `stage_plan.md`
  (language-agnostic) or the language guide, but required for correctness
  against the "any subset" update semantics.
- `qc_interface.md`'s 422 body is "shape unconstrained for QC purposes" —
  the server will return FastAPI's default validation-error body (or a
  simple `{"detail": ...}` from the exception handler) since `audit.py`
  never compares its fields, only the status code.

## File layout

```
wrappers/mock-api/python/
├── .venv/                 # dedicated venv, created with `uv venv --python 3.12`
├── lib/
│   ├── __init__.py
│   ├── client.py          # TasksClient class + typed methods
│   ├── models.py          # Task, BulkUpdateFailure, BulkUpdateResult dataclasses
│   └── errors.py          # TaskNotFoundError, TaskValidationError
├── server/
│   ├── __init__.py
│   └── main.py            # FastAPI app, one route per qc_interface.openapi.json entry
└── requirements.txt       # requests, fastapi, uvicorn
```
