# Directory & naming conventions

WrapperForge is designed to plan and build wrappers for **more than one
API over time** (not just the bundled mock Tasks API). Every artifact
this skill touches is namespaced by an `api-name` slug so that running
macro-planning for a second API never overwrites or collides with the
first.

## The `api-name` slug

- Derived from the **parent directory name of the `contract.md` file**
  the user references, lowercased and hyphenated
  (e.g. `core/mock-api/contract.md` → `mock-api`).
- `contract.md` must therefore already live at
  `core/<api-name>/contract.md` — that's the hand-written, fixed
  foundation (per `plan.md`, Phase 1) that has to exist *before*
  macro-planning runs. This skill never writes or edits `contract.md`.
- If the derived slug is generic/wrong (e.g. `core`, empty, or just
  looks off), don't silently accept it — confirm the intended api-name
  with the user before creating any files. Getting this wrong means
  drafting into the wrong folder.
- Use `scripts/preflight.py` to derive and sanity-check the slug (see
  SKILL.md workflow) rather than guessing by hand.

## Fixed paths, parameterized by `api-name`

```
core/<api-name>/
├── contract.md                    # hand-written, pre-existing, never touched by this skill
├── stage_plan.md                  # promoted from drafts/ on approval
├── qc_interface.md                # promoted from drafts/ on approval
└── qc_interface.openapi.json      # promoted from drafts/ on approval

drafts/macro_output/<api-name>/
├── stage_plan.md                  # macro-planning writes/revises here
├── qc_interface.md                # macro-planning writes/revises here
├── qc_interface.openapi.json      # macro-planning writes/revises here
└── language_notes.md              # optional, brief per-language steering notes
```

`wrappers/<api-name>/<language>/{lib,server}/` follows the same
namespacing convention in Phase 3 (`/implement-wrapper`), though that
skill is out of scope here — mentioned only so the convention is
consistent end to end.

## Why namespace `core/` and `drafts/` but never touch `contract.md`

- `contract.md` is authored by hand, once, before any agent runs. It's
  the fixed foundation every other artifact is derived from or checked
  against. This skill only *reads* it.
- `stage_plan.md`, `qc_interface.md`, and `qc_interface.openapi.json`
  are the three artifacts this skill is responsible for producing,
  revising, and (on approval) promoting.
- Nothing here is deleted on a re-run. Promoting again after a revision
  overwrites the three promoted files but leaves `contract.md` and
  anything else already in `core/<api-name>/` alone (see
  `scripts/promote.py`).

## Multiple APIs in one repo

Running macro-planning for a second API (say, `core/billing-api/contract.md`)
produces `drafts/macro_output/billing-api/` and, on approval,
`core/billing-api/`, fully independent of any earlier `core/mock-api/`
run. Nothing about this skill's design assumes a single API per repo.
