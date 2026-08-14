# `cases.json` — template and guidance

`cases.json` is the **fully-resolved, static test-case list** that
`tests/audit.py` replays. It is a macro-planning output artifact — drafted
into `drafts/macro_output/<api-name>/cases.json`, reviewed in the same
approval loop as `stage_plan.md` / `qc_interface.md` /
`qc_interface.openapi.json`, and promoted verbatim to
`core/<api-name>/cases.json` on approval. It is **not** hand-written
directly by the user and **not** generated or modified by
`/implement-wrapper` — by the time a language's wrapper/server exist,
`cases.json` is already locked.

## Why this file exists (design context)

Earlier revisions of this project had `tests/audit.py` itself decide what
to call and derive expected values live, spawning and reseeding the mock
backend per test case. That coupled test *authoring* (edge-case judgment)
to test *execution* (process orchestration) inside one script. This
project now separates them: macro-planning is where edge-case judgment
belongs (it already has full visibility into `contract.md` and
`stage_plan.md`), and `audit.py` is a static, language-agnostic
replay-and-compare loop with no process-spawning or seeding logic at all.
Both real backend and QC server are started **manually / by
`/implement-wrapper`**, outside `audit.py`'s responsibility — see
`plan.md` Phase 4.

## Required input: the direct-backend base URL

Before drafting `cases.json`, ask the user for the base URL the real
backend will be reachable at during QC runs (e.g. `http://localhost:8000`
for the bundled mock API). This is a required input to this skill, same
tier as the contract file and OpenAPI spec — don't guess it or default it
silently. Store it as the top-level `direct_base_url` field (see shape
below) so `audit.py` doesn't need it passed on every invocation.

## File shape

```json
{
  "direct_base_url": "http://localhost:8000",
  "cases": [
    {
      "case_id": "create_happy_path",
      "edge_case_label": null,
      "direct": {
        "method": "POST",
        "endpoint": "/tasks",
        "body": { "title": "Buy milk", "due_date": "2026-09-01" }
      },
      "wrapper": {
        "method": "POST",
        "endpoint": "/wrapper/create",
        "body": { "title": "Buy milk", "due_date": "2026-09-01" }
      }
    }
  ]
}
```

- **`case_id`** — short, unique, descriptive (`get_not_found`,
  `bulk_update_partial_failure_1`), not a bare number.
- **`edge_case_label`** — optional; a short tag (`"not_found"`,
  `"invalid_input"`, `"partial_failure"`) for cases that aren't the
  happy path. Omit or `null` for happy-path cases.
- **`direct`** / **`wrapper`** — each a full, independent
  `{method, endpoint, body?}` call spec. They are **not** assumed to
  share a path — write them out separately even though, given the
  locked 1:1 endpoint-mapping rule in `qc_interface.md`, they'll often
  differ only in path prefix (`/tasks/{id}` vs `/wrapper/get/{id}`).
  Keeping them separate means a genuine divergence in a language
  server's routing doesn't silently break the test file itself.
  - `method` — HTTP method, upper- or lower-case (audit.py
    upper-cases it).
  - `endpoint` — path only, no host/port (e.g. `/tasks/abc`, not
    `http://localhost:8000/tasks/abc`). Include path params inlined
    (literal IDs, not `{id}` placeholders) and query strings if needed
    (e.g. `/tasks?done=true`).
  - `body` — optional; omit entirely for bodyless requests (`GET`,
    `DELETE`). JSON object, sent as the request body.

## Coverage requirements (keep this file small and deliberate)

Roughly **15–20 cases across the 6 contract operations** — small enough
that every case is a deliberate choice, not exhaustive fuzzing. At
minimum:

- **1 happy-path case per operation** (create, get, list, update,
  delete, bulk_update) — 6 cases.
- **1 not-found case** (`get`, `update`, `delete`, or a `bulk_update`
  item, whichever fits the API) — `edge_case_label: "not_found"`.
- **1 invalid-input case** (malformed body, missing required field) —
  `edge_case_label: "invalid_input"`.
- **2–3 `bulk_update` cases specifically constructed so at least one
  item in the batch fails** (bad id or invalid field on one item,
  valid on the others) — `edge_case_label: "partial_failure"`. This is
  the deliberate friction point called out in `contract.md` /
  `plan.md`; don't skip it or reduce it to a single case.

Fill remaining slots with whatever else meaningfully exercises the
domain (list filtering by `done`, update touching only one field,
etc.) — but don't pad the file just to hit a round number.

## What determines a literal ID for `get`/`update`/`delete`/not-found cases?

Since there's no live seeding step before `audit.py` runs, IDs used in
non-happy-path cases (a specific task ID to fetch, update, or delete)
must either:

- Reference an ID that a **prior case in the same list creates**
  (cases run in file order — a `create_happy_path` case near the top
  can produce an ID a later case reuses, if you're encoding IDs by
  position/response-chaining is in scope), **or**
- Use an ID that's obviously synthetic and guaranteed not to exist for
  not-found cases (e.g. `"does-not-exist-000"`), which is sufficient
  for `edge_case_label: "not_found"` cases since both direct and
  wrapper sides are expected to 404 regardless of prior state.

Since `audit.py` has no response-chaining logic (it does not thread a
created ID from one case's response into a later case's request), keep
non-happy-path ID references **self-contained** — don't design a case
that depends on another case's live response. If get/update/delete
happy-path coverage needs a real existing ID, note in
`language_notes.md` or a comment-equivalent that the target backend
must be seeded with at least one known task before a QC run (matching
how the bundled mock API's `seed.py`/manual startup is expected to
work) — or write those happy-path cases against a `list` response
instead of a hardcoded ID, if that fits the API better.

## Field/schema comparison note (unchanged from `qc_interface.md`)

`audit.py` restricts comparison to fields declared in
`qc_interface.openapi.json` for the matching response — this file only
needs to supply *inputs*, not expected outputs. Don't add an
`expected_output` field; it's intentionally absent (the whole point of
differential testing is that the real backend's response *is* the
expected output).

## Validating the draft

After generating the file, parse it back to confirm it's valid JSON
and that every case has both `direct` and `wrapper` specs before
presenting it for approval:

```bash
python3 -c "import json; d = json.load(open('drafts/macro_output/<api-name>/cases.json')); assert 'cases' in d and d['cases']; [c['direct'] and c['wrapper'] for c in d['cases']]"
```

No output/error means it parsed and every case has both specs.
