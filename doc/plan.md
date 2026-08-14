# 02 — GitHub Repo B: Multi-Language API/DB Wrapper Factory (v2 — Detailed Implementation Plan)

**Links:** [[00_Index]] · [[01_GitHub_Repo_A_MathProblems]] · [[03_ArXiv_Paper]] · [[04_Blog_and_Distribution]]

**Status:** Planning → ready to implement
**Supersedes:** `02_GitHub_Repo_B_WrapperFactory.md` (v1). This document is the result of a design brainstorm that substantially refined v1's QC and pipeline mechanics. Where this doc is silent, v1 still applies (naming, README, resources, definition of done).
**Current scope:** Pipeline only — `API docs → macro-agent → human approval loop → 3× micro-agent → 3 working wrapper+server pairs`. Results logging (`results.json`) and paper-table generation are explicitly deferred, matching Repo A's current state.

---

## What changed from v1 (summary)

| Aspect | v1 | v2 |
|---|---|---|
| Backing service | Mock API or SQLite (open choice) | **Mock REST API only**, FastAPI |
| Domain | Unspecified generic CRUD | **Tasks API** (title, done, due_date, + generated fields) |
| Wrapper definition | Ambiguous ("wrapper spins up a server") | Wrapper = **client library**; a separate **QC-facing server** (in the same language) wraps it |
| QC method | Static `cases.json` with baked-in `expected_output` | **Differential testing**: same seeded backend, called directly vs. via wrapper-server, responses compared |
| Macro-agent scope | Per-language Stage Plans (3 runs) | **One run**, language-agnostic, produces Stage Plan + `qc_interface.md` + OpenAPI spec |
| Reviewer step | Bounded reviewer-agent, max 2 rounds, auto-escalate | **Unbounded human-or-AI-judge approval loop** on a draft artifact; no cap, no auto-escalation |
| Micro-agent scope | Per-language, builds wrapper only | Per-language, builds **wrapper + QC-facing server**, reads only from approved `core/` |
| Comparison strictness | Exact match against fixture | **Schema-driven allowlist** (OpenAPI-declared fields only) |
| Failure logging | Pass/fail | **Categorized**: `pass \| value_mismatch \| shape_invalid \| direct_call_error \| wrapper_call_error` (deferred until results logging phase) |
| Harder 6th operation | Unspecified ("compound/transactional") | **`bulk_update` with partial failure** |
| API keys | Not mentioned | Considered, explicitly **dropped** to keep scope tight |

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
  micro-agent (py)       micro-agent (go)        micro-agent (js)
        │                       │                       │
        ▼                       ▼                       ▼
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

- [ ] Confirm repo name (see [[00_Index]]).
- [ ] Create GitHub repo, license, `.gitignore`.
- [ ] Scaffold:
```
{REPO_B_NAME}/
├── core/                          # APPROVED artifacts only — micro-agents read ONLY from here
│   ├── contract.md                # hand-written: Tasks CRUD semantics (fixed, written before any agent runs)
│   ├── stage_plan.md              # macro-agent output, promoted from drafts/ on approval
│   ├── qc_interface.md            # macro-agent output, promoted from drafts/ on approval
│   └── qc_interface.openapi.json  # macro-agent output, promoted from drafts/ on approval
├── drafts/
│   └── macro_output/              # macro-agent writes/revises here; nothing here is trusted
│       ├── stage_plan.md
│       ├── qc_interface.md
│       └── qc_interface.openapi.json
├── backend/
│   └── mock_api/                  # hand-written FastAPI backend (the "provider")
│       ├── main.py                # accepts SEED env var / startup arg, exposes Tasks CRUD
│       └── seed.py                # seeded RNG helpers for priority_score, created_at jitter
├── wrappers/
│   ├── python/
│   │   ├── lib/                   # client library (micro-agent output)
│   │   └── server/                # QC-facing server (micro-agent output)
│   ├── go/
│   │   ├── lib/
│   │   └── server/
│   └── javascript/
│       ├── lib/
│       └── server/
├── tests/
│   ├── cases.json                 # hand-written: {operation, input, seed, edge_case_label?} — NO expected_output
│   └── audit.py                   # blind QC: process orchestration + differential comparison + categorized logging
├── skills/
│   ├── MACRO_SKILL.md
│   └── MICRO_SKILL.md             # (no separate REVIEWER_SKILL.md — see Phase 2 note)
├── results/                       # deferred — not populated in this phase
├── README.md
└── LICENSE
```
- [ ] Confirm runtimes available locally: Python, Go, Node.

## Phase 1: Core Contract (hand-written, before any agent runs)

- [ ] Write `core/contract.md` by hand: the 6 operations above, exact field names/types, error semantics (404 on missing id, 422-equivalent on invalid input). This is the fixed foundation — same principle as both v1 plans: write this yourself, don't delegate it.
- [ ] Build `backend/mock_api/main.py` (FastAPI): implements all 6 operations against in-memory storage. Accepts a `SEED` env var at startup; `priority_score` and `created_at` jitter are derived deterministically from that seed (e.g. `random.Random(seed)` instance scoped to the process). Expose `GET /health`.
- [ ] Confirm the mock backend runs standalone and produces **identical output across two separate process starts with the same `SEED`** — validate this by hand (start, call, kill, restart same seed, call again, diff) before building anything else on top of it. This is the load-bearing assumption for the entire differential-QC design.
- [ ] FastAPI auto-generates OpenAPI for the backend itself — save this as a reference (`backend/mock_api/openapi.json`) for the macro-agent to consume as "the API docs."

## Phase 2: Macro-Agent + Approval Gate

- [ ] Write `skills/MACRO_SKILL.md`. Given `core/contract.md` + `backend/mock_api/openapi.json`, the macro-agent (single run, language-agnostic) produces, into `drafts/macro_output/`:
  1. `stage_plan.md` — per-operation behavior spec, what the seeded/generated fields mean and how they must behave, edge cases (not-found, invalid input, bulk partial-failure semantics). High-level only — no code, no per-language implementation choices.
  2. `qc_interface.md` — human-readable QC-facing HTTP contract: one route per contract operation (1:1 mapping — see rationale below), method, request/response shape. Includes the **fixed process convention**: every language's QC server must bind to a `PORT` env var and expose `GET /health` → 200.
  3. `qc_interface.openapi.json` — machine-readable version of the same routes.
  4. Optional brief per-language guidance notes (a few lines each, not detailed idiom tables) — e.g. "Go: prefer explicit error returns"; "JS: prefer async/await." Steering only, not design.
- [ ] **1:1 endpoint mapping rationale** (locked decision): one QC route per contract operation (`POST /wrapper/create`, `GET /wrapper/get/{id}`, etc.), not a single uniform `/invoke`. Reasons: mirrors real SDK method-per-operation shape; gets REST-semantics coverage (status codes) for free; a uniform endpoint would let broken wrappers hide behind generic 200s; cleaner per-operation pass/fail table for the paper.
- [ ] **Approval loop** (unbounded, no auto-escalation): you review `drafts/macro_output/*` in conversation, give feedback, macro-agent revises in place. Repeat until you say "approved."
- [ ] On approval: a scaffolding/skill step copies `drafts/macro_output/*` → `core/*` verbatim. `core/` is now the only location `MICRO_SKILL.md` is permitted to read from.
- [ ] No `REVIEWER_SKILL.md` for this repo (deliberate deviation from v1 and from Repo A): the approval gate itself — human or AI-judge, interchangeable — *is* the reviewer mechanism, implemented as a draft/promote workflow rather than a separate agent persona with a bounded iteration count. Worth calling out explicitly in the paper as an alternate valid instantiation of architecture element 3 (the dial still exists — human-gated vs. delegated-to-an-AI-judge — it's just implemented as "who approves the promotion," not "how many agent-vs-agent rounds run").

## Phase 3: Micro-Agent (run 3×, once per language)

- [ ] Write `skills/MICRO_SKILL.md`. Given `core/*` (contract, stage plan, qc_interface + OpenAPI) and a `--language` argument, the micro-agent (run manually, once per language, sequentially) builds, for that language only:
  1. `wrappers/{lang}/lib/` — an idiomatic client library implementing all 6 `contract.md` operations against the mock backend's real HTTP API (OpenAI-SDK-style: typed methods, per-language-appropriate error handling).
  2. `wrappers/{lang}/server/` — a small server, in the same language, that imports/uses the client library and exposes exactly the routes defined in `core/qc_interface.openapi.json`. Must honor the fixed process convention (`PORT` env var, `GET /health`).
- [ ] Confirm each language's server can be started standalone, points at the already-running mock backend, and manually smoke-test one call per operation before moving to full QC.
- [ ] Run Python, then Go, then JS — sequential, manual invocations of the same skill with a different `--language` value each time.

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

- `results.json` schema + population (mirrors Repo A, once Repo A's own results logging is also resumed).
- Whether Repo B's numbers land in a separate Table 2 or merged with Repo A's Table 1 in the arXiv paper.
- Any retry-ceiling numbers for the paper's methodology section (moot for now since the reviewer step here is unbounded-until-approved, not loop-count-bounded like Repo A's).

## Definition of Done for this phase

- [ ] `core/contract.md` hand-written and stable.
- [ ] Mock backend built, seeded-determinism validated by hand.
- [ ] Macro-agent produces all 3 required draft artifacts; approval loop reaches "approved"; promotion to `core/` works.
- [ ] All 3 language micro-agent runs complete; each produces a working `lib/` + `server/`.
- [ ] `tests/cases.json` hand-written, covering all 6 operations incl. bulk_update partial-failure cases.
- [ ] `tests/audit.py` runs end-to-end against all 3 languages, produces categorized pass/fail output (console output is sufficient for now — no results.json required yet).
