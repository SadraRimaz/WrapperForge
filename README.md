# WrapperForge

WrapperForge is a contract-bound multi-agent pipeline that forges idiomatic API client wrapper
libraries in multiple languages from one shared, hand-written spec. A macro agent turns that spec
into a language-agnostic implementation plan and a static set of QC test cases (both human-approved
before use); micro agents implement the wrapper and a small QC-facing server per language; a blind
QC harness then statically replays the approved test cases, calling the real backend and the
wrapper-server side by side and diffing responses. No wrapper source is ever inspected by the QC
step — it is a pure black-box, response-only comparison.

The project ships one worked example end to end: a mock Tasks REST API (`backend/mock_api/`) as the
proof-of-concept backend, wrapped in Python, Go, and JavaScript.

## Why differential testing

Unit tests for a generated wrapper tend to test the wrapper against its own assumptions. Instead,
WrapperForge tests each wrapper by replaying the same logical calls twice — once directly against
the real backend, once through the wrapper's own QC server — and diffing the two responses on the
fields the API contract actually declares. If the wrapper is faithful, the two responses should be
indistinguishable on that basis, regardless of the language or the implementation details behind it.
This catches real divergence (a dropped field, a mis-mapped status code, a wrong error shape) without
requiring a human — or the QC harness — to read a single line of wrapper source.

The test cases themselves are static and pre-approved (`core/<api-name>/cases.json`): each one is a
fully-resolved pair of HTTP calls (`direct` against the real backend, `wrapper` against the QC
server), authored during the macro-planning stage and reviewed before any wrapper code exists. The
QC harness (`tests/audit.py`) does nothing but replay that fixed list and compare — it never spawns a
process, reseeds anything, or derives a call at runtime.

## How it works

```
contract.md (hand-written)
        │
        ▼
  /macro-planning  ──►  drafts/macro_output/<api>/   (stage_plan.md, qc_interface.md,
        │                                              qc_interface.openapi.json, cases.json)
        │  human approval loop ("approved")
        ▼
  core/<api>/                              ← promoted, read-only from here on
        │
        ├──► /implement-wrapper --language python      ──► wrappers/<api>/python/{lib,server}/
        ├──► /implement-wrapper --language go           ──► wrappers/<api>/go/{lib,server}/
        └──► /implement-wrapper --language javascript   ──► wrappers/<api>/javascript/{lib,server}/
                     │  no-code plan + human approval loop ("approved"), then code
                     ▼
             starts that language's QC server, runs tests/audit.py against it,
             reports pass/fail + reason per case
```

Two nested contracts are worth noting explicitly: the client library is built against
`contract.md` (the API's CRUD semantics), and the QC server is a second, smaller product built
against `qc_interface.md` (the HTTP shape used for blind testing) — same pattern, one level down.

1. **Contract** — `core/<api-name>/contract.md` is hand-written, never generated, and fixes the
   operation semantics up front.
2. **Macro-planning** (`/macro-planning`) reads the contract plus the backend's OpenAPI spec and
   drafts four artifacts: a per-operation stage plan, a QC-facing HTTP interface (one route per
   contract operation, both as markdown and OpenAPI), and the static `cases.json` test list. Drafts
   go through an unbounded human-approval loop before being promoted verbatim into `core/<api-name>/`.
3. **Implement-wrapper** (`/implement-wrapper --language <python|go|javascript>`) reads only from an
   already-approved `core/<api-name>/`, drafts a no-code implementation plan, waits for the same
   approval gate, then generates the client library and QC server, smoke-tests the process
   convention, starts the server, and runs the QC harness against it — once per language, three
   separate manual runs for full coverage.
4. **QC harness** (`tests/audit.py`) is a static, language-agnostic replay-and-compare loop with no
   process-spawning or seeding logic. It calls the real backend and the QC server for each case in
   `cases.json`, compares responses restricted to the fields declared in the OpenAPI response schema
   for that path/method/status (falling back to a full-body comparison if the schema is behind an
   unresolved `$ref`), and logs pass/fail with a free-text reason per case.

No stage chains automatically into the next — promoting `core/` doesn't trigger wrapper generation,
and finishing one language doesn't trigger the next. Each step is a separate, explicit, human-
triggered action.

## The worked example: mock Tasks API

`backend/mock_api/` is a small in-memory FastAPI service exposing a `Task` resource
(`id`, `title`, `done`, `due_date`, plus server-generated `priority_score` and `created_at`) and six
operations: `create`, `get`, `list`, `update`, `delete`, and `bulk_update`. `priority_score` and
`created_at` are seeded-random on purpose — they're what make a wrapper's field-level divergence from
the real backend detectable.

`bulk_update` is the deliberate hard case: partial success/failure across multiple items, with at
least one item designed to fail in every test case that touches it. Each language wrapper makes its
own idiomatic choice for representing a part-success/part-failure result (a typed result object in
Python, a per-item error slice in Go, an `allSettled`-style array in JavaScript) — first-pass
divergence here is expected and reported honestly rather than hidden.

All three language wrappers have been generated, approved, and QC'd against this backend
(`wrappers/mock-api/{python,go,javascript}/`), each passing 16–18 of `cases.json`'s 18 cases; the
handful of non-passing cases are a documented artifact of replaying two ordered, mutating calls
(`direct` then `wrapper`) against one shared backend state rather than a wrapper defect.

## Repository layout

```
core/<api-name>/                 approved artifacts only — the only thing /implement-wrapper reads
  contract.md                    hand-written CRUD/error semantics
  stage_plan.md                  macro-planning output: per-operation behavior spec
  qc_interface.md                macro-planning output: human-readable QC HTTP contract
  qc_interface.openapi.json      macro-planning output: machine-readable QC HTTP contract
  cases.json                     macro-planning output: static, pre-resolved QC test cases
  language_notes.md              optional macro-planning output: brief per-language steering notes

drafts/macro_output/<api-name>/  macro-planning scratch space; nothing here is trusted until promoted

backend/mock_api/                the mock Tasks API (the "provider" every wrapper is tested against)

wrappers/<api-name>/
  _plan.<language>.md            implement-wrapper's no-code plan, awaiting approval before any code
  <language>/lib/                client library
  <language>/server/             QC-facing server wrapping that library

tests/audit.py                   static, language-agnostic QC replay-and-compare harness

.claude/skills/
  macro-planning/                 the /macro-planning skill
  implement-wrapper/              the /implement-wrapper skill

doc/plan.md                      full design history and locked decisions — read before making
                                  architectural changes
```

Every artifact under `core/`, `drafts/macro_output/`, and `wrappers/` is namespaced by an `api-name`
slug (derived from the contract file's parent directory), so more than one backing API can coexist —
only `mock-api` exists today.

## Running it

Start the mock backend (always started manually, out-of-band — never spawned by a skill or script):

```bash
cd backend/mock_api
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # first time (Windows)
SEED=42 uvicorn main:app --reload --port 8000        # bash
$env:SEED=42; uvicorn main:app --reload --port 8000  # PowerShell
```

`GET /health` returns `{"status": "ok", "seed": <int>}` once it's up.

Run the QC harness standalone against an already-running wrapper server (normally this happens
automatically as the last step of `/implement-wrapper`):

```bash
python3 tests/audit.py \
  --cases core/mock-api/cases.json \
  --openapi core/mock-api/qc_interface.openapi.json \
  --server-base-url http://localhost:<wrapper-server-port> \
  [--direct-base-url http://localhost:8000]
```

See `CLAUDE.md` for the full command reference (per-language server startup, skill preflight
scripts) and `doc/plan.md` for the complete design rationale and phase-by-phase history.

## Adding a fourth language

No pipeline changes are needed. Add a new per-language guide under
`.claude/skills/implement-wrapper/references/` describing that language's fixed defaults (client
library approach, error-handling shape, partial-failure representation for `bulk_update`), then run
`/implement-wrapper --language <new-language>` against the same already-approved `core/mock-api/` —
the macro-planning artifacts and `cases.json` are language-agnostic and require no changes.

## Status

Mock backend, `/macro-planning`, `/implement-wrapper`, and `tests/audit.py` are all built and have
been run end to end. `core/mock-api/` is approved and promoted; all three language wrappers
(Python, Go, JavaScript) are generated and QC'd. Result-table generation and a `results/` artifact
directory are explicitly deferred — see `doc/plan.md` for what's left.
