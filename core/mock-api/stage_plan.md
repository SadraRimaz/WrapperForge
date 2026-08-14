# Stage Plan: Tasks API

Derived from `core/mock-api/contract.md`. Behavior spec only — no code,
no per-language implementation choices.

## Open questions / notes for review

1. **`GET /health` on the OpenAPI spec is not a `contract.md` operation.**
   It's the direct backend's own readiness probe, distinct in purpose
   (and process) from the QC server's own `GET /health`, which every
   language's QC server must independently expose per the fixed process
   convention in `qc_interface.md`. Two different servers happen to
   share a route name; not a contract mismatch, just noted for clarity.

2. **Fixed-id seed fixtures added to the backend.** `contract.md` notes
   `id` is "Server-generated (UUID4)". Real `create()` calls still
   generate random UUID4 ids, unchanged. But `tests/audit.py` does no
   live derivation and no response-chaining between cases (locked
   design — see `plan.md` Phase 4), so a genuine happy-path (200/204)
   QC case for `get`/`update`/`delete`/`bulk_update` needs a task id
   that's known at draft time, which a random UUID4 can never be.
   With the user's approval, `backend/mock_api/main.py` now
   deterministically seeds three fixture tasks at startup with fixed,
   non-UUID4 string ids: `seed-task-1`, `seed-task-2`, `seed-task-3`.
   Their `priority_score`/`created_at` still come from the seeded RNG,
   so restart-reproducibility is unaffected. `id`'s contract type is
   `string` (the "(UUID4)" note describes the normal-path implementation,
   not a wire-format constraint), so no wrapper-facing type contract is
   broken by these fixture ids. `cases.json` references them directly
   for non-happy-path-safe, non-destructive read/update cases; the sole
   `delete` happy-path case necessarily consumes one fixture permanently
   for that run.

## Generated / server-controlled fields

- **`id`** — Unique task identifier. Assigned once, at creation, never
  reassigned. Client never sets or changes it. For QC purposes: must be
  present, non-empty, and stable across reads of the same task.
- **`priority_score`** — A seeded-random float in `[0, 100)`. Assigned
  once, at creation. Never recomputed on read, never changed by
  `update`/`bulk_update`. For QC purposes: must be present and, for a
  given `SEED` and call sequence, byte-identical between the direct
  backend and the wrapper server — this is the primary field this
  pipeline uses to detect a wrapper silently dropping or corrupting a
  passthrough field.
- **`created_at`** — A seeded-random ISO 8601 UTC timestamp. Assigned
  once, at creation. Never changed thereafter. Same QC role as
  `priority_score`.

## Operations

### `create`

- **Trigger / when it's called:** client wants to add a new task.
- **Inputs:** `title` (required, non-empty string), `due_date`
  (required, ISO 8601 date `YYYY-MM-DD`). No other fields accepted —
  `id`, `done`, `priority_score`, `created_at` are never client-supplied
  on create.
- **Success behavior:** a new `Task` is created and stored, with
  `done` defaulting to `false` and `id`/`priority_score`/`created_at`
  server-generated. Returns the full created `Task`.
- **Edge cases:**
  - Invalid input: missing `title`, missing `due_date`, or a
    malformed `due_date` (not a valid ISO 8601 date) — rejected, task
    is not created.
- **Idempotency / side effects:** not idempotent — every call creates a
  distinct new task, even with identical `title`/`due_date`.

### `get`

- **Trigger / when it's called:** client wants a single task by id.
- **Inputs:** `id` (required).
- **Success behavior:** returns the full `Task` matching `id`, exactly
  as currently stored (post any prior updates).
- **Edge cases:**
  - Not-found: `id` doesn't match any stored task.
- **Idempotency / side effects:** read-only; repeatable with identical
  results (given no intervening writes).

### `list`

- **Trigger / when it's called:** client wants some or all tasks.
- **Inputs:** `done` (optional boolean filter).
- **Success behavior:** returns every stored task when `done` is
  omitted; returns only tasks whose `done` matches the filter
  otherwise. Empty store or empty filter match returns an empty list,
  not an error.
- **Edge cases:** none beyond the above — there is no not-found
  concept for `list`.
- **Idempotency / side effects:** read-only; repeatable with identical
  results (given no intervening writes).

### `update`

- **Trigger / when it's called:** client wants to change one or more
  mutable fields of an existing task.
- **Inputs:** `id` (required); `fields` — a partial object, any subset
  of `title`, `done`, `due_date`. Fields omitted from `fields` are left
  unchanged. `priority_score` and `created_at` are never accepted as
  update inputs and never change as a side effect of update.
- **Success behavior:** only the fields present in `fields` are
  applied; returns the full, post-update `Task`.
- **Edge cases:**
  - Not-found: `id` doesn't match any stored task — no fields applied.
  - Invalid input: a present field fails its type (e.g. `due_date` not
    a valid ISO 8601 date, `done` not a boolean).
- **Idempotency / side effects:** applying the same `fields` twice
  produces the same end state (idempotent at the field-value level),
  but each call still counts as a distinct update.

### `delete`

- **Trigger / when it's called:** client wants to remove a task
  permanently.
- **Inputs:** `id` (required).
- **Success behavior:** the task is removed from storage; no content
  returned.
- **Edge cases:**
  - Not-found: `id` doesn't match any stored task.
- **Idempotency / side effects:** not idempotent in the strict sense —
  a second `delete` of the same now-gone `id` is a not-found, not a
  repeat success.

## Partial-failure / batch operations

### `bulk_update`

- **Trigger / when it's called:** client wants to apply independent
  partial updates to many tasks in one call.
- **Inputs:** `items` — a list of `{id, fields}`, where `fields` follows
  the same shape/rules as plain `update`.
- **Exact per-item success/failure conditions:** each item is evaluated
  independently against current storage. An item whose `id` doesn't
  match any stored task **fails on its own** (recorded with its `id`
  and an error) without aborting the batch — every other item in the
  same call is still attempted and, if valid, still succeeds. An item
  can only fail for the same reasons plain `update` can fail for that
  `id`: not-found. (This stage plan does not extend `bulk_update` with
  its own additional per-item invalid-input case beyond what `update`
  already defines — an item's `fields` are assumed well-typed, per the
  same validation `update` performs.)
- **Atomicity:** each item's own change, if it succeeds, is atomic —
  there is no partial application of a single item's `fields`. Only the
  *batch-level* isolation (one item's failure not affecting others)
  varies; there is no cross-item transactionality at all — every item
  is fully independent.
- **Overall response shape (behaviorally, not wire format):** a
  succeeded set (full updated `Task` per success) and a failed set (the
  offending `id` plus an error indication per failure).
- **Deliberate divergence point:** this stage plan fixes the
  *behavior* above — it does not decide how each language represents a
  "part success, part failure" result (exceptions vs. a result object
  vs. an `allSettled`-style array vs. a per-item error slice). That
  choice is intentionally left to each language's micro-agent in
  `/implement-wrapper`, per the fixed per-language defaults in
  `CLAUDE.md`.

## Cross-cutting edge cases

- **Not-found** (`get`, `update`, `delete`, and per-item in
  `bulk_update`) always means the same thing: the `id` doesn't match
  any currently-stored task. It never means anything else (e.g. it
  never means "malformed id syntax" — a syntactically-odd id that
  simply isn't in storage is still just not-found, not invalid-input).
- **Invalid input** (`create`, `update`, and — by the same field rules
  — each item's `fields` in `bulk_update`) always means: a
  client-supplied field fails to satisfy the type/format in
  `contract.md`'s field table (missing required field on `create`;
  malformed `due_date`; wrong type for `done`). It's a rejection of the
  request, not a partial application.
- **Status-code parity requirement:** because QC is a live
  direct-vs-wrapper diff, every language's QC server must return the
  same HTTP status code as the direct backend for the same logical
  outcome — including reusing the backend's own `422` for invalid
  input (an unusual choice outside FastAPI/Pydantic, but required here
  for cross-implementation comparability; see `qc_interface.md`).
- **Error body wording is not compared.** `qc_interface.openapi.json`
  deliberately does not declare error-message text fields as part of
  the QC comparison allowlist (see its "Notes" section) — only the
  status code, and for `bulk_update`, the set of failed `id`s, are
  checked. Each language is free to phase its error messages
  idiomatically per `contract.md`'s "surface both cases in a way that's
  idiomatic for their language" instruction.
- **Timestamps** (`created_at`) are always UTC ISO 8601.
