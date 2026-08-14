# JavaScript implementation guide

Practical, opinionated defaults for `wrappers/<api-name>/javascript/`.
Zero external dependencies — modern Node.js ships with a global
`fetch` and a built-in `http` module, both of which are enough for this
scope, so there's no `package.json` dependency to install or version.

## Client library (`lib/`)

- **HTTP client: global `fetch`** (available in Node 18+ without any
  import). No `axios`, `node-fetch`, or `got` needed — `fetch` plus
  `async`/`await` covers everything this wrapper needs, and it's the
  same API surface browsers use, which keeps the code portable.
- **One class per resource area, `async` typed methods per operation.**
  `async create(title, dueDate) -> Task`,
  `async get(id) -> Task`, `async list({ done } = {}) -> Task[]`, etc.
  — method-per-operation mirroring `contract.md`'s operation names, not
  a single generic `call(op, ...)` dispatcher.
- **Prefer `async`/`await` over raw `.then()` chains** — reads more
  like the synchronous client libraries in other languages here and is
  the more idiomatic modern style.
- **Use JSDoc type annotations** (`/** @param {string} id @returns
  {Promise<Task>} */`) rather than introducing TypeScript/a build step
  — keeps the wrapper runnable directly with `node`, no compilation
  step, which matters for a minimal-dependency proof-of-concept. If
  this project later adds a TypeScript build step project-wide, revisit
  this; don't introduce it unilaterally from within one language's
  wrapper.
- **Errors: throw typed `Error` subclasses** for the not-found and
  invalid-input cases (e.g. `class TaskNotFoundError extends Error {}`,
  `class TaskValidationError extends Error {}`) rather than returning
  `null`/error codes — idiomatic JS favors thrown errors, and it lets
  callers `catch` and branch on `instanceof`.
- **Partial-failure operations** (e.g. a bulk operation): return a
  plain result object with `succeeded` / `failed` arrays, in the spirit
  of `Promise.allSettled` — i.e. the method itself resolves normally
  with both lists inside it, rather than rejecting. Only reject the
  returned promise if the *whole call* fails (network error, malformed
  request) — same principle as the other languages, just JS's own
  idiom for expressing "the call succeeded, some items in it didn't."

## QC-facing server (`server/`)

- **Framework: built-in `node:http`.** No Express, no Fastify — for a
  handful of 1:1 routes, manually matching on `req.method` and
  `req.url` (or a tiny hand-rolled router function) is simple enough
  and keeps `package.json` dependency-free. A small local helper like:
  ```js
  const routes = { "POST /tasks": handleCreate, "GET /health": handleHealth, ... };
  function route(req) { return routes[`${req.method} ${new URL(req.url, base).pathname}`]; }
  ```
  is enough structure without pulling in a framework.
- **One route per operation, matching `qc_interface.openapi.json`
  exactly.** Each handler calls the client library and translates a
  thrown error into the HTTP response `qc_interface.md` describes
  (`instanceof TaskNotFoundError` → 404, etc.). No business logic
  beyond that translation.
- **`PORT` env var, not a hardcoded port.** Read with
  `process.env.PORT`; a local default (e.g. `8000`) is fine only as a
  fallback when unset.
- **`GET /health`** returns `200` once the server is listening. Keep it
  trivial.
- **Manually parse the request body** (`req.on("data", ...)` /
  `req.on("end", ...)` collecting chunks, then `JSON.parse`) since
  there's no framework doing it automatically — a small shared helper
  function used by every POST/PATCH handler avoids repeating this.

## Suggested layout

```
wrappers/<api-name>/javascript/
├── package.json            # name/version/type:"module" only, no dependencies
├── lib/
│   ├── client.js            # the client class + typed async methods
│   ├── errors.js            # TaskNotFoundError, TaskValidationError, etc.
│   └── models.js            # (optional) JSDoc typedefs for the resource shape
└── server/
    └── main.js              # node:http server, one route per qc_interface.openapi.json entry
```

## Dependencies

`package.json` should declare no `dependencies` at all — everything
needed (`fetch`, `http`) is a Node.js built-in on any reasonably recent
Node version. Set `"type": "module"` to use `import`/`export` syntax
rather than CommonJS `require`, which reads closer to how modern JS SDKs
are written. If a genuine gap shows up that the standard library can't
cover, flag it in the implementation plan for approval rather than
silently adding a dependency.
