---
name: implement-wrapper
description: Builds one language's client library + QC-facing server from an approved core/api-name/ folder (contract.md, stage_plan.md, qc_interface.md, qc_interface.openapi.json, cases.json). Drafts a no-code implementation plan for the requested language, waits for human approval, then generates minimal-dependency, idiomatic code, starts the server, and runs tests/audit.py against it. Use when the user runs /implement-wrapper with a --language argument (python, go, or javascript), or asks to build/implement the wrapper or QC server for one of those languages against an already-approved core/ folder. Run once per language, three times total for full coverage. Not for drafting core/ itself — that's /macro-planning, which must be approved and promoted first.
license: See repository LICENSE.
metadata:
  phase: "3"
  produces: "wrappers/api-name/language/lib and wrappers/api-name/language/server; runs tests/audit.py at the end"
  project: "WrapperForge"
---

# Implement Wrapper

Per-language build stage of the WrapperForge pipeline (`doc/plan.md`,
Phase 3). Run manually, once per language, three times total
(`python`, `go`, `javascript`) — never automatically, and never
triggered by `/macro-planning`. Reads only from an already-approved
`core/<api-name>/`; never touches `drafts/`.

Three stages, with a hard stop after the first: draft a **no-code**
implementation plan for the requested language, wait for explicit
approval, generate the client library and QC-facing server, then start
the server and run `tests/audit.py` against it as this run's final
step.

## When this skill does NOT apply

- Drafting or revising `core/<api-name>/` content (`contract.md`,
  `stage_plan.md`, `qc_interface.md`, `qc_interface.openapi.json`,
  `cases.json`) — that's `/macro-planning`. This skill only reads that
  content, never writes it.
- Building more than one language in a single invocation. The user
  supplies exactly one `--language` value per run; if they ask for
  "all three" or don't specify one, ask which language this run is for
  rather than looping over all three yourself.
- Starting or seeding the real backend itself (e.g. the mock API) —
  that's started manually by the user, out-of-band, before this skill
  runs. This skill starts and stops only the language-specific server
  it just generated.

## Inputs required

Every run needs:

1. An **`api-name`** (e.g. `mock-api`) — whichever API's `core/<api-name>/`
   the user wants a wrapper for. Ask if it isn't clear from context.
2. A **`--language`** value: exactly one of `python`, `go`,
   `javascript`. Ask if it isn't given — don't default to one.

## Workflow

### 1. Preflight

Run the bundled preflight script:

```bash
python3 .claude/skills/implement-wrapper/scripts/preflight.py <api-name> <language> --repo-root <repo_root>
```

This checks that `<language>` is valid and that `core/<api-name>/`
contains all five required approved artifacts (`contract.md`,
`stage_plan.md`, `qc_interface.md`, `qc_interface.openapi.json`,
`cases.json`) — mirroring how `promote.py` refuses an incomplete draft
set, one level down. It also validates `qc_interface.openapi.json` and
`cases.json` each parse as JSON, and warns (without blocking) if
`wrappers/<api-name>/<language>/` already has files in it from a prior
run.

- If `ok` is `false`, stop and surface the errors. A missing
  `core/<api-name>/` or an incomplete one means `/macro-planning`
  hasn't been approved and promoted for this API yet — say so plainly,
  and don't try to work around it by reading from `drafts/` instead.
- If there's a warning about existing wrapper files, mention it to the
  user before proceeding (re-running is fine, e.g. after a plan
  revision, but they should know prior output may be overwritten).
- Read all five `core/<api-name>/` files in full before drafting the
  plan. Load `references/<language>_guide.md` for the requested
  language too — its choices (HTTP client, error-handling shape, server
  framework) are what the plan will restate and the code will follow.
  `cases.json` in particular tells you the exact endpoints/methods the
  generated server must expose — the routes the server ends up with
  must line up with what `cases.json`'s `wrapper` specs expect to call,
  or the final QC step will fail on routing alone, before any real
  comparison happens.

### 2. Draft the implementation plan

Write `wrappers/<api-name>/_plan.<language>.md` (create
`wrappers/<api-name>/` if needed). Follow
`references/plan_template.md` closely:

- **No code.** This plan captures implementation *decisions* — which
  library, how errors are represented, how the partial-failure
  operation (if `contract.md` has one) is represented in this
  language, the method-to-route mapping, the file layout — not any
  actual source. If a decision seems to need a code snippet to explain
  clearly, restate it in plainer prose instead.
- Pull the language-specific choices from `references/<language>_guide.md`
  (Python → `requests` + FastAPI; Go → stdlib `net/http` only, explicit
  `error` returns, per-item error slice for partial failure; JavaScript
  → global `fetch` + stdlib `node:http`, thrown typed errors,
  `allSettled`-style result object for partial failure). Restate them
  briefly in the plan rather than re-deciding them — they're fixed
  defaults for this project, not open questions per run.
- List every operation from `stage_plan.md`, in the same order, mapped
  to its client method name and server route (from
  `qc_interface.openapi.json`). This is the part most worth a human
  glancing at before any code exists.
- If `stage_plan.md` or `qc_interface.md` left something ambiguous that
  this plan had to resolve, say so explicitly under "Open questions" —
  don't silently decide and move on.

This file replaces any prior `_plan.<language>.md` for the same
language (each language gets its own plan file; don't touch a sibling
language's plan).

### 3. Present the plan for approval

Summarize the plan in chat (don't just dump the raw file unless asked)
and ask the user to review
`wrappers/<api-name>/_plan.<language>.md`. This gate is **required** —
never generate code before it clears.

- If the user gives feedback (anything without an explicit approval
  keyword), revise `_plan.<language>.md` in place and present again.
  Do not write any `lib/`/`server/` code yet.
- If the user's message contains an explicit approval keyword —
  **"approved"** (case-insensitive; also accept close variants like
  "approve" or "approved, go ahead") — same convention as
  `/macro-planning` — proceed to code generation. Anything else,
  including clear enthusiasm without the keyword, is still
  feedback-mode: ask directly, don't infer it.

### 4. Generate the code

Only after approval. Write into
`wrappers/<api-name>/<language>/{lib,server}/` following the approved
plan and the relevant `references/<language>_guide.md` for concrete
conventions (layout, dependency list, idioms):

- `lib/` — the client library: typed methods, one per `stage_plan.md`
  operation, calling the real backend's HTTP API.
- `server/` — the QC-facing server: one route per
  `qc_interface.openapi.json` entry, calling into `lib/` and
  translating its results/errors into the HTTP responses
  `qc_interface.md` specifies. Must bind to the `PORT` env var and
  expose `GET /health` → 200 (the fixed process convention every
  language's server must honor — this is non-negotiable, not a
  per-language choice).

Keep dependencies to what each language guide specifies (`requests` +
`fastapi` + `uvicorn` for Python; standard library only for Go;
standard library only, `"dependencies": {}`, for JavaScript) unless the
approved plan explicitly called out a genuine gap.

**Python only — dedicated venv, created here, not reused from the
backend:**

```bash
cd wrappers/<api-name>/python
uv venv --python 3.12
# write requirements.txt (requests, fastapi, uvicorn)
uv pip install -r requirements.txt --python .venv
```

Never install into or run this server from `backend/mock_api/`'s
`.venv` — the two are separate projects. See
`references/python_guide.md`'s "Environment & dependencies" section for
the full rationale.

### 5. Smoke-test the process convention

Start the generated server locally (start command depends on the
language — for Python, `.venv/bin/uvicorn server.main:app --port
"$PORT"` from the dedicated venv created in step 4, never the backend's
`.venv`; `go run` for Go; `node` for JavaScript) with `PORT` set, then
confirm it answers `/health`:

```bash
python3 .claude/skills/implement-wrapper/scripts/smoke_test_server.py <port>
```

This is a lightweight pre-check — it only confirms the `PORT` +
`GET /health` convention before spending a full QC run against a
server that might not even be up. It is not a substitute for step 6.
If this fails, stop and fix the server; don't proceed to a QC run
against a server that can't pass its own health check.

### 6. Run QC (`tests/audit.py`) against the running server

The real backend (e.g. the mock API) is **not** started by this
skill — the user starts and seeds it manually, out-of-band, before
running `/implement-wrapper` (see `doc/plan.md` Phase 1). Confirm with
the user that it's up and reachable at the `direct_base_url` recorded
in `core/<api-name>/cases.json` before this step; if you can't confirm
independently, ask.

With the language server from step 5 still running, invoke the static
QC runner:

```bash
python3 tests/audit.py \
  --cases core/<api-name>/cases.json \
  --openapi core/<api-name>/qc_interface.openapi.json \
  --server-base-url http://localhost:<port>
```

`audit.py` is a pure black-box replay-and-compare loop: it never reads
anything under `wrappers/<lang>/`, only speaks HTTP against the two
base URLs. It loads the pre-approved `cases.json` as-is, calls the
`direct` spec against the real backend and the `wrapper` spec against
the server just started, compares responses restricted to the fields
`qc_interface.openapi.json` declares for that response, and prints a
`pass`/`fail` + reason per case plus a summary line. Exit code `0`
means every case passed; non-zero means at least one failed.

Report the full output to the user verbatim (case-by-case pass/fail,
plus the summary line) — don't just say "QC passed" or "QC failed"
without showing which cases and why. A clean all-pass run is not
required to consider this language's `/implement-wrapper` run
complete; honestly-reported, categorized failures are an acceptable
outcome per `doc/plan.md`'s Phase 4/5 notes (e.g. `bulk_update`
friction is expected and fine to surface). Stop the server once QC has
finished running.

## Notes

- Nothing in this skill chains into the next language automatically.
  Running Python, then Go, then JavaScript are three separate,
  user-triggered invocations, as `doc/plan.md` describes.
- This skill's own run now ends with a `tests/audit.py` invocation
  (step 6) — Phase 4 QC for a given language happens automatically as
  part of that language's `/implement-wrapper` run, not as a separate
  later invocation. `tests/audit.py` itself remains reusable standalone
  (e.g. to re-run QC later without rebuilding anything) — this skill
  just also calls it once, at the end.
- See `references/plan_template.md`, `references/python_guide.md`,
  `references/go_guide.md`, and `references/javascript_guide.md` for
  the detailed guidance this workflow points to at each step.
