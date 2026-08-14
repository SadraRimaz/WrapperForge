# QC Interface: Tasks API

Human-readable HTTP contract that every language's QC-facing server
(`wrappers/mock-api/<lang>/server/`) must implement. One route per
`stage_plan.md` operation (**1:1 mapping** — locked design decision:
mirrors real SDK method-per-operation shape, gives REST-semantics
coverage (status codes) for free, and stops a broken wrapper from
hiding behind a generic `200` on a uniform `/invoke` endpoint. Never a
uniform `/invoke` endpoint.

## Process convention

- Every QC server binds to a `PORT` env var (no hardcoded port).
- Every QC server exposes `GET /health` → `200` once ready to serve.
  (This is the QC server's own health route — distinct from the direct
  backend's `GET /health` at `/health` on its own base URL; see
  `stage_plan.md` open question 1.)

## Field/schema comparison note

`tests/audit.py` compares status codes always, and restricts body
comparison to fields declared in the matching response schema in
`qc_interface.openapi.json` — undeclared fields (headers, request ids,
error message text, etc.) are ignored. See that file's schemas for the
exact allowlist per route/status; this file describes shape only.

## Routes

### `POST /wrapper/create` — `create`

- **Maps to:** `stage_plan.md` § `create`
- **Request:**
  - No path/query params.
  - Body: `{ title: string, due_date: string (YYYY-MM-DD) }`
- **Success response:** `201`, body = full `Task`.
- **Error responses:**
  - `422` — invalid input (missing `title`/`due_date`, malformed
    `due_date`). Body shape unconstrained for QC purposes (see
    Notes).

### `GET /wrapper/get/{id}` — `get`

- **Maps to:** `stage_plan.md` § `get`
- **Request:**
  - Path param: `id` (string).
- **Success response:** `200`, body = full `Task`.
- **Error responses:**
  - `404` — not found. Body shape unconstrained for QC purposes.

### `GET /wrapper/list` — `list`

- **Maps to:** `stage_plan.md` § `list`
- **Request:**
  - Query param: `done` (optional boolean).
- **Success response:** `200`, body = `Task[]` (possibly empty).
- **Error responses:** none.

### `PATCH /wrapper/update/{id}` — `update`

- **Maps to:** `stage_plan.md` § `update`
- **Request:**
  - Path param: `id` (string).
  - Body: `{ title?: string, done?: boolean, due_date?: string
    (YYYY-MM-DD) }` — any subset, at least conceptually (an empty body
    is a legal no-op update).
- **Success response:** `200`, body = full, post-update `Task`.
- **Error responses:**
  - `404` — not found.
  - `422` — invalid input (a present field fails its type).

### `DELETE /wrapper/delete/{id}` — `delete`

- **Maps to:** `stage_plan.md` § `delete`
- **Request:**
  - Path param: `id` (string).
- **Success response:** `204`, no body.
- **Error responses:**
  - `404` — not found.

### `POST /wrapper/bulk_update` — `bulk_update`

- **Maps to:** `stage_plan.md` § `bulk_update`
- **Request:**
  - Body: `{ items: [{ id: string, fields: { title?, done?,
    due_date? } }] }`
- **Success response:** `200` always — even when some items fail, the
  batch call itself succeeds. Body:
  `{ succeeded: Task[], failed: [{ id: string, error: string }] }`.
  (Wire shape only — each language's *client-library-facing*
  representation of this part-success/part-failure result is an
  intentionally open per-language choice; see `stage_plan.md`.)
- **Error responses:** none at the batch level (per-item failures are
  reported inside the `200` body's `failed` array, not via HTTP status).

### `GET /health` — process convention (not a `contract.md` operation)

- **Success response:** `200`.

## Notes

- **`bulk_update` is always `200` at the HTTP layer**, regardless of
  how many items failed — `stage_plan.md` deliberately leaves the
  *client-library-level* representation of partial failure open, but
  this file fixes the *wire-level* shape (`succeeded`/`failed` split in
  one `200` body) so `tests/audit.py` has something concrete to diff.
- **Error message text is intentionally excluded from the QC
  comparison allowlist.** `qc_interface.openapi.json` declares `404`
  and `422` response bodies with no compared properties, and declares
  `bulk_update`'s `failed[]` entries with only `id` in the allowlist
  (not `error`). Requiring verbatim error-string parity across Python,
  Go, and JavaScript QC servers would contradict `contract.md`'s
  instruction that wrappers surface errors "in a way that's idiomatic
  for their language" — so only status codes, and for `bulk_update` the
  *set* of failed ids, are checked for these paths. Success-path bodies
  (`Task`, `Task[]`, `succeeded[]`) are fully declared and fully
  compared, since those carry `priority_score`/`created_at` — the
  fields this pipeline relies on to catch a wrapper silently dropping
  or corrupting a passthrough value.
