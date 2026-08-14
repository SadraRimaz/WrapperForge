---
name: macro-planning
description: Turns a hand-written API contract (contract.md) plus that API's OpenAPI spec into a language-agnostic implementation plan for building client wrapper libraries — a per-operation stage_plan.md, a QC-facing HTTP interface (qc_interface.md + qc_interface.openapi.json), and optional brief per-language steering notes. Runs a human-approval revision loop before promoting drafts into core/. Use when the user runs /macro-planning, references a contract file (e.g. core/mock-api/contract.md) together with an OpenAPI spec (e.g. backend/mock_api/openapi.json), or asks to plan/draft the macro-agent stage for a new API wrapper. Not for implementing the wrappers themselves (see /implement-wrapper) and not for writing contract.md, which is always hand-authored ahead of time.
license: See repository LICENSE.
metadata:
  phase: "2"
  produces: "stage_plan.md, qc_interface.md, qc_interface.openapi.json"
  project: "WrapperForge"
---

# Macro-Planning

Single-run, language-agnostic planning stage of the WrapperForge pipeline
(`doc/plan.md`, Phase 2). Consumes a hand-written `contract.md` and an
API's OpenAPI spec, drafts three planning artifacts, runs an unbounded
human-approval revision loop on the drafts, and — only on explicit
approval — promotes them into `core/<api-name>/` where the (separate,
out-of-scope-here) `/implement-wrapper` skill is permitted to read from.

This skill is general across APIs: it works for whatever API the user
points it at (the bundled mock Tasks API today, a different API
tomorrow), not just one fixed use case. See
`references/directory_conventions.md` for how multiple APIs coexist in
one repo.

## When this skill does NOT apply

- Writing or editing `contract.md` — that file is always hand-authored
  by the user, before this skill ever runs. If it doesn't exist yet,
  stop and tell the user to write it first; do not draft one yourself.
- Building the actual language wrappers/servers — that's
  `/implement-wrapper` (Phase 3), a separate skill, run manually and
  only after promotion. Do not chain into it automatically.
- Any repo-wide file search. Only act on files the user explicitly
  references (e.g. `@core/mock-api/contract.md`,
  `@backend/mock_api/openapi.json`). If the user invokes
  `/macro-planning` without both a contract file and an OpenAPI file
  referenced, ask for the missing one — don't go looking for it.

## Inputs required

Exactly two file references from the user, every run:

1. A **contract file** (conventionally `contract.md`) — hand-written,
   fixed, authoritative for operation semantics.
2. An **OpenAPI spec** (conventionally `openapi.json`) for the same API
   — secondary source, used for HTTP-shape detail (status codes,
   response schemas actually exposed by the backend) and to flag
   operations it exposes that the contract doesn't mention.

If either is missing, ask for it rather than guessing a path.

## Workflow

### 1. Preflight

Run the bundled preflight script against the two referenced files:

```bash
python3 .claude/skills/macro-planning/scripts/preflight.py <contract_path> <openapi_path>
```

This returns a small JSON report: whether both files are readable,
whether the OpenAPI file is valid JSON and looks like an OpenAPI/Swagger
document, an operation count, and a **derived `api_name` slug** taken
from the contract file's parent directory name (see
`references/directory_conventions.md`).

- If `ok` is `false`, stop and surface the errors to the user — don't
  proceed to drafting with a broken input.
- If there are `warnings` (e.g. the derived `api_name` looks generic or
  the OpenAPI file has no `paths`), surface them and confirm the
  intended `api_name` with the user before continuing. Getting this
  wrong means drafting into the wrong folder.
- Read `contract.md` and the OpenAPI spec in full before drafting.

### 2. Draft the three artifacts

Write all three into `drafts/macro_output/<api-name>/` (create the
directory if needed):

1. **`stage_plan.md`** — per-operation behavior spec. Follow
   `references/stage_plan_template.md` closely: one section per
   `contract.md` operation, in the same order, high-level only (no
   code, no per-language choices). Explicitly calls out any
   partial-failure / batch operations as the deliberate point where
   per-language representation will diverge later, without deciding
   that representation here.

2. **`qc_interface.md`** — human-readable QC-facing HTTP contract.
   Follow `references/qc_interface_template.md`: **1:1 route-per-operation
   mapping** (never a uniform `/invoke` endpoint — this is a locked
   design decision, state the rationale in the file), plus the fixed
   process convention every language's QC server must honor
   (`PORT` env var, `GET /health` → 200).

3. **`qc_interface.openapi.json`** — machine-readable twin of
   `qc_interface.md`. Follow
   `references/qc_interface_openapi_guidance.md`: same routes, same
   order, same status codes as `qc_interface.md` — the two must never
   drift apart. Response schemas double as the QC comparison allowlist,
   so be deliberate about which fields are declared. Validate the JSON
   parses before moving on (see the guidance file for a one-line check).

Optionally, also write **`language_notes.md`**: a few lines per target
language (Python / Go / JavaScript, or whatever languages this repo
targets), steering only — e.g. "Go: prefer explicit error returns",
"JS: prefer async/await". Not detailed idiom tables, not design
decisions; those belong to `/implement-wrapper` later.

While drafting, cross-check the OpenAPI spec against `contract.md`:
if the OpenAPI spec exposes an operation `contract.md` doesn't mention,
note it as an open question at the top of `stage_plan.md` rather than
silently planning around it or silently dropping it. Don't attempt
deeper schema-level validation between the two — `contract.md` is the
source of truth for behavior; the OpenAPI spec is secondary.

### 3. Present drafts for approval

Summarize what was drafted (don't just dump raw file contents unless
asked) and ask the user to review
`drafts/macro_output/<api-name>/*`. Make clear this is an **unbounded**
loop: no cap, no auto-escalation.

- If the user gives feedback (anything other than an explicit approval
  keyword — see below), revise the relevant draft file(s) in place
  under `drafts/macro_output/<api-name>/` and present again. Do not
  promote.
- If the user's message contains an explicit approval keyword —
  **"approved"** (case-insensitive; also accept close variants like
  "approve" or "approved, go ahead") — treat that as authorization to
  promote. Anything else, including enthusiasm ("looks great!") without
  the keyword, is still feedback-mode: ask directly whether they
  approve, don't infer it.

### 4. Promote on approval

Run the bundled promotion script:

```bash
python3 .claude/skills/macro-planning/scripts/promote.py <api-name> --repo-root <repo_root>
```

This copies `stage_plan.md`, `qc_interface.md`,
`qc_interface.openapi.json` (and `language_notes.md` if present) from
`drafts/macro_output/<api-name>/` to `core/<api-name>/`, refusing to run
if the draft set is incomplete, and never touches `contract.md`. Report
the script's output to the user (it prints exactly what was copied) and
confirm `core/<api-name>/` is now the approved source for
`/implement-wrapper`.

If re-approving after a later revision, just re-run the promotion
script — it overwrites the three promoted files without deleting
anything else already in `core/<api-name>/`.

## Notes

- This skill never runs `/implement-wrapper` itself, even after a
  successful promotion. That's a separate, manual invocation the user
  triggers per language.
- See `references/directory_conventions.md` for the full picture of how
  `api-name` namespacing keeps multiple APIs independent in one repo.
