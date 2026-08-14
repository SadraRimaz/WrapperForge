# `qc_interface.md` — template and guidance

`qc_interface.md` is the **human-readable QC-facing HTTP contract**: the
routes every language's QC server must expose so `tests/audit.py` (or
whatever the blind differential-QC harness is called in this repo) can
call each operation the same way regardless of language.

## Locked design rule: 1:1 endpoint mapping

One QC route per operation in `contract.md` / `stage_plan.md`. Not a
single uniform `/invoke` endpoint. Always state the rationale briefly at
the top of the file (mirrors real SDK method-per-operation shape; gets
REST-semantics coverage, i.e. status codes, for free; a uniform endpoint
lets broken wrappers hide behind generic 200s; produces a clean
per-operation pass/fail table). Keep this rationale even when adapting
the skill to a new API — it's a locked project-level decision, not
something to re-derive per API.

## Fixed process convention (always include verbatim)

Every QC server, in every language, must:
- Bind to a `PORT` environment variable (no hardcoded port).
- Expose `GET /health` → `200` once ready to serve.

State this explicitly in the file — it's load-bearing for
`tests/audit.py`'s process orchestration.

## Structure to follow

```markdown
# QC Interface: <API Name>

Human-readable HTTP contract that every language's QC-facing server
(`wrappers/<lang>/server/`) must implement. One route per
`stage_plan.md` operation (1:1 mapping) — not a uniform `/invoke`
endpoint — so broken wrappers can't hide behind generic 200s and QC
gets a clean per-operation pass/fail table.

## Process convention

- Every QC server binds to a `PORT` env var.
- Every QC server exposes `GET /health` → `200` once ready.

## Routes

### `<METHOD> <path>` — `<operation_name>`

- **Maps to:** stage_plan.md § `<operation_name>`
- **Request:**
  - Path/query params, if any.
  - Body shape (field names + types only — full JSON Schema lives in
    qc_interface.openapi.json).
- **Success response:** status code + body shape.
- **Error responses:** status code(s) + body shape, one row per case
  (not-found, invalid-input, etc.), matching the edge cases listed in
  stage_plan.md for this operation.

(Repeat per operation, in the same order as stage_plan.md.)

## Notes

Anything QC-relevant that doesn't fit per-route (e.g. how partial
failure in a batch operation is represented at the HTTP layer — status
code choice, body shape — since stage_plan.md deliberately leaves the
*language-level* representation open, but the *HTTP-level* shape must
still be fixed here so `audit.py` can compare responses).
```

## Field/schema comparison note

Add a short note reminding future readers (and `audit.py`'s author)
that comparison during QC is schema-driven: only fields declared in
`qc_interface.openapi.json` for a given response are compared between
the direct-backend call and the wrapper-server call. Anything not in
the schema (headers, request IDs, etc.) is ignored. This belongs in
`qc_interface.md` as a one-line pointer; the actual schema lives in
`qc_interface.openapi.json`.

## What NOT to put here

- Per-language implementation choices (that's the optional guidance
  notes, or left to the micro-agent).
- Anything about `wrappers/<lang>/lib/` internals — this file describes
  only the QC-facing server's HTTP surface, not the client library
  underneath it.
