# Contract: Tasks API

This is the fixed semantics every language wrapper (`wrappers/{lang}/lib/`)
must implement against the mock backend's real HTTP API. It is written by
hand and does not change once agents start building against it.

## Resource: `Task`

| Field            | Type              | Notes                                   |
|-------------------|-------------------|------------------------------------------|
| `id`              | string            | Server-generated (UUID4).                |
| `title`           | string            |                                            |
| `done`            | boolean           | Defaults to `false` on create.            |
| `due_date`        | string (ISO 8601 date, `YYYY-MM-DD`) | |
| `priority_score`  | float             | Server-generated, seeded-random, `[0, 100)`. Never set by the client, never changed by update. |
| `created_at`      | string (ISO 8601 datetime) | Server-generated, seeded-random jitter. Never changed by update. |

## Operations

### 1. `create(title, due_date) -> Task`
Creates a task. `id`, `priority_score`, `created_at` are server-generated;
`done` starts `false`.

### 2. `get(id) -> Task`
Returns the task, or a not-found error if `id` doesn't exist.

### 3. `list(done?: boolean) -> Task[]`
Returns all tasks, optionally filtered by `done`. Omitting the filter
returns everything.

### 4. `update(id, fields) -> Task`
Partial update — only fields present in `fields` change. Updatable fields:
`title`, `done`, `due_date`. `priority_score` and `created_at` are
immutable. Not-found `id` returns a not-found error.

### 5. `delete(id) -> void`
Deletes the task. Not-found `id` returns a not-found error.

### 6. `bulk_update(items: [{id, fields}]) -> { succeeded: Task[], failed: [{id, error}] }`
Applies each item's update independently. An item with an unknown `id`
fails on its own without aborting the batch — every other item still
succeeds. Same field rules as `update`.

This is the deliberate partial-failure case: wrappers must make an
explicit, idiomatic choice for representing a response that's part
success, part failure (e.g. exceptions vs. a result object, an
`allSettled`-style array, a per-item error slice).

## Errors

- **Not found** (`get`, `update`, `delete`, and per-item in `bulk_update`):
  the `id` doesn't match any task.
- **Invalid input**: request fails to satisfy the field types above
  (e.g. missing `title`, malformed `due_date`).

Wrappers should surface both cases in a way that's idiomatic for their
language, but must not silently swallow either.
