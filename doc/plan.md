# WrapperForge — Multi-Language API/DB Wrapper Factory (Implementation Plan)

**Status:** Mock API, `core/mock-api/contract.md`, the `macro-planning` skill (Phase 2), and the `implement-wrapper` skill (Phase 3) built. `core/mock-api/` is not yet fully approved/promoted in this environment (only `contract.md` exists there so far), so `/implement-wrapper` hasn't actually been run end-to-end against real content yet — next step is running `/macro-planning` for real, then `/implement-wrapper` × 3 languages.
**Current scope:** Pipeline — `API docs → macro-planning skill → human approval loop → 3× implement-wrapper skill (per-language plan + approval + code) → 3 working wrapper+server pairs`. Results logging (`results.json`) and paper-table generation are explicitly deferred.

**Multi-API note (added during Phase 2 build-out):** WrapperForge is designed to plan and build wrappers for more than one backing API over time, not only the bundled mock Tasks API. Every macro-planning artifact is namespaced by an `api-name` slug derived from the contract file's parent directory, so `core/`, `drafts/macro_output/`, and `wrappers/` can hold multiple independent APIs side by side without collision. This is why `core/contract.md` was relocated to `core/mock-api/contract.md` (see Phase 0/1 updates below) — a bare `core/contract.md` doesn't encode which API it belongs to.

**Per-language plan/approval gate (added during Phase 3 build-out):** `/implement-wrapper` was built with its own no-code implementation-plan-then-approval step, one level below macro-planning's. This wasn't in the original Phase 3 sketch — see the Phase 3 section below for the full rationale.

---

## Design decisions (locked)

These reflect the finalized shape of the project:

- **Backing service:** Mock REST API only, FastAPI.
- **Domain:** Tasks API (title, done, due_date, + generated fields).
- **Wrapper definition:** Wrapper = **client library**; a separate **QC-facing server** (in the same language) wraps it.
- **QC method:** Differential testing — same seeded backend, called directly vs. via wrapper-server, responses compared.
- **Macro-agent scope:** One run, language-agnostic, produces Stage Plan + `qc_interface.md` + OpenAPI spec.
- **Reviewer step:** Unbounded human-or-AI-judge approval loop on a draft artifact; no cap, no auto-escalation.
- **Micro-agent scope:** Per-language, builds wrapper + QC-facing server, reads only from approved `core/`. Drafts a no-code implementation plan first and waits for the same "approved"-keyword gate as the macro-agent, one level down, before generating any code (locked during Phase 3 build-out — see Phase 3 section).
- **Comparison strictness:** Schema-driven allowlist (OpenAPI-declared fields only).
- **Failure logging:** Categorized — `pass | value_mismatch | shape_invalid | direct_call_error | wrapper_call_error` (deferred until results logging phase).
- **Harder 6th operation:** `bulk_update` with partial failure.
- **API keys:** Explicitly dropped to keep scope tight.
- **Per-language dependencies (locked during Phase 3 build-out):** minimal/no external dependencies, favoring standard-library or single well-known packages over frameworks. Python: `requests` + FastAPI/`uvicorn`. Go: standard library only (`net/http`, `encoding/json`). JavaScript: standard library only (global `fetch`, `node:http`) — no `package.json` dependencies.

---

## Architecture Overview

```
                     ┌─────────────────────┐
                     │   core/ (approved)   │
                     │  contract.md         │
                     │  stage_plan.md        │
                     │  qc_interface.md      │
                     │  qc_interface.openapi.json │
                     └──────────┬───────────┘
                                │ read-only
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
  implement-wrapper      implement-wrapper       implement-wrapper
  (python)                (go)                    (javascript)
        │                       │                       │
        ▼ plan → approve → code ▼ plan → approve → code ▼ plan → approve → code
  wrappers/python/        wrappers/go/            wrappers/javascript/
    lib/  (client lib)      lib/                    lib/
    server/ (QC shim)       server/                 server/

  QC (tests/audit.py) — per test case, per language server:
    1. spawn mock backend (seed=S) → call directly → capture A → kill
    2. spawn mock backend (seed=S) → call via language's QC server (already running) → capture B → kill
    3. compare A vs B on OpenAPI-declared fields only → log categorized result
```

**Two nested contract instances** (worth stating explicitly in the paper): the wrapper is a product built against `contract.md` (the Tasks CRUD semantics); the QC server is a second, smaller product built against `qc_interface.md` (the HTTP-shape-for-blind-testing contract). Same pattern, one level down.

---

## Domain: Tasks API

Chosen for being simple, practical, and legible, while still giving QC meaningful fields to catch divergence on.

**Resource: `Task`**
```
id: string (server-generated)
title: string
done: boolean
due_date: date (ISO 8601)
priority_score: float        # server-generated, seeded-random — the key QC differentiator field
created_at: datetime          # server-generated, seeded-random jitter
```

**Base operations (5):**
- `create(title, due_date) -> Task`
- `get(id) -> Task | 404`
- `list(done: bool | None) -> Task[]`
- `update(id, fields) -> Task | 404`
- `delete(id) -> 204 | 404`

**Harder 6th operation:**
- `bulk_update(items: [{id, fields}]) -> { succeeded: [...], failed: [{id, error}] }`
  — at least one item in every test case is designed to fail (bad id or invalid field), forcing each language wrapper/server to make an explicit, idiomatic choice about partial-failure representation (Go: per-item error slice; Python: exception vs. result-object choice; JS: `Promise.allSettled`-style). This is the deliberate friction point required by both repo plans — expect (and document) real first-pass divergence here.

---

## Phase 0: Naming & Scaffolding

- [x] Repo name: `WrapperForge`.
- [x] Create GitHub repo, license, `.gitignore`.
- [x] Scaffold (mock API and its docs already built; rest to follow):
```
WrapperForge/
├── core/                                  # APPROVED artifacts only — micro-agents read ONLY from here
│   └── <api-name>/                        # one namespaced folder per backing API (e.g. mock-api/)
│       ├── contract.md                    # hand-written: CRUD semantics for this API — DONE for mock-api
│       ├── stage_plan.md                  # macro-planning output, promoted from drafts/ on approval
│       ├── qc_interface.md                # macro-planning output, promoted from drafts/ on approval
│       ├── qc_interface.openapi.json      # macro-planning output, promoted from drafts/ on approval
│       └── language_notes.md              # optional: macro-planning output, promoted on approval
├── drafts/
│   └── macro_output/
│       └── <api-name>/                    # macro-planning writes/revises here; nothing here is trusted
│           ├── stage_plan.md
│           ├── qc_interface.md
│           ├── qc_interface.openapi.json
│           └── language_notes.md          # optional
├── backend/
│   └── mock_api/                  # hand-written FastAPI backend (the "provider") — DONE
│       ├── main.py                # accepts SEED env var, exposes Tasks CRUD + bulk_update
│       ├── seed.py                # seeded RNG helpers for priority_score, created_at jitter
│       ├── openapi.json           # generated spec — the API docs the macro-planning skill consumes
│       └── requirements.txt
├── wrappers/
│   └── <api-name>/                # namespaced per API, mirrors core/<api-name>/
│       ├── _plan.python.md        # implement-wrapper output: no-code plan, awaits approval before code
│       ├── _plan.go.md            # implement-wrapper output: no-code plan, awaits approval before code
│       ├── _plan.javascript.md    # implement-wrapper output: no-code plan, awaits approval before code
│       ├── python/
│       │   ├── lib/               # client library (implement-wrapper output, post-approval)
│       │   └── server/            # QC-facing server (implement-wrapper output, post-approval)
│       ├── go/
│       │   ├── lib/
│       │   └── server/
│       └── javascript/
│           ├── lib/
│           └── server/
├── tests/
│   ├── cases.json                 # hand-written: {operation, input, seed, edge_case_label?} — NO expected_output
│   └── audit.py                   # blind QC: process orchestration + differential comparison + categorized logging
├── .claude/
│   └── skills/
│       ├── macro-planning/                        # DONE — Phase 2, renamed from the earlier "macro" placeholder
│       │   ├── SKILL.md
│       │   ├── scripts/
│       │   │   ├── preflight.py                    # validates inputs, derives api-name slug
│       │   │   └── promote.py                      # drafts/macro_output/<api>/ → core/<api>/ on approval
│       │   └── references/
│       │       ├── stage_plan_template.md
│       │       ├── qc_interface_template.md
│       │       ├── qc_interface_openapi_guidance.md
│       │       └── directory_conventions.md
│       └── implement-wrapper/                      # DONE — Phase 3
│           ├── SKILL.md                            # (no separate reviewer skill — see Phase 2 note; this skill's plan/approval gate is a different, per-language mechanism — see Phase 3 note)
│           ├── scripts/
│           │   ├── preflight.py                    # validates language + core/<api>/ completeness
│           │   └── smoke_test_server.py            # verifies PORT + GET /health convention
│           └── references/
│               ├── plan_template.md                # shape of the no-code _plan.<language>.md gate artifact
│               ├── python_guide.md                 # requests + FastAPI, typed exceptions
│               ├── go_guide.md                     # stdlib net/http only, explicit error returns
│               └── javascript_guide.md             # global fetch + stdlib node:http, thrown typed errors
├── results/                       # deferred — not populated in this phase
├── README.md
└── LICENSE
```
- [ ] Confirm runtimes available locally: Python, Go, Node.

## Phase 1: Core Contract (hand-written, before any agent runs)

- [x] Write `core/mock-api/contract.md` by hand: the 6 operations above, exact field names/types, error semantics (not-found on missing id, invalid-input on malformed request). This is the fixed foundation, written directly rather than delegated. **(Relocated during Phase 2 build-out from `core/contract.md` to `core/mock-api/contract.md`** — the macro-planning skill derives its `api-name` namespace from this file's parent directory, so a bare `core/contract.md` doesn't encode which API it belongs to. A single-API layout was ambiguous the moment a second API was in scope, so contract files now live one level deeper, under their own `<api-name>/` folder, matching every other artifact in `core/`.)
- [x] Build `backend/mock_api/main.py` (FastAPI): implements all 6 operations against in-memory storage. Accepts a `SEED` env var at startup; `priority_score` and `created_at` jitter are derived deterministically from that seed via a `random.Random(seed)` instance scoped to the process (see `seed.py`). Exposes `GET /health`.
- [x] Confirmed the mock backend produces **identical output across two separate process starts with the same `SEED`**, given the same call sequence — validated by hand (start, create two tasks, kill, restart same seed, repeat the same two creates, diff `priority_score`/`created_at`: identical). This load-bearing assumption for the differential-QC design holds.
- [x] FastAPI's auto-generated OpenAPI spec saved as `backend/mock_api/openapi.json` — this is the "API docs" the macro-planning skill consumes in Phase 2.

## Phase 2: Macro-Agent + Approval Gate — DONE

- [x] Write `.claude/skills/macro-planning/SKILL.md` (renamed from the originally planned `.claude/skills/macro/SKILL.md` — the agentskills.io spec requires the frontmatter `name` field to match the parent folder name, and the skill is invoked as `/macro-planning`, so the folder itself is `macro-planning/`). Given a hand-written contract file (e.g. `core/mock-api/contract.md`) + that API's OpenAPI spec (e.g. `backend/mock_api/openapi.json`), both passed explicitly by the user (the skill does **not** scan the repo — only acts on files the user references), the macro-planning skill (single run, language-agnostic) produces, into `drafts/macro_output/<api-name>/`:
  1. `stage_plan.md` — per-operation behavior spec, what the seeded/generated fields mean and how they must behave, edge cases (not-found, invalid input, bulk partial-failure semantics). High-level only — no code, no per-language implementation choices.
  2. `qc_interface.md` — human-readable QC-facing HTTP contract: one route per contract operation (1:1 mapping — see rationale below), method, request/response shape. Includes the **fixed process convention**: every language's QC server must bind to a `PORT` env var and expose `GET /health` → 200.
  3. `qc_interface.openapi.json` — machine-readable version of the same routes.
  4. Optional brief per-language guidance notes (`language_notes.md`, a few lines each, not detailed idiom tables) — e.g. "Go: prefer explicit error returns"; "JS: prefer async/await." Steering only, not design.
- [x] **1:1 endpoint mapping rationale** (locked decision): one QC route per contract operation (`POST /wrapper/create`, `GET /wrapper/get/{id}`, etc.), not a single uniform `/invoke`. Reasons: mirrors real SDK method-per-operation shape; gets REST-semantics coverage (status codes) for free; a uniform endpoint would let broken wrappers hide behind generic 200s; cleaner per-operation pass/fail table for the paper. Encoded in `references/qc_interface_template.md` and `references/qc_interface_openapi_guidance.md` so it survives across different APIs, not just the mock Tasks API.
- [x] **Approval loop** (unbounded, no auto-escalation): the user reviews `drafts/macro_output/<api-name>/*` in conversation, gives feedback, macro-planning revises in place. Repeat until the user's message contains an explicit approval keyword (**"approved"**, case-insensitive, plus close variants like "approve"). Anything else — including unambiguous enthusiasm without the keyword — is treated as feedback-mode, and the skill asks directly rather than inferring approval.
- [x] On approval: `scripts/promote.py` copies `drafts/macro_output/<api-name>/*` → `core/<api-name>/*` verbatim (refusing to run if the draft set is incomplete, and never touching `contract.md`). `core/<api-name>/` is now the only location a future `.claude/skills/implement-wrapper/SKILL.md` is permitted to read from.
- [x] No separate reviewer skill for this project (deliberate design choice, unchanged): the approval gate itself — human or AI-judge, interchangeable — *is* the reviewer mechanism, implemented as a draft/promote workflow rather than a separate agent persona with a bounded iteration count. The dial still exists — human-gated vs. delegated-to-an-AI-judge — it's just implemented as "who approves the promotion," not "how many agent-vs-agent rounds run."
- [x] **Multi-API generality** (new, added during this phase's build-out, not in the original Phase 2 scope as first drafted): the macro-planning skill is not hardcoded to the mock Tasks API. Every artifact it touches is namespaced by an `api-name` slug, derived from the contract file's parent directory name (`core/<api-name>/contract.md`) via `scripts/preflight.py`, so `core/`, `drafts/macro_output/`, and (later) `wrappers/` can hold multiple independent APIs side by side. Running macro-planning again for a second API (e.g. `core/billing-api/contract.md`) is fully independent of `core/mock-api/`. See `references/directory_conventions.md`.
- [x] Built and tested `scripts/preflight.py` (validates both input files, parses the OpenAPI JSON, derives and sanity-checks the `api-name` slug, refuses to proceed silently if the slug looks generic/wrong) and `scripts/promote.py` (copies the three-or-four promoted files, refuses to run on an incomplete draft set, is idempotent on re-run, never deletes or overwrites `contract.md`). Both verified against the real `core/mock-api/contract.md` + `backend/mock_api/openapi.json` inputs.

**Note (from the Phase 2 session):** `/implement-wrapper` (Phase 3) was intentionally not built in the Phase 2 session — that pass covered `/macro-planning` only. It has since been built; see the Phase 3 section below. The macro-planning skill still does not chain into `/implement-wrapper` automatically, even after a successful promotion — running the language wrappers remains a separate, manual step per language.

## Phase 3: Micro-Agent / `/implement-wrapper` (run 3×, once per language) — DONE

- [x] Write `.claude/skills/implement-wrapper/SKILL.md`. Given `core/<api-name>/*` (contract, stage plan, qc_interface + OpenAPI, for a specific approved API) and a required `--language` argument (`python` | `go` | `javascript`, exactly one per run — no "all" shortcut), the skill builds, for that language only:
  1. `wrappers/<api-name>/{lang}/lib/` — an idiomatic client library implementing all `contract.md` operations against the backend's real HTTP API (OpenAI-SDK-style: typed methods, per-language-appropriate error handling).
  2. `wrappers/<api-name>/{lang}/server/` — a small server, in the same language, that imports/uses the client library and exposes exactly the routes defined in `core/<api-name>/qc_interface.openapi.json`. Must honor the fixed process convention (`PORT` env var, `GET /health`).
- [x] **New: per-language plan + approval gate** (locked decision, added during this phase's build-out — not in the original Phase 3 sketch, which had micro-agents build directly with no gate). Before writing any code, the skill drafts `wrappers/<api-name>/_plan.<language>.md` — a **no-code** implementation plan: which library/framework choices apply (from the fixed per-language defaults below), the operation → client-method → server-route mapping, how the partial-failure operation is represented in this language, and any open questions. The user must reply with the same explicit approval keyword convention as macro-planning (**"approved"**, case-insensitive) before code generation starts; anything else is treated as feedback and the plan is revised in place. One plan file per language (`_plan.python.md`, `_plan.go.md`, `_plan.javascript.md`) living in the shared `wrappers/<api-name>/` folder, not deleted after code is generated. Rationale: catches a wrong per-language design choice (error-handling shape, partial-failure representation, a missed operation) before any files exist, mirroring the macro-planning approval pattern one level down, at the user's request.
- [x] **Fixed per-language defaults** (locked, encoded in `references/{python,go,javascript}_guide.md` so `/implement-wrapper` doesn't re-decide them per run):
  - **Python:** `requests` for the client, FastAPI + `uvicorn` for the QC server, typed exceptions (e.g. `TaskNotFoundError`) for not-found/invalid-input, a typed result object (not an exception) for partial-failure operations.
  - **Go:** standard library only (`net/http`, `encoding/json`, `net/http.ServeMux` for routing) — zero external dependencies. Explicit `error` returns, `context.Context` as first argument on client methods, a per-item error slice for partial-failure operations.
  - **JavaScript:** standard library only — global `fetch` for the client, built-in `node:http` for the QC server (no Express/Fastify), zero `package.json` dependencies. `async`/`await`, thrown typed `Error` subclasses, an `allSettled`-style result object for partial-failure operations.
  - All three were chosen for minimal/no external dependencies per explicit request, favoring standard-library or single well-known packages over frameworks.
- [x] Built and tested `scripts/preflight.py` (validates the `--language` value and that `core/<api-name>/` has all four required approved files — `contract.md`, `stage_plan.md`, `qc_interface.md`, `qc_interface.openapi.json` — refusing to proceed the same way `promote.py` refuses an incomplete draft set; warns, without blocking, if `wrappers/<api-name>/<language>/` already has prior output) and `scripts/smoke_test_server.py` (language-agnostic check that a running server honors the `PORT` + `GET /health` convention, with retry/timeout). Both verified against simulated `core/mock-api/` content and a toy stdlib HTTP server, including the incomplete-`core/` refusal case matching this repo's actual current state (see note below).
- [x] Confirm each language's server can be started standalone, points at the already-running backend, and manually smoke-test one call per operation before moving to full QC — encoded as workflow step 5 in `SKILL.md`, using `smoke_test_server.py` for the process-convention check plus a manual per-operation pass.
- [ ] Run Python, then Go, then JS — sequential, manual invocations of the same skill with a different `--language` value each time. `/macro-planning` does **not** trigger this automatically; it is a deliberate, separate step per the Phase 2 decision above. **Not yet run for real in this environment** — see note below.
- [x] `wrappers/<api-name>/` namespacing (decision carried over from Phase 2's multi-API generality work): mirrors `core/<api-name>/`, so building wrappers for a second API doesn't collide with the first.

**Not yet exercised end-to-end in this environment:** `core/mock-api/` currently contains only `contract.md` — `/macro-planning` has not actually been run and approved for mock-api yet in this session, so `stage_plan.md`, `qc_interface.md`, and `qc_interface.openapi.json` don't exist there. `/implement-wrapper`'s `preflight.py` correctly refuses to proceed against this incomplete `core/mock-api/` (verified). The skill itself is complete and was validated against simulated complete `core/` content plus a toy server; the next real step is running `/macro-planning` for mock-api to completion, then `/implement-wrapper --language python` (then `go`, then `javascript`) against the real, approved artifacts.

## Phase 4: Blind QC — Differential Testing (`tests/audit.py`)

- [ ] Write `tests/cases.json` by hand — coverage-driven, not auto-generated from the OpenAPI spec (the point of this file is deliberate edge-case judgment, and it's small enough — roughly 15–20 entries across 6 operations — that hand-authoring costs little and buys more). Each entry: `{case_id, operation, input, seed, edge_case_label?}` — no `expected_output` field; that's derived live.
- [ ] Include at least: 1 happy-path case per operation, 1 not-found case, 1 invalid-input case, and 2–3 `bulk_update` cases specifically constructed so at least one item fails per case.
- [ ] Implement `tests/audit.py` orchestration, per test case, per language:
  1. Spawn mock backend with `SEED=case.seed`, wait for `/health`, call the operation **directly** against the backend → response **A**, kill backend process.
  2. Spawn mock backend again with the same `SEED`, wait for `/health`. The language's QC server is already running (started once at the top of that language's whole run, stays up across all its cases) and now has a live backend to proxy to. Call the **same operation via the language server** → response **B**, kill backend.
  3. Load the relevant OpenAPI schema for that operation's response; compare **A vs B only on schema-declared fields** (ignore incidental extras like request IDs or headers).
  4. Log a categorized result: `pass` / `value_mismatch` (+ which fields) / `shape_invalid` (response failed schema validation) / `direct_call_error` (backend itself errored unexpectedly) / `wrapper_call_error` (language server errored where backend didn't).
- [ ] Confirm `audit.py` never reads any file under `wrappers/{lang}/` — it only starts processes by the fixed convention and speaks HTTP. True black box.
- [ ] Restart scope (locked decision): only the mock **backend** restarts per test case; each language's **QC server** starts once per language run and stays up for that language's whole case list. Reasoning: the QC server holds no state worth resetting, and restarting 3 servers × N cases is strictly more overhead than restarting 1 backend × N cases for no isolation benefit.

## Phase 5: README & Polish

- [ ] Write README covering: what this is, the two nested contracts (`contract.md` + `qc_interface.md`), why differential/seeded testing was chosen over static fixtures (good selling point — lead with it), how to add a 4th language.
- [ ] `results/` and results-table generation are **deferred** — do not block on this for v1 of the pipeline.
- [ ] Tag `v0.1` once all 3 language wrapper+server pairs pass Phase 4 QC (or have honestly-logged, categorized failures — a clean all-pass table is not required, and `bulk_update` friction is expected and fine to show).

## Open items deferred to later passes (explicitly not blocking right now)

- `results.json` schema + population.
- Any retry-ceiling reporting for a future write-up (moot for now since the reviewer step here is unbounded-until-approved, not loop-count-bounded).

## Definition of Done for this phase

- [x] `core/mock-api/contract.md` hand-written and stable (relocated from `core/contract.md` during Phase 2 for `api-name` namespacing — see Phase 1 note above).
- [x] Mock backend built, seeded-determinism validated by hand.
- [x] Macro-planning skill (`/macro-planning`) produces all 3 required draft artifacts (+ optional `language_notes.md`); approval loop, keyed on an explicit "approved" keyword, reaches promotion; `scripts/promote.py` copies drafts to `core/<api-name>/` verbatim and was verified end-to-end against the real mock-api inputs.
- [x] Implement-wrapper skill (`/implement-wrapper`) built: per-language, `--language`-gated, drafts a no-code `_plan.<language>.md` and waits for the same "approved" keyword before generating `lib/` + `server/`; `scripts/preflight.py` and `scripts/smoke_test_server.py` verified against simulated complete `core/` content and a toy server.
- [ ] All 3 language `/implement-wrapper` runs complete against real, approved `core/mock-api/` content; each produces a working `lib/` + `server/`. **(Not started for real — blocked on running `/macro-planning` to completion for mock-api first; see Phase 3 note above.)**
- [ ] `tests/cases.json` hand-written, covering all 6 operations incl. bulk_update partial-failure cases.
- [ ] `tests/audit.py` runs end-to-end against all 3 languages, produces categorized pass/fail output (console output is sufficient for now — no results.json required yet).
