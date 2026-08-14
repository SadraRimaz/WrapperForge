#!/usr/bin/env python3
"""
tests/audit.py — Blind QC: static differential-testing runner.

WrapperForge's QC harness. It is intentionally "dumb": it spawns no
processes, seeds nothing, and knows nothing about any language wrapper
internals. It loads a fully-resolved, pre-approved test-case file
(`core/<api-name>/cases.json`, produced by the `/macro-planning` skill
and human-approved before promotion) and, for each case:

  1. Sends the `direct` request to the real backend (already running,
     started manually — see README / plan.md Phase 1).
  2. Sends the `wrapper` request to the language-specific QC server
     (already running — started by `/implement-wrapper` as the final
     step of its own workflow, which then invokes this script).
  3. Compares the two responses, restricted to the fields declared for
     that response in `core/<api-name>/qc_interface.openapi.json`
     (schema-driven allowlist — incidental extras like request IDs are
     ignored).
  4. Logs pass/fail + a free-text reason per case, and prints a summary
     table at the end.

This script never reads anything under `wrappers/<lang>/` — it only
speaks HTTP against the two base URLs it's given. True black box.

Usage:
    python3 tests/audit.py \\
        --cases core/mock-api/cases.json \\
        --openapi core/mock-api/qc_interface.openapi.json \\
        --server-base-url http://localhost:8100

    (--direct-base-url is optional; if omitted it's read from the
    "direct_base_url" key at the top of cases.json.)

Exit code: 0 if every case passed, 1 otherwise (so it composes cleanly
with `/implement-wrapper`'s "start server -> run audit -> report"
final step, or any future CI use).
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional


# --------------------------------------------------------------------------
# Data shapes
# --------------------------------------------------------------------------

@dataclass
class CallSpec:
    method: str
    endpoint: str
    body: Optional[dict] = None

    @staticmethod
    def from_dict(d: dict) -> "CallSpec":
        method = d.get("method")
        endpoint = d.get("endpoint")
        if not method or not endpoint:
            raise ValueError(f"call spec missing 'method' or 'endpoint': {d!r}")
        return CallSpec(method=str(method).upper(), endpoint=str(endpoint), body=d.get("body"))


@dataclass
class Case:
    case_id: str
    direct: CallSpec
    wrapper: CallSpec
    edge_case_label: Optional[str] = None

    @staticmethod
    def from_dict(d: dict) -> "Case":
        case_id = d.get("case_id")
        if not case_id:
            raise ValueError(f"case missing 'case_id': {d!r}")
        if "direct" not in d or "wrapper" not in d:
            raise ValueError(f"case {case_id!r} missing 'direct' and/or 'wrapper' spec")
        return Case(
            case_id=str(case_id),
            direct=CallSpec.from_dict(d["direct"]),
            wrapper=CallSpec.from_dict(d["wrapper"]),
            edge_case_label=d.get("edge_case_label"),
        )


@dataclass
class CallResult:
    status: Optional[int] = None
    body: Any = None
    error: Optional[str] = None  # transport-level error (connection refused, timeout, non-JSON body, ...)


@dataclass
class CaseResult:
    case_id: str
    passed: bool
    reason: str = ""
    edge_case_label: Optional[str] = None


# --------------------------------------------------------------------------
# Loading inputs
# --------------------------------------------------------------------------

def load_cases(path: str) -> tuple[list[Case], Optional[str]]:
    """Returns (cases, direct_base_url_from_file_or_None)."""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if isinstance(raw, dict):
        direct_base_url = raw.get("direct_base_url")
        raw_cases = raw.get("cases")
        if raw_cases is None:
            raise ValueError(
                f"{path}: expected a top-level 'cases' list "
                f"(optionally alongside 'direct_base_url')"
            )
    elif isinstance(raw, list):
        # Bare list form: no direct_base_url in the file; must be passed via CLI.
        direct_base_url = None
        raw_cases = raw
    else:
        raise ValueError(f"{path}: top level must be a JSON object or list")

    cases = [Case.from_dict(c) for c in raw_cases]
    if not cases:
        raise ValueError(f"{path}: no cases found")
    return cases, direct_base_url


def load_openapi_schemas(path: str) -> dict:
    """Returns the parsed OpenAPI document's 'paths' section (or {} if absent)."""
    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    return doc.get("paths", {})


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def do_request(base_url: str, spec: CallSpec, timeout: float = 10.0) -> CallResult:
    url = base_url.rstrip("/") + "/" + spec.endpoint.lstrip("/")
    data = None
    headers = {}
    if spec.body is not None:
        data = json.dumps(spec.body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=spec.method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            raw = resp.read()
    except urllib.error.HTTPError as e:
        # Non-2xx is a normal, expected outcome (e.g. 404 for not-found cases) —
        # not a transport error. Capture status + body as usual.
        status = e.code
        raw = e.read()
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        return CallResult(error=f"transport error calling {spec.method} {url}: {e}")

    body: Any = None
    if raw:
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            return CallResult(status=status, error=f"non-JSON response body: {e}")

    return CallResult(status=status, body=body)


# --------------------------------------------------------------------------
# Schema-driven comparison
# --------------------------------------------------------------------------

def resolve_schema(openapi_paths: dict, endpoint: str, method: str, status: Optional[int]) -> Optional[dict]:
    """Look up the response schema for (endpoint, method, status) in the
    QC OpenAPI doc's 'paths' section. Returns None if not found, in which
    case comparison falls back to comparing full response bodies."""
    path_item = openapi_paths.get(endpoint) or openapi_paths.get("/" + endpoint.lstrip("/"))
    if not path_item:
        return None
    op = path_item.get(method.lower())
    if not op:
        return None
    responses = op.get("responses", {})
    resp = responses.get(str(status)) or responses.get("default")
    if not resp:
        return None
    content = resp.get("content", {})
    json_content = content.get("application/json", {})
    return json_content.get("schema")


def allowed_fields(schema: Optional[dict]) -> Optional[set]:
    """Top-level property names declared in a JSON-schema object. Returns
    None if the schema doesn't declare an object with properties (so the
    caller should compare the full body instead of filtering)."""
    if not schema or not isinstance(schema, dict):
        return None
    if "$ref" in schema:
        # References into components.schemas aren't resolved here (audit.py
        # deliberately doesn't do full JSON-Schema resolution) — treat as
        # "unknown shape" and fall back to full-body comparison.
        return None
    props = schema.get("properties")
    if not isinstance(props, dict):
        return None
    return set(props.keys())


def filter_to_allowed(body: Any, fields: Optional[set]) -> Any:
    if fields is None or not isinstance(body, dict):
        return body
    return {k: v for k, v in body.items() if k in fields}


def compare_bodies(direct_filtered: Any, wrapper_filtered: Any) -> Optional[str]:
    """Returns None if equal, else a short human-readable mismatch reason."""
    if direct_filtered == wrapper_filtered:
        return None
    if isinstance(direct_filtered, dict) and isinstance(wrapper_filtered, dict):
        mismatched = []
        all_keys = set(direct_filtered) | set(wrapper_filtered)
        for k in sorted(all_keys):
            dv = direct_filtered.get(k, "<missing>")
            wv = wrapper_filtered.get(k, "<missing>")
            if dv != wv:
                mismatched.append(f"{k} (direct={dv!r} vs wrapper={wv!r})")
        return "value_mismatch on field(s): " + ", ".join(mismatched)
    return f"body mismatch: direct={direct_filtered!r} vs wrapper={wrapper_filtered!r}"


# --------------------------------------------------------------------------
# Per-case evaluation
# --------------------------------------------------------------------------

def run_case(case: Case, direct_base_url: str, server_base_url: str, openapi_paths: dict) -> CaseResult:
    direct_result = do_request(direct_base_url, case.direct)
    if direct_result.error:
        return CaseResult(
            case_id=case.case_id,
            passed=False,
            reason=f"direct call failed: {direct_result.error}",
            edge_case_label=case.edge_case_label,
        )

    wrapper_result = do_request(server_base_url, case.wrapper)
    if wrapper_result.error:
        return CaseResult(
            case_id=case.case_id,
            passed=False,
            reason=f"wrapper call failed: {wrapper_result.error}",
            edge_case_label=case.edge_case_label,
        )

    if direct_result.status != wrapper_result.status:
        return CaseResult(
            case_id=case.case_id,
            passed=False,
            reason=(
                f"status code mismatch: direct={direct_result.status} "
                f"vs wrapper={wrapper_result.status}"
            ),
            edge_case_label=case.edge_case_label,
        )

    schema = resolve_schema(openapi_paths, case.wrapper.endpoint, case.wrapper.method, wrapper_result.status)
    fields = allowed_fields(schema)

    direct_filtered = filter_to_allowed(direct_result.body, fields)
    wrapper_filtered = filter_to_allowed(wrapper_result.body, fields)

    mismatch = compare_bodies(direct_filtered, wrapper_filtered)
    if mismatch:
        return CaseResult(
            case_id=case.case_id,
            passed=False,
            reason=mismatch,
            edge_case_label=case.edge_case_label,
        )

    return CaseResult(case_id=case.case_id, passed=True, edge_case_label=case.edge_case_label)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="WrapperForge blind QC: static differential-testing runner.")
    parser.add_argument(
        "--cases",
        required=True,
        help="Path to the approved cases.json (e.g. core/mock-api/cases.json).",
    )
    parser.add_argument(
        "--openapi",
        required=True,
        help="Path to the approved qc_interface.openapi.json (e.g. core/mock-api/qc_interface.openapi.json).",
    )
    parser.add_argument(
        "--server-base-url",
        required=True,
        help="Base URL of the running language-specific QC server, e.g. http://localhost:8100.",
    )
    parser.add_argument(
        "--direct-base-url",
        default=None,
        help=(
            "Base URL of the running real backend, e.g. http://localhost:8000. "
            "Optional if cases.json declares a top-level 'direct_base_url'; "
            "if both are given, this flag wins."
        ),
    )
    args = parser.parse_args()

    try:
        cases, direct_base_url_from_file = load_cases(args.cases)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"error loading cases file: {e}", file=sys.stderr)
        return 1

    direct_base_url = args.direct_base_url or direct_base_url_from_file
    if not direct_base_url:
        print(
            "error: no direct backend base URL given — pass --direct-base-url or "
            "add a top-level \"direct_base_url\" to cases.json",
            file=sys.stderr,
        )
        return 1

    try:
        openapi_paths = load_openapi_schemas(args.openapi)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"error loading openapi file: {e}", file=sys.stderr)
        return 1

    results: list[CaseResult] = []
    for case in cases:
        results.append(run_case(case, direct_base_url, args.server_base_url, openapi_paths))

    # --- report ---
    print(f"\nWrapperForge QC — {len(results)} case(s)")
    print(f"  direct backend:  {direct_base_url}")
    print(f"  wrapper server:  {args.server_base_url}\n")

    width = max((len(r.case_id) for r in results), default=8)
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        label = f" [{r.edge_case_label}]" if r.edge_case_label else ""
        line = f"  {status:<4}  {r.case_id:<{width}}{label}"
        if not r.passed:
            line += f"\n        reason: {r.reason}"
        print(line)

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    print(f"\n{passed}/{len(results)} passed, {failed} failed\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
