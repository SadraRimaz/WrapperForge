# WrapperForge — Multi-Language API/DB Wrapper Factory (Implementation Plan)

**Status:** Mock API, `core/mock-api/contract.md`, the `macro-planning` skill (Phase 2), the `implement-wrapper` skill (Phase 3), and the static `tests/audit.py` QC runner (Phase 4) are built. `core/mock-api/` is not yet fully approved/promoted in this environment (only `contract.md` exists there so far), so `/implement-wrapper` hasn't actually been run end-to-end against real content yet — next step is running `/macro-planning` for real, then `/implement-wrapper` × 3 languages (each of which now runs QC automatically as its final step).
**Current scope:** Pipeline — `API docs → macro-planning skill (incl. cases.json) → human approval loop → 3× implement-wrapper skill (per-language plan + approval + code + start server + run tests/audit.py) → 3 working, QC'd wrapper+server pairs`. Results logging (`results.json`) and paper-table generation are explicitly deferred.

**QC redesign (added during Phase 4 build-out):** the original Phase 4 sketch had `tests/audit.py` itself spawn/reseed the mock backend per test case and derive comparisons live. This has been replaced with a cleaner split: `/macro-planning` now generates a fourth required draft artifact, `cases.json` — a fully-resolved, human-approved, static list of test items (each with a concrete `direct` call spec against the real backend and a `wrapper` call spec against the language's QC server) — and `tests/audit.py` is now a pure, static, language-agnostic replay-and-compare loop with **no process-spawning or seeding logic at all**. Both the real backend (started manually by the user, out-of-band) and each language's QC server (started by `/implement-wrapper` itself, as its final step, which then also invokes `audit.py` and reports results) are outside `audit.py`'s responsibility. See the Phase 4 section below for the full rationale and shape.

**Multi-API note (added during Phase 2 build-out):** WrapperForge is designed to plan and build wrappers for more than one backing API over time, not only the bundled mock Tasks API. Every macro-planning artifact is namespaced by an `api-name` slug derived from the contract file's parent directory, so `core/`, `drafts/macro_output/`, and `wrappers/` can hold multiple independent APIs side by side without collision. This is why `core/contract.md` was relocated to `core/mock-api/contract.md` (see Phase 0/1 updates below) — a bare `core/contract.md` doesn't encode which API it belongs to.

**Per-language plan/approval gate (added during Phase 3 build-out):** `/implement-wrapper` was built with its own no-code implementation-plan-then-approval step, one level below macro-planning's. This wasn't in the original Phase 3 sketch — see the Phase 3 section below for the full rationale.

---

## Design decisions (locked)

These reflect the finalized shape of the project:

- **Backing service:** Mock REST API only, FastAPI.
- **Domain:** Tasks API (title, done, due_date, + generated fields).
- **Wrapper definition:** Wrapper = **client library**; a separate **QC-facing server** (in the same language) wraps it.
- **QC method:** Differential testing — same backend, called directly vs. via wrapper-server, responses compared. **(Revised during Phase 4 build-out — see below.)** Originally: `audit.py` itself spawned/killed the mock backend per test case with a fresh `SEED`, so direct and wrapper calls saw identical seeded state. Now: `/macro-planning` generates a static, pre-approved `cases.json` (fully-resolved `direct`/`wrapper` call specs, no live derivation), and `audit.py` is a pure replay-and-compare loop against two already-running servers — the real backend (started manually by the user, out-of-band) and the language's QC server (started by `/implement-wrapper` itself). `audit.py` no longer spawns, kills, or seeds any process.
- **Macro-agent scope:** One run, language-agnostic, produces Stage Plan + `qc_interface.md` + OpenAPI spec + `cases.json` (added during Phase 4 build-out).
- **Reviewer step:** Unbounded human-or-AI-judge approval loop on a draft artifact; no cap, no auto-escalation. Now covers 4 draft artifacts (was 3) since `cases.json` is approved in the same loop.
- **Micro-agent scope:** Per-language, builds wrapper + QC-facing server, reads only from approved `core/`. Drafts a no-code implementation plan first and waits for the same "approved"-keyword gate as the macro-agent, one level down, before generating any code (locked during Phase 3 build-out — see Phase 3 section). **Extended during Phase 4 build-out:** after code generation and a process-convention smoke test, this same skill run starts the generated server and invokes `tests/audit.py` against it, reporting results in chat — QC is now the automatic final step of each language's `/implement-wrapper` run, not a separately-invoked script.
- **Comparison strictness:** Schema-driven allowlist (OpenAPI-declared fields only). Unchanged by the Phase 4 redesign.
- **Failure logging:** Simplified during Phase 4 build-out from a categorized taxonomy (`pass | value_mismatch | shape_invalid | direct_call_error | wrapper_call_error`) to **`pass` / `fail` + a free-text reason string** per case, since `audit.py` no longer distinguishes categories of process/transport failure the way the live-spawning version could.
- **Harder 6th operation:** `bulk_update` with partial failure.
- **API keys:** Explicitly dropped to keep scope tight.
- **Per-language dependencies (locked during Phase 3 build-out):** minimal/no external dependencies, favoring standard-library or single well-known packages over frameworks. Python: `requests` + FastAPI/`uvicorn`. Go: standard library only (`net/http`, `encoding/json`). JavaScript: standard library only (global `fetch`, `node:http`) — no `package.json` dependencies.

---

## Architecture Overview

```
                     ┌─────────────────────────────┐
                     │      core/ (approved)        │
                     │  contract.md                 │
                     │  stage_plan.md                │
                     │  qc_interface.md               │
                     │  qc_interface.openapi.json     │
                     │  cases.json                     │
                     └──────────┬───────────────────┘
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
        │                       │                       │
        ▼ start server, run tests/audit.py, report      ▼ (same, per language)
        ▼ (same, per language)

  Real backend (e.g. mock API): started manually by the user, out-of-band,
  before any /implement-wrapper run. Not spawned or managed by any skill/script.

  QC (tests/audit.py) — static, language-agnostic, no process-spawning:
    for each item in core/<api-name>/cases.json (already-approved, fully resolved):
    1. call item.direct against the real backend (already running) → response A
    2. call item.wrapper against the language's QC server (already running) → response B
    3. compare A vs B on OpenAPI-declared fields only (core/<api-name>/qc_interface.openapi.json)
    4. log pass / fail + free-text reason
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
│       ├── cases.json                     # macro-planning output, promoted from drafts/ on approval — static, fully-resolved QC test-case list (added Phase 4 build-out)
│       └── language_notes.md              # optional: macro-planning output, promoted on approval
├── drafts/
│   └── macro_output/
│       └── <api-name>/                    # macro-planning writes/revises here; nothing here is trusted
│           ├── stage_plan.md
│           ├── qc_interface.md
│           ├── qc_interface.openapi.json
│           ├── cases.json                 # added Phase 4 build-out
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
│   └── audit.py                   # blind QC: static, language-agnostic replay-and-compare loop — no process spawning, no seeding. Loads core/<api-name>/cases.json (NOT hand-written under tests/ anymore — see Phase 4)
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
│       │       ├── cases_template.md               # shape/coverage guidance for cases.json (added Phase 4 build-out)
│       │       └── directory_conventions.md
│       └── implement-wrapper/                      # DONE — Phase 3; extended Phase 4 build-out to also run QC
│           ├── SKILL.md                            # (no separate reviewer skill — see Phase 2 note; this skill's plan/approval gate is a different, per-language mechanism — see Phase 3 note; final step now starts the server and runs tests/audit.py — see Phase 4 note)
│           ├── scripts/
│           │   ├── preflight.py                    # validates language + core/<api>/ completeness (now 5 required files, incl. cases.json)
│           │   └── smoke_test_server.py            # verifies PORT + GET /health convention — a pre-check before the audit.py run, not a replacement for it
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

- [x] Write `.claude/skills/macro-planning/SKILL.md` (renamed from the originally planned `.claude/skills/macro/SKILL.md` — the agentskills.io spec requires the frontmatter `name` field to match the parent folder name, and the skill is invoked as `/macro-planning`, so the folder itself is `macro-planning/`). Given a hand-written contract file (e.g. `core/mock-api/contract.md`) + that API's OpenAPI spec (e.g. `backend/mock_api/openapi.json`) + the real backend's base URL (e.g. `http://localhost:8000`, a plain string the user supplies in conversation — **added during Phase 4 build-out**), all passed explicitly by the user (the skill does **not** scan the repo — only acts on files/values the user references), the macro-planning skill (single run, language-agnostic) produces, into `drafts/macro_output/<api-name>/`:
  1. `stage_plan.md` — per-operation behavior spec, what the seeded/generated fields mean and how they must behave, edge cases (not-found, invalid input, bulk partial-failure semantics). High-level only — no code, no per-language implementation choices.
  2. `qc_interface.md` — human-readable QC-facing HTTP contract: one route per contract operation (1:1 mapping — see rationale below), method, request/response shape. Includes the **fixed process convention**: every language's QC server must bind to a `PORT` env var and expose `GET /health` → 200.
  3. `qc_interface.openapi.json` — machine-readable version of the same routes.
  4. `cases.json` — **added during Phase 4 build-out** (see Phase 4 section for full rationale). A fully-resolved, static list of QC test items — each with a concrete `direct` call spec (method/endpoint/body against the real backend) and `wrapper` call spec (against the QC server), no `expected_output` field (the real backend's live response *is* the expected output). Roughly 15–20 cases: happy path per operation, not-found, invalid-input, 2–3 `bulk_update` partial-failure cases. Carries the real backend's base URL (`direct_base_url`) at the top of the file. This is now a required 4th draft artifact, approved in the same loop as the other three, and is what `tests/audit.py` replays later — see `references/cases_template.md`.
  5. Optional brief per-language guidance notes (`language_notes.md`, a few lines each, not detailed idiom tables) — e.g. "Go: prefer explicit error returns"; "JS: prefer async/await." Steering only, not design.
- [x] **1:1 endpoint mapping rationale** (locked decision): one QC route per contract operation (`POST /wrapper/create`, `GET /wrapper/get/{id}`, etc.), not a single uniform `/invoke`. Reasons: mirrors real SDK method-per-operation shape; gets REST-semantics coverage (status codes) for free; a uniform endpoint would let broken wrappers hide behind generic 200s; cleaner per-operation pass/fail table for the paper. Encoded in `references/qc_interface_template.md` and `references/qc_interface_openapi_guidance.md` so it survives across different APIs, not just the mock Tasks API.
- [x] **Approval loop** (unbounded, no auto-escalation): the user reviews `drafts/macro_output/<api-name>/*` in conversation, gives feedback, macro-planning revises in place. Repeat until the user's message contains an explicit approval keyword (**"approved"**, case-insensitive, plus close variants like "approve"). Anything else — including unambiguous enthusiasm without the keyword — is treated as feedback-mode, and the skill asks directly rather than inferring approval.
- [x] On approval: `scripts/promote.py` copies `drafts/macro_output/<api-name>/*` → `core/<api-name>/*` verbatim (refusing to run if the draft set is incomplete, and never touching `contract.md`). `core/<api-name>/` is now the only location a future `.claude/skills/implement-wrapper/SKILL.md` is permitted to read from. **Updated during Phase 4 build-out:** the required-file set `promote.py` checks/copies grew from 3 to 4 (`stage_plan.md`, `qc_interface.md`, `qc_interface.openapi.json`, `cases.json`), verified against a synthetic incomplete-then-complete draft set.
- [x] No separate reviewer skill for this project (deliberate design choice, unchanged): the approval gate itself — human or AI-judge, interchangeable — *is* the reviewer mechanism, implemented as a draft/promote workflow rather than a separate agent persona with a bounded iteration count. The dial still exists — human-gated vs. delegated-to-an-AI-judge — it's just implemented as "who approves the promotion," not "how many agent-vs-agent rounds run."
- [x] **Multi-API generality** (new, added during this phase's build-out, not in the original Phase 2 scope as first drafted): the macro-planning skill is not hardcoded to the mock Tasks API. Every artifact it touches is namespaced by an `api-name` slug, derived from the contract file's parent directory name (`core/<api-name>/contract.md`) via `scripts/preflight.py`, so `core/`, `drafts/macro_output/`, and (later) `wrappers/` can hold multiple independent APIs side by side. Running macro-planning again for a second API (e.g. `core/billing-api/contract.md`) is fully independent of `core/mock-api/`. See `references/directory_conventions.md`.
- [x] Built and tested `scripts/preflight.py` (validates both input files, parses the OpenAPI JSON, derives and sanity-checks the `api-name` slug, refuses to proceed silently if the slug looks generic/wrong) and `scripts/promote.py` (copies the four-or-five promoted files, refuses to run on an incomplete draft set, is idempotent on re-run, never deletes or overwrites `contract.md`). Both verified against the real `core/mock-api/contract.md` + `backend/mock_api/openapi.json` inputs, and (for `promote.py`'s `cases.json` handling) against a synthetic draft set during Phase 4 build-out.

**Note (from the Phase 2 session):** `/implement-wrapper` (Phase 3) was intentionally not built in the Phase 2 session — that pass covered `/macro-planning` only. It has since been built; see the Phase 3 section below. The macro-planning skill still does not chain into `/implement-wrapper` automatically, even after a successful promotion — running the language wrappers remains a separate, manual step per language.

## Phase 3: Micro-Agent / `/implement-wrapper` (run 3×, once per language) — DONE; extended during Phase 4 build-out

- [x] Write `.claude/skills/implement-wrapper/SKILL.md`. Given `core/<api-name>/*` (contract, stage plan, qc_interface + OpenAPI + cases.json, for a specific approved API) and a required `--language` argument (`python` | `go` | `javascript`, exactly one per run — no "all" shortcut), the skill builds, for that language only:
  1. `wrappers/<api-name>/{lang}/lib/` — an idiomatic client library implementing all `contract.md` operations against the backend's real HTTP API (OpenAI-SDK-style: typed methods, per-language-appropriate error handling).
  2. `wrappers/<api-name>/{lang}/server/` — a small server, in the same language, that imports/uses the client library and exposes exactly the routes defined in `core/<api-name>/qc_interface.openapi.json` (and, by extension, the routes `core/<api-name>/cases.json`'s `wrapper` specs expect to call — these must line up). Must honor the fixed process convention (`PORT` env var, `GET /health`).
  3. **Added during Phase 4 build-out:** as this run's final step, start the generated server and invoke `tests/audit.py` against it, reporting pass/fail results (per case, plus a summary) back to the user in chat. The real backend is not started by this skill — the user starts it manually, out-of-band, before running `/implement-wrapper` — see Phase 4 below.
- [x] **New: per-language plan + approval gate** (locked decision, added during this phase's build-out — not in the original Phase 3 sketch, which had micro-agents build directly with no gate). Before writing any code, the skill drafts `wrappers/<api-name>/_plan.<language>.md` — a **no-code** implementation plan: which library/framework choices apply (from the fixed per-language defaults below), the operation → client-method → server-route mapping, how the partial-failure operation is represented in this language, and any open questions. The user must reply with the same explicit approval keyword convention as macro-planning (**"approved"**, case-insensitive) before code generation starts; anything else is treated as feedback and the plan is revised in place. One plan file per language (`_plan.python.md`, `_plan.go.md`, `_plan.javascript.md`) living in the shared `wrappers/<api-name>/` folder, not deleted after code is generated. Rationale: catches a wrong per-language design choice (error-handling shape, partial-failure representation, a missed operation) before any files exist, mirroring the macro-planning approval pattern one level down, at the user's request.
- [x] **Fixed per-language defaults** (locked, encoded in `references/{python,go,javascript}_guide.md` so `/implement-wrapper` doesn't re-decide them per run):
  - **Python:** `requests` for the client, FastAPI + `uvicorn` for the QC server, typed exceptions (e.g. `TaskNotFoundError`) for not-found/invalid-input, a typed result object (not an exception) for partial-failure operations.
  - **Go:** standard library only (`net/http`, `encoding/json`, `net/http.ServeMux` for routing) — zero external dependencies. Explicit `error` returns, `context.Context` as first argument on client methods, a per-item error slice for partial-failure operations.
  - **JavaScript:** standard library only — global `fetch` for the client, built-in `node:http` for the QC server (no Express/Fastify), zero `package.json` dependencies. `async`/`await`, thrown typed `Error` subclasses, an `allSettled`-style result object for partial-failure operations.
  - All three were chosen for minimal/no external dependencies per explicit request, favoring standard-library or single well-known packages over frameworks.
- [x] Built and tested `scripts/preflight.py` (validates the `--language` value and that `core/<api-name>/` has all five required approved files — `contract.md`, `stage_plan.md`, `qc_interface.md`, `qc_interface.openapi.json`, `cases.json` — refusing to proceed the same way `promote.py` refuses an incomplete draft set; warns, without blocking, if `wrappers/<api-name>/<language>/` already has prior output) and `scripts/smoke_test_server.py` (language-agnostic check that a running server honors the `PORT` + `GET /health` convention, with retry/timeout — a lightweight pre-check before the full `tests/audit.py` run, not a replacement for it). Both verified against simulated `core/mock-api/` content and a toy stdlib HTTP server, including the incomplete-`core/` refusal case matching this repo's actual current state (see note below), and (during Phase 4 build-out) the `cases.json`-present-but-empty and `cases.json`-missing refusal cases.
- [x] Confirm each language's server can be started standalone, points at the already-running backend, and manually smoke-test one call per operation before moving to full QC — encoded as workflow step 5 in `SKILL.md`, using `smoke_test_server.py` for the process-convention check plus a manual per-operation pass.
- [x] **Added during Phase 4 build-out:** workflow step 6 in `SKILL.md` — with the language server still running, invoke `tests/audit.py --cases core/<api-name>/cases.json --openapi core/<api-name>/qc_interface.openapi.json --server-base-url http://localhost:<port>` and report the full per-case output back to the user. This folds Phase 4 QC into the automatic tail end of each language's `/implement-wrapper` run.
- [ ] Run Python, then Go, then JS — sequential, manual invocations of the same skill with a different `--language` value each time. `/macro-planning` does **not** trigger this automatically; it is a deliberate, separate step per the Phase 2 decision above. **Not yet run for real in this environment** — see note below.
- [x] `wrappers/<api-name>/` namespacing (decision carried over from Phase 2's multi-API generality work): mirrors `core/<api-name>/`, so building wrappers for a second API doesn't collide with the first.

**Not yet exercised end-to-end in this environment:** `core/mock-api/` currently contains only `contract.md` — `/macro-planning` has not actually been run and approved for mock-api yet in this session, so `stage_plan.md`, `qc_interface.md`, `qc_interface.openapi.json`, and `cases.json` don't exist there. `/implement-wrapper`'s `preflight.py` correctly refuses to proceed against this incomplete `core/mock-api/` (verified). The skill itself is complete and was validated against simulated complete `core/` content plus a toy server; the next real step is running `/macro-planning` for mock-api to completion (now including a real `cases.json` and supplying the real backend's base URL), then `/implement-wrapper --language python` (then `go`, then `javascript`) against the real, approved artifacts — each run now also exercising `tests/audit.py` for real at the end.

## Phase 4: Blind QC — Differential Testing (`tests/audit.py`) — REDESIGNED, `audit.py` DONE

**Design note:** this phase's original sketch (see the redesign note at the top of this document) had `audit.py` itself spawn/reseed the mock backend per test case and derive comparisons live from a hand-written, abstract `tests/cases.json`. That design has been replaced with the one below, at the user's request, to keep `audit.py` static and simple and to move test-case authorship into `/macro-planning`'s existing draft/approval loop.

- [x] **`cases.json` is no longer hand-written under `tests/`.** It's a `/macro-planning` output artifact — drafted into `drafts/macro_output/<api-name>/cases.json`, reviewed in the same approval loop as the other three artifacts, and promoted to `core/<api-name>/cases.json`. See the Phase 2 section above and `references/cases_template.md`. Coverage requirements are unchanged in spirit: roughly 15–20 cases across the 6 operations, 1 happy-path per operation, 1 not-found, 1 invalid-input, 2–3 `bulk_update` partial-failure cases.
- [x] **New shape:** each case is `{case_id, edge_case_label?, direct: {method, endpoint, body?}, wrapper: {method, endpoint, body?}}` — fully resolved (literal endpoints, literal bodies), not `{operation, input, seed}` resolved live. No `expected_output` field, same as before — the real backend's live response during the run is the expected output. `direct` and `wrapper` are two independent specs (not one shared spec reused against both base URLs) so a genuine routing divergence between backend and QC server doesn't silently break the test file itself. The file also carries a top-level `direct_base_url` (the real backend's base URL, supplied by the user during `/macro-planning`).
- [x] Implement `tests/audit.py` as a **static, language-agnostic replay-and-compare loop** — built and smoke-tested against stdlib fake servers during Phase 4 build-out:
  1. Load `core/<api-name>/cases.json` (`--cases`) and `core/<api-name>/qc_interface.openapi.json` (`--openapi`).
  2. For each case: call `direct` against `direct_base_url` (from the file, or `--direct-base-url` override) → response **A**.
  3. Call `wrapper` against `--server-base-url` (required CLI arg, supplied by whichever process — currently `/implement-wrapper` — started that language's server) → response **B**.
  4. Compare status codes, then compare bodies **restricted to fields declared in the matching `qc_interface.openapi.json` response schema** (unchanged design principle — schema-driven allowlist; falls back to full-body comparison if no schema is found for that path/method/status).
  5. Log `pass` or `fail` + a short free-text reason per case (simplified from the original categorized taxonomy — see the locked-decisions note above) and print a summary line at the end. Exit code `0` iff every case passed.
- [x] Confirmed `audit.py` never reads any file under `wrappers/{lang}/` and never spawns, kills, or seeds any process — it only sends HTTP requests to the two base URLs it's given. True black box, and simpler than the original spawn-per-case design.
- [x] **Backend/server lifecycle (revised locked decision):** neither server is started or restarted by `audit.py` itself.
  - The real backend is started **manually by the user**, once, out-of-band, before any `/implement-wrapper` run — not per test case, not per language run. `audit.py` assumes it's already up and reachable at `direct_base_url`.
  - Each language's QC server is started by **`/implement-wrapper`**, as the final step of that language's own run (after code generation and the process-convention smoke test), which then invokes `audit.py` directly and reports results — see the Phase 3 section above.
  - There is therefore no reseeding-per-case behavior at all in the new design; whatever state the manually-started backend is in when a QC run happens is what both `direct` and `wrapper` calls observe. This is a deliberate simplification traded for `audit.py`'s statelessness — `cases.json`'s authors (via `/macro-planning`) are responsible for writing cases that behave sensibly against whatever backend state exists at run time (e.g. self-contained not-found IDs that are guaranteed not to exist regardless of prior state) — see `references/cases_template.md` for detail.

## Phase 5: README & Polish

- [ ] Write README covering: what this is, the two nested contracts (`contract.md` + `qc_interface.md`), why differential testing was chosen over static fixtures (good selling point — lead with it; note it's now static-replay differential testing against manually-started servers, not live-seeded per-case spawning — see Phase 4), how to add a 4th language.
- [ ] `results/` and results-table generation are **deferred** — do not block on this for v1 of the pipeline.
- [ ] Tag `v0.1` once all 3 language wrapper+server pairs pass Phase 4 QC (or have honestly-logged pass/fail with reasons — a clean all-pass table is not required, and `bulk_update` friction is expected and fine to show).

## Open items deferred to later passes (explicitly not blocking right now)

- `results.json` schema + population.
- Any retry-ceiling reporting for a future write-up (moot for now since the reviewer step here is unbounded-until-approved, not loop-count-bounded).

## Definition of Done for this phase

- [x] `core/mock-api/contract.md` hand-written and stable (relocated from `core/contract.md` during Phase 2 for `api-name` namespacing — see Phase 1 note above).
- [x] Mock backend built, seeded-determinism validated by hand.
- [x] Macro-planning skill (`/macro-planning`) produces all 4 required draft artifacts (`stage_plan.md`, `qc_interface.md`, `qc_interface.openapi.json`, `cases.json` — grew from 3 during Phase 4 build-out) + optional `language_notes.md`; approval loop, keyed on an explicit "approved" keyword, reaches promotion; `scripts/promote.py` copies drafts to `core/<api-name>/` verbatim and was verified end-to-end against the real mock-api inputs (contract.md, openapi.json) plus a synthetic draft set for the `cases.json` promotion path.
- [x] Implement-wrapper skill (`/implement-wrapper`) built: per-language, `--language`-gated, drafts a no-code `_plan.<language>.md` and waits for the same "approved" keyword before generating `lib/` + `server/`, then (added during Phase 4 build-out) starts the server and runs `tests/audit.py` against it as its final step; `scripts/preflight.py` and `scripts/smoke_test_server.py` verified against simulated complete `core/` content and a toy server.
- [x] `tests/audit.py` built as a static, language-agnostic replay-and-compare loop (no process-spawning, no seeding) and verified against stdlib fake servers: schema-driven field filtering confirmed to correctly ignore undeclared extras and correctly catch a genuine value mismatch on a declared field; CLI error paths (missing cases file, unreachable server, `--direct-base-url` override) verified.
- [ ] All 3 language `/implement-wrapper` runs complete against real, approved `core/mock-api/` content; each produces a working `lib/` + `server/` and a real `tests/audit.py` run against it. **(Not started for real — blocked on running `/macro-planning` to completion for mock-api first, including a real `cases.json`; see Phase 3 note above.)**
- [ ] `core/mock-api/cases.json` drafted and approved via `/macro-planning`, covering all 6 operations incl. bulk_update partial-failure cases. **(Not yet run for real in this environment.)**
