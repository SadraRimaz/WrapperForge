# Implementation Plan: Tasks API — Go

Source: core/mock-api/{contract.md, stage_plan.md, qc_interface.md,
qc_interface.openapi.json, language_notes.md}

## Approach

- Client: stdlib `net/http` + `encoding/json`, no third-party HTTP
  package. One `Client` struct, one typed method per operation, each
  taking `context.Context` as its first argument (per `CLAUDE.md` /
  `go_guide.md`).
- Errors: explicit `error` returns, not panics. `ErrTaskNotFound`
  sentinel (via `errors.Is`) for not-found; a typed `*ValidationError`
  (via `errors.As`) for invalid-input (422), carrying enough detail to
  distinguish it from a not-found without string-matching.
- Server: stdlib `net/http` + `http.ServeMux` (Go 1.22+ method+path
  patterns, e.g. `mux.HandleFunc("POST /wrapper/create", ...)`). Each
  handler calls the client library and translates its `error` into the
  HTTP response `qc_interface.md` specifies via `errors.Is`/`errors.As`.
- Dependencies: none beyond the standard library. `go.mod` declares
  the module and Go version only.

## Operations

| Operation (stage_plan.md) | Client method | Server route (qc_interface.openapi.json) |
|---|---|---|
| create | `Create(ctx, title, dueDate string) (*Task, error)` | `POST /wrapper/create` |
| get | `Get(ctx, id string) (*Task, error)` | `GET /wrapper/get/{id}` |
| list | `List(ctx, done *bool) ([]Task, error)` | `GET /wrapper/list` |
| update | `Update(ctx, id string, fields TaskUpdate) (*Task, error)` | `PATCH /wrapper/update/{id}` |
| delete | `Delete(ctx, id string) error` | `DELETE /wrapper/delete/{id}` |
| bulk_update | `BulkUpdate(ctx, items []BulkUpdateItem) (*BulkUpdateResult, error)` | `POST /wrapper/bulk_update` |
| (process convention) | — | `GET /health` |

`List`'s `done` filter is modeled as `*bool` (nil = omit filter,
non-nil = filter value) since Go has no native optional-primitive
syntax and the contract's filter is genuinely tri-state (unset vs.
true vs. false). `TaskUpdate` is a plain struct with pointer fields
(`*string`/`*bool`) so "field omitted" and "field explicitly cleared"
stay distinguishable on the wire, matching `qc_interface.openapi.json`'s
`TaskUpdate` schema (all-optional properties).

## Partial-failure representation

`BulkUpdate` returns `(*BulkUpdateResult, error)` where the outer
`error` is non-nil only for whole-call failures (network/transport
error, malformed request) — never for per-item not-found. Per
`language_notes.md`, `BulkUpdateResult` holds a per-item error slice,
preserving input order:

```
BulkUpdateResult { Succeeded []Task; Failed []BulkUpdateFailure }
BulkUpdateFailure { ID string; Err error }
```

The server's `/wrapper/bulk_update` handler always returns `200` (per
`qc_interface.md`) with `{succeeded: Task[], failed: [{id, error}]}`,
regardless of how many items failed — the client library is what turns
that wire shape into the `BulkUpdateResult` split above; the server
itself does no partial-failure translation beyond passing the direct
backend's per-item outcomes through.

## Open questions / judgment calls

- `qc_interface.openapi.json`'s `TaskUpdate` schema declares all
  properties optional with no wire-level way to distinguish "omitted"
  from "explicitly null" — Go has no JSON `undefined`, so pointer
  fields (nil = omitted) are used on the request-building side, and the
  server only forwards fields actually present in the incoming JSON
  body to the backend's update call (using `json.RawMessage`/map
  presence-check, not a fixed-shape struct with pointer fields) so an
  omitted field on the wire into `/wrapper/update/{id}` stays omitted
  going to the direct backend, not defaulted to null. This preserves
  partial-update semantics without needing a code-generation step.
- `list`'s `done` query param: `qc_interface.openapi.json` declares it
  as an optional boolean. The server parses `r.URL.Query().Get("done")`
  and only applies a filter when the param is present and equals `true`
  or `false`; any other value (missing, empty) is treated as "no
  filter," matching `stage_plan.md`'s "omitting the filter returns
  everything."
- Go 1.22+ `ServeMux` method+path patterns are assumed available; if
  the local toolchain is older, the server will fall back to
  manual `r.Method` checks inside path-only handlers (still zero
  dependencies) — this will only be decided if the smoke test in step 5
  reveals an older toolchain.

## File layout

```
wrappers/mock-api/go/
├── go.mod                 # module + go version only, no external requires
├── lib/
│   ├── client.go           # Client struct + typed methods (Create, Get, List, Update, Delete, BulkUpdate)
│   ├── models.go           # Task, TaskUpdate, BulkUpdateItem, BulkUpdateResult, BulkUpdateFailure structs with json tags
│   └── errors.go           # ErrTaskNotFound, ValidationError
└── server/
    └── main.go             # net/http + ServeMux, one handler per qc_interface.openapi.json route + /health
```
