# `qc_interface.openapi.json` — guidance

This is the machine-readable twin of `qc_interface.md`. It must describe
**exactly the same routes**, in the same order, with no additions or
omissions — `qc_interface.md` and `qc_interface.openapi.json` should never
drift apart. If you change one while drafting, update the other in the
same pass.

## Minimum required shape

A valid OpenAPI 3.x document:

```json
{
  "openapi": "3.0.3",
  "info": {
    "title": "<API Name> — QC Interface",
    "version": "1.0.0",
    "description": "Machine-readable QC-facing HTTP contract. One route per contract.md operation. Every language's QC server (wrappers/<lang>/server/) must implement exactly these routes, plus GET /health."
  },
  "paths": {
    "/health": {
      "get": {
        "summary": "Health check",
        "responses": {
          "200": { "description": "Server is ready to serve." }
        }
      }
    }
    // ... one entry per contract.md operation, matching qc_interface.md
  }
}
```

## Rules

1. **1:1 with `contract.md` operations**, same as `qc_interface.md` — no
   `/invoke`-style catch-all.
2. **Always include `GET /health`** returning `200` — it's part of the
   fixed process convention, not optional per-API.
3. **Response schemas are the QC allowlist.** Only fields declared in a
   response's schema here are compared during differential testing
   (schema-driven allowlist — see `plan.md`'s locked design decisions).
   This means: be deliberate about what you include. Include every field
   that matters for correctness (e.g. all resource fields on a
   success response). Do not include incidental fields you don't want
   compared (if the backend happens to emit an internal field,
   leave it out of the schema and it's automatically ignored by QC).
4. **Reuse a `components.schemas` entry for the resource type** if the
   same shape appears in multiple responses (e.g. a `Task`-like object
   returned by both a "get" and a "list" operation) — reference it with
   `$ref` rather than repeating the schema inline. Keeps the file
   consistent and easier to keep in sync with `qc_interface.md`.
5. **Error responses need schemas too** (e.g. a `404` body shape), since
   error-path QC still needs something to validate against. Don't skip
   error responses just because the happy path is more detailed.
6. **Status codes must match `qc_interface.md` exactly.** These two
   files describe the same contract in two formats — a mismatch between
   them is a defect in the draft, not a stylistic choice, and should be
   caught before presenting drafts for approval.

## Partial-failure / batch operations

If `contract.md` has an operation with partial-failure semantics (e.g. a
bulk operation), its OpenAPI response schema should model the
succeeded/failed split explicitly (e.g. `succeeded: []`, `failed: []`
arrays) rather than collapsing it into a single ambiguous shape — this
is the field-level detail `audit.py` needs to validate against later.

## Validating the draft

After generating the file, parse it back with a JSON parser to confirm
it's syntactically valid before presenting it for approval — a
hand-authored/LLM-authored OpenAPI JSON file with a trailing comma or
mismatched brace is a common, easily-avoidable failure mode. If Python
is available in the environment, a quick check is:

```bash
python3 -c "import json; json.load(open('drafts/macro_output/<api-name>/qc_interface.openapi.json'))"
```

No output means it parsed successfully.
