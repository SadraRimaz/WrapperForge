# Implementation Plan: Tasks API — JavaScript

Source: core/mock-api/{contract.md, stage_plan.md, qc_interface.md,
qc_interface.openapi.json}

## Approach

- Client: global `fetch` (Node 18+ built-in), one class (`TaskClient`)
  with `async` typed methods, method-per-operation mirroring
  `contract.md`'s operation names. Errors: thrown typed `Error`
  subclasses — `TaskNotFoundError` (404) and `TaskValidationError`
  (422) — for `get`/`update`/`delete`/`create` failure cases, not
  `null`/error-code returns.
- Server: built-in `node:http` only, no framework. A small hand-rolled
  router matching on `` `${method} ${pathname}` `` (with a tiny bit of
  extra logic for the two path-param routes, `get/{id}` and
  `update/{id}`/`delete/{id}`, since `node:http` doesn't parse path
  params itself). Manual JSON body parsing via a shared
  `readJsonBody(req)` helper used by every `POST`/`PATCH` handler.
  Each handler calls into `lib/` and translates a thrown error
  (`instanceof TaskNotFoundError` → 404, `instanceof
  TaskValidationError` → 422) into the HTTP response `qc_interface.md`
  specifies. Binds to `PORT` env var (fallback `8000` only if unset);
  `GET /health` returns 200 once listening.
- Dependencies: none beyond Node built-ins (`fetch`, `node:http`).
  `package.json` declares `"dependencies": {}` and `"type": "module"`.

## Operations

| Operation (stage_plan.md) | Client method | Server route (qc_interface.openapi.json) |
|---|---|---|
| create | `async create(title, dueDate) -> Task` | `POST /wrapper/create` |
| get | `async get(id) -> Task` | `GET /wrapper/get/{id}` |
| list | `async list({ done } = {}) -> Task[]` | `GET /wrapper/list` |
| update | `async update(id, fields) -> Task` | `PATCH /wrapper/update/{id}` |
| delete | `async delete(id) -> void` | `DELETE /wrapper/delete/{id}` |
| bulk_update | `async bulkUpdate(items) -> { succeeded: Task[], failed: [{id, error}] }` | `POST /wrapper/bulk_update` |

`GET /health` is also exposed by the server per the fixed process
convention (not a `contract.md` operation, no corresponding client
method).

## Partial-failure representation

`bulkUpdate` returns a plain result object with `succeeded` / `failed`
arrays — the method's promise always resolves normally (never rejects
for per-item failures), only rejecting for a whole-call failure like a
network error or malformed request. This is the `allSettled`-style
shape fixed by `references/javascript_guide.md` and
`core/mock-api/language_notes.md`: one array of full `Task` objects for
successes, one array of `{ id, error }` for failures, mirroring the
wire-level `BulkUpdateResponse` shape in `qc_interface.openapi.json`
directly (no extra client-side reshaping needed) — `error` is a plain
string message, kept out of the QC comparison allowlist per
`qc_interface.md`.

## Open questions / judgment calls

- `qc_interface.openapi.json`'s `TaskUpdate` schema treats all three
  update fields as optional and doesn't define an "empty body" special
  case — the server's `readJsonBody` helper will treat a body-less
  `PATCH` as `{}` (a legal no-op update, consistent with
  `qc_interface.md`'s "an empty body is a legal no-op update" note),
  rather than raising a validation error.
- `list`'s `done` query param arrives as a string (`"true"`/`"false"`)
  over HTTP; the server parses it to a boolean before calling
  `list({ done })` and treats any other value (or absence) as
  "no filter," matching the direct backend's own query-param handling.
  Not spelled out explicitly in `qc_interface.md`, but the only
  reading consistent with `Task.done: boolean` and `cases.json`'s
  `list_done_filter` case (`?done=true`).

## File layout

```
wrappers/mock-api/javascript/
├── package.json            # name/version/type:"module", no dependencies
├── lib/
│   ├── client.js            # TaskClient class + typed async methods
│   ├── errors.js            # TaskNotFoundError, TaskValidationError
│   └── models.js            # JSDoc typedefs for Task / BulkUpdate shapes
└── server/
    └── main.js              # node:http server, one route per qc_interface.openapi.json entry + /health
```
