# `stage_plan.md` — template and guidance

`stage_plan.md` is a **per-operation behavior spec**. It is high-level and
language-agnostic: no code, no per-language implementation choices, no HTTP
routing detail (that belongs in `qc_interface.md`). Its job is to pin down
*behavior* precisely enough that three independent implementations, in three
different languages, would all make the same semantic decisions.

Write one section per operation in `contract.md`. Do not invent operations
that aren't in `contract.md` — this file elaborates on the contract, it
doesn't extend it.

## Structure to follow

```markdown
# Stage Plan: <API Name>

Derived from `core/<api-name>/contract.md`. Behavior spec only — no code,
no per-language implementation choices.

## Generated / server-controlled fields

For each field in the resource that the client does not set directly
(server-generated IDs, timestamps, computed scores, etc.), state:
- What it means / represents.
- When it's assigned (on create only? recomputed on every read?).
- Whether it can ever be mutated by the client (usually: no).
- What "equal" or "valid" looks like for QC purposes (e.g. "must be
  present and non-empty", "must be a valid ISO 8601 datetime").

## Operations

### `<operation_name>`

- **Trigger / when it's called:** one line.
- **Inputs:** which fields are required vs optional, and any validation
  rules beyond basic typing (e.g. "title must be non-empty").
- **Success behavior:** what changes, what's returned, exact shape at a
  conceptual level (defer wire format to qc_interface.md).
- **Edge cases:**
  - Not-found behavior, if applicable (which id, what should happen).
  - Invalid-input behavior (malformed fields, missing required fields).
  - Any operation-specific edge case called out in contract.md.
- **Idempotency / side effects:** note if calling twice has different
  effects the wrapper author needs to know about.

(Repeat for every operation in contract.md, in the same order they
appear in contract.md.)

## Partial-failure / batch operations (if any)

If contract.md defines an operation with partial-failure semantics
(e.g. a bulk operation where some items succeed and some fail), give it
its own subsection, separate from the per-operation list above:

- Exact conditions under which an individual item fails vs succeeds.
- Whether a failing item can have partial side effects (usually: no —
  each item's change is atomic, only cross-item failure isolation
  varies).
- Explicitly flag this as the place where per-language idiom will
  diverge (exceptions vs. result objects vs. settled-promise arrays,
  etc.) — the *behavior* is fixed here, but the *representation* is
  intentionally left to each language's micro-agent.

## Cross-cutting edge cases

Anything that applies across multiple operations rather than to one
(e.g. "every not-found case uses the same error semantics", "every
timestamp field is UTC").
```

## What NOT to put here

- HTTP methods, routes, status codes → `qc_interface.md` /
  `qc_interface.openapi.json`.
- Language-specific naming, error types, async patterns → per-language
  guidance notes (optional, brief, steering-only — see SKILL.md).
- Anything not derivable from `contract.md` + the OpenAPI spec. If you
  need to make a judgment call the contract doesn't settle, say so
  explicitly in the draft (e.g. "contract.md doesn't specify X — this
  plan assumes Y; flag during review if that's wrong") rather than
  silently picking one.

## Source of truth

- `contract.md` is authoritative for *what* operations exist and their
  semantics. Never contradict it.
- The OpenAPI spec is a secondary source for HTTP-shape details (status
  codes actually used, exact response schemas) but is not authoritative
  over contract.md for behavior. If the OpenAPI spec exposes an
  operation contract.md doesn't mention, note it as an open question in
  the draft rather than silently planning around it or silently
  dropping it.
