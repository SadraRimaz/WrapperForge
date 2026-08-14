---
name: implement-wrapper
description: Builds one language's client library + QC-facing server from an approved core/api-name/ folder (contract.md, stage_plan.md, qc_interface.md, qc_interface.openapi.json). Drafts a no-code implementation plan for the requested language, waits for human approval, then generates minimal-dependency, idiomatic code. Use when the user runs /implement-wrapper with a --language argument (python, go, or javascript), or asks to build/implement the wrapper or QC server for one of those languages against an already-approved core/ folder. Run once per language, three times total for full coverage. Not for drafting core/ itself — that's /macro-planning, which must be approved and promoted first.
license: See repository LICENSE.
metadata:
  phase: "3"
  produces: "wrappers/api-name/language/lib and wrappers/api-name/language/server"
  project: "WrapperForge"
---

# Implement Wrapper

Per-language build stage of the WrapperForge pipeline (`doc/plan.md`,
Phase 3). Run manually, once per language, three times total
(`python`, `go`, `javascript`) — never automatically, and never
triggered by `/macro-planning`. Reads only from an already-approved
`core/<api-name>/`; never touches `drafts/`.

Two steps, with a hard stop between them: draft a **no-code**
implementation plan for the requested language, wait for explicit
approval, then generate the client library and QC-facing server.

## When this skill does NOT apply

- Drafting or revising `core/<api-name>/` content (`contract.md`,
  `stage_plan.md`, `qc_interface.md`, `qc_interface.openapi.json`) —
  that's `/macro-planning`. This skill only reads that content, never
  writes it.
- Building more than one language in a single invocation. The user
  supplies exactly one `--language` value per run; if they ask for
  "all three" or don't specify one, ask which language this run is for
  rather than looping over all three yourself.
- Running QC / differential testing (`tests/audit.py`) — that's Phase
  4, a separate concern. This skill's job ends once the code exists and
  has been smoke-tested to start and answer `GET /health`.

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
contains all four required approved artifacts (`contract.md`,
`stage_plan.md`, `qc_interface.md`, `qc_interface.openapi.json`) —
mirroring how `promote.py` refuses an incomplete draft set, one level
down. It also validates `qc_interface.openapi.json` parses as JSON, and
warns (without blocking) if `wrappers/<api-name>/<language>/` already
has files in it from a prior run.

- If `ok` is `false`, stop and surface the errors. A missing
  `core/<api-name>/` or an incomplete one means `/macro-planning`
  hasn't been approved and promoted for this API yet — say so plainly,
  and don't try to work around it by reading from `drafts/` instead.
- If there's a warning about existing wrapper files, mention it to the
  user before proceeding (re-running is fine, e.g. after a plan
  revision, but they should know prior output may be overwritten).
- Read all four `core/<api-name>/` files in full before drafting the
  plan. Load `references/<language>_guide.md` for the requested
  language too — its choices (HTTP client, error-handling shape, server
  framework) are what the plan will restate and the code will follow.

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

### 5. Smoke-test the process convention

Start the generated server locally (start command depends on the
language — `uvicorn` for Python, `go run` for Go, `node` for
JavaScript) with `PORT` set, then confirm it answers `/health`:

```bash
python3 .claude/skills/implement-wrapper/scripts/smoke_test_server.py <port>
```

This only checks the `PORT` + `GET /health` convention — it's not full
QC (that's `tests/audit.py`, Phase 4, out of scope here). Report the
result and, if time allows, manually try one call per operation against
the running server before considering this run complete, per
`doc/plan.md`'s Phase 3 checklist.

## Notes

- Nothing in this skill chains into the next language automatically.
  Running Python, then Go, then JavaScript are three separate,
  user-triggered invocations, as `doc/plan.md` describes.
- Nothing in this skill chains into Phase 4 (`tests/audit.py`) either.
- See `references/plan_template.md`, `references/python_guide.md`,
  `references/go_guide.md`, and `references/javascript_guide.md` for
  the detailed guidance this workflow points to at each step.
