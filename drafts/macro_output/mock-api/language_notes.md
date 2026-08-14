# Language Notes: Tasks API

Brief, steering-only. Detailed idiom decisions belong to each
language's `/implement-wrapper` run, not here.

## Backend setup required before any QC run

`backend/mock_api/main.py` now seeds three fixed-id tasks
(`seed-task-1`, `seed-task-2`, `seed-task-3`) at startup, in addition
to the existing `SEED` env var for RNG-derived fields — no new startup
flag or command needed, this happens unconditionally on every start.
`core/mock-api/cases.json` depends on these three ids existing exactly
once, freshly, at the start of each `tests/audit.py` run — restart the
backend process between full audit runs rather than reusing a process
that has already run the case list once (`seed-task-3` gets deleted by
`delete_happy_path` and won't exist on a second pass without a
restart).

## Python

- `requests` session for the client, FastAPI for the QC server (per
  `CLAUDE.md` fixed defaults).
- `bulk_update`: a typed result object (not a raised exception) is the
  fixed default — e.g. a small dataclass/NamedTuple with `succeeded:
  list[Task]` and `failed: list[BulkUpdateFailure]`.
- Prefer a dedicated `TaskNotFoundError` (per `CLAUDE.md`) over a bare
  `requests.HTTPError` for `get`/`update`/`delete` 404s, so callers can
  catch it without inspecting status codes.

## Go

- Standard library only. `context.Context` as the first argument on
  every client method (per `CLAUDE.md`), including `List`.
- `bulk_update`: a per-item error slice, e.g.
  `[]BulkUpdateResult{ID string; Task *Task; Err error}`, preserving
  input order.
- Not-found and invalid-input should be distinguishable `error` values
  (e.g. via `errors.Is`/a sentinel or typed error), not just a generic
  wrapped HTTP error.

## JavaScript

- Global `fetch`, built-in `node:http` for the QC server, zero
  `package.json` dependencies (per `CLAUDE.md`).
- `bulk_update`: an `allSettled`-style array is the natural fit given
  the fixed default — one entry per input item, each tagged
  success/failure.
- Thrown typed `Error` subclasses (e.g. `TaskNotFoundError extends
  Error`) for `get`/`update`/`delete` 404s, not a bare rejected
  promise with an HTTP status buried in it.
