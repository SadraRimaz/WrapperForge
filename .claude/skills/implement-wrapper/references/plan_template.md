# `_plan.<language>.md` — template and guidance

This is the artifact `/implement-wrapper` drafts and waits for approval
on **before writing any code**. It captures no-code implementation
decisions only — the goal is for the user to be able to catch a wrong
design choice (wrong error-handling shape, wrong partial-failure
representation, missing edge case) before any files are generated, not
after.

## What belongs in the plan

- Which client/server approach this run will use, restated briefly
  from the relevant language guide (`references/<language>_guide.md`)
  — e.g. "Python client: `requests`, typed exceptions for not-found /
  invalid-input, QC server: FastAPI." One or two lines; the guide is
  the source of truth, the plan just confirms which choices apply.
- The **method/route list**: one line per operation from
  `stage_plan.md`, mapping to its method signature (client side) and
  its route (server side, from `qc_interface.openapi.json`). This is
  the part most worth a human glancing at before code exists — it's
  where a missing operation or wrong mapping would show up.
- How the **partial-failure operation** (if `contract.md` has one) will
  be represented in this language — restate the choice from the
  language guide explicitly, since this is the one place per-language
  idiom deliberately diverges and is worth confirming.
- Any **open question or judgment call** the agent had to make because
  `stage_plan.md` / `qc_interface.md` didn't fully specify something —
  flag it here rather than silently deciding and moving on.
- **File layout** this run will produce, as a short tree (paths only,
  no code).

## What does NOT belong in the plan

- No code. Not even short snippets. If describing a decision requires
  showing code to be clear, that's a sign the decision itself needs to
  be stated more plainly in prose instead.
- No re-litigating already-fixed choices from `stage_plan.md` /
  `qc_interface.md` — those are approved and out of scope for this
  plan. This plan is about *how this language will implement* what's
  already been decided, not about re-deciding it.
- No content about other languages. Each language gets its own
  `_plan.<language>.md`; don't reference or restate a sibling
  language's plan here.

## Structure to follow

```markdown
# Implementation Plan: <API Name> — <Language>

Source: core/<api-name>/{contract.md, stage_plan.md, qc_interface.md,
qc_interface.openapi.json}

## Approach

- Client: <library/stdlib choice>, <error-handling shape>
- Server: <framework/stdlib choice>
- Dependencies: <list, or "none beyond stdlib">

## Operations

| Operation (stage_plan.md) | Client method | Server route (qc_interface.openapi.json) |
|---|---|---|
| create | `create(...)` | `POST /tasks` |
| ... | ... | ... |

## Partial-failure representation

<How the bulk/partial-failure operation, if any, is represented in
this language — one paragraph, restating the language guide's choice.>

## Open questions / judgment calls

<Anything stage_plan.md or qc_interface.md left ambiguous that this
plan had to decide — or "None." if there aren't any.>

## File layout

```
wrappers/<api-name>/<language>/
├── ...
```
```

## Where this file lives

`wrappers/<api-name>/_plan.<language>.md` — one per language, in the
shared `wrappers/<api-name>/` folder (not nested under the
language-specific subfolder, since it's written and approved *before*
that subfolder's contents exist). It is not deleted after code is
generated — it stays as a durable record of what was approved and why,
useful if the code needs revisiting later.

## Approval

Same convention as macro-planning: the user's message must contain an
explicit approval keyword ("approved", case-insensitive, or a close
variant like "approve") before code generation starts. Anything else —
including clear enthusiasm without the keyword — is feedback: revise
`_plan.<language>.md` in place and present again. Don't infer approval.
