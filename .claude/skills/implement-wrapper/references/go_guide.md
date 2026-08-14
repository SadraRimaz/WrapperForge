# Go implementation guide

Practical, opinionated defaults for `wrappers/<api-name>/go/`. Zero
external dependencies — Go's standard library is more than capable for
both the client and the QC server, and this keeps the proof-of-concept
simple to build and run (`go build` with no `go.sum` surprises).

## Client library (`lib/`)

- **HTTP client: stdlib `net/http`.** No third-party HTTP client
  package needed — `http.Client` plus `encoding/json` covers everything
  this wrapper needs. Don't reach for a router/client framework; this
  is a *client*, not a server, so there's no routing to do here anyway.
- **One struct per resource area (e.g. `Client`), typed methods per
  operation.** `func (c *Client) Create(ctx context.Context, title string, dueDate string) (*Task, error)`,
  `func (c *Client) Get(ctx context.Context, id string) (*Task, error)`,
  etc. — method-per-operation, mirroring `contract.md`, not a single
  generic `Call(op string, ...)`.
- **Accept `context.Context` as the first argument on every method**
  that makes an HTTP call — idiomatic Go, and lets callers set
  timeouts/cancellation without the library needing its own timeout
  config.
- **Errors: explicit `error` returns, not panics.** This is the most
  idiomatic Go choice and also the one `stage_plan.md`/`contract.md`
  usually expect to be called out explicitly for Go. Define sentinel
  or typed errors for the not-found and invalid-input cases (e.g.
  `var ErrTaskNotFound = errors.New("task not found")`, or a
  `*ValidationError` type with a field for which input was bad) so
  callers can `errors.Is` / `errors.As` against them rather than
  string-matching error messages.
- **Partial-failure operations** (e.g. a bulk operation): this is the
  deliberate friction point `stage_plan.md` flags — Go's idiomatic
  answer is a **per-item error slice**, e.g.
  ```go
  type BulkUpdateResult struct {
      Succeeded []Task
      Failed    []BulkUpdateFailure // {ID string; Err error}
  }
  ```
  returned as a normal `(*BulkUpdateResult, error)` where the *outer*
  error is only non-nil if the whole call failed (network error,
  malformed request), and per-item failures live inside the result.
  Don't try to force this into a single Go `error` — that's fighting
  the language, not embracing its idiom.
- **JSON (de)serialization:** define plain structs with `json:"..."`
  tags matching the wire format in `qc_interface.openapi.json` /
  `contract.md`. No need for code generation tooling for a
  proof-of-concept this size — hand-written structs are simpler to
  read and modify.

## QC-facing server (`server/`)

- **Framework: stdlib `net/http` + `http.ServeMux`.** Go 1.22+'s
  `ServeMux` supports method + path pattern matching
  (`mux.HandleFunc("POST /tasks", handler)`) natively, which is enough
  for a 1:1 route-per-operation server without pulling in a router
  package like `chi` or `gin`. If the Go toolchain available is older
  than 1.22, fall back to manually checking `r.Method` inside a
  path-only handler — still zero dependencies, just a bit more
  boilerplate.
- **One route per operation, matching `qc_interface.openapi.json`
  exactly.** Each handler calls the client library and translates its
  `error` into the HTTP response `qc_interface.md` describes — use
  `errors.Is`/`errors.As` against the client's typed errors to pick the
  right status code. No business logic in the handler beyond that
  translation.
- **`PORT` env var, not a hardcoded port.** Read with
  `os.Getenv("PORT")`; a local default (e.g. `"8000"`) is fine only as
  a fallback when the env var is unset.
- **`GET /health`** returns `200` once the server is listening. Keep it
  trivial.
- **No framework middleware, no dependency injection container** — a
  handful of `HandleFunc` calls and a struct holding the client is
  enough for this scope.

## Suggested layout

```
wrappers/<api-name>/go/
├── go.mod                 # module only, no external requires
├── lib/
│   ├── client.go           # Client struct + typed methods
│   ├── models.go           # Task-like structs with json tags
│   └── errors.go           # ErrTaskNotFound, ValidationError, etc.
└── server/
    └── main.go             # net/http server, one route per qc_interface.openapi.json entry
```

## Dependencies

`go.mod` should declare the module and Go version only — no `require`
entries beyond the standard library, unless something in
`stage_plan.md` genuinely can't be done without one (unlikely for this
scope; if it comes up, flag it in the implementation plan for approval
rather than silently adding a dependency).
