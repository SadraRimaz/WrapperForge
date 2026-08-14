#!/usr/bin/env python3
"""
preflight.py — validate inputs and derive the api-name slug before
macro-planning drafts anything.

Usage:
    python3 preflight.py <contract.md path> <openapi.json path>

What it checks:
    - Both files exist and are readable.
    - openapi.json is valid JSON and looks like an OpenAPI/Swagger doc
      (has an "openapi" or "swagger" top-level key, plus "paths").
    - Derives an api-name slug from contract.md's parent directory name
      (e.g. core/mock_api/contract.md -> "mock-api"), lowercased and
      hyphenated per the convention this skill uses for
      drafts/macro_output/<api-name>/ and core/<api-name>/.

Prints a small JSON report to stdout:
    {
      "ok": true/false,
      "api_name": "...",
      "contract_path": "...",
      "openapi_path": "...",
      "openapi_operation_count": N,
      "errors": [...],
      "warnings": [...]
    }

This script does not write anything. It's read-only reconnaissance so
the agent can decide the api-name slug and confirm it with the user
before creating drafts/macro_output/<api-name>/.
"""

import json
import re
import sys
from pathlib import Path


def slugify(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return name or "api"


def main() -> int:
    if len(sys.argv) != 3:
        print(
            json.dumps(
                {
                    "ok": False,
                    "errors": [
                        "Usage: preflight.py <contract.md path> <openapi.json path>"
                    ],
                }
            )
        )
        return 1

    contract_path = Path(sys.argv[1])
    openapi_path = Path(sys.argv[2])

    errors = []
    warnings = []

    if not contract_path.is_file():
        errors.append(f"contract file not found: {contract_path}")
    if not openapi_path.is_file():
        errors.append(f"openapi file not found: {openapi_path}")

    openapi_operation_count = None
    if openapi_path.is_file():
        try:
            spec = json.loads(openapi_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"openapi file is not valid JSON: {e}")
            spec = None

        if spec is not None:
            if "openapi" not in spec and "swagger" not in spec:
                warnings.append(
                    "openapi file has no 'openapi' or 'swagger' top-level key — "
                    "double-check this is really an OpenAPI/Swagger document."
                )
            paths = spec.get("paths", {})
            if not paths:
                warnings.append("openapi file has no 'paths' — spec looks empty.")
            op_count = 0
            for _route, methods in paths.items():
                for method in methods:
                    if method.lower() in (
                        "get",
                        "post",
                        "put",
                        "patch",
                        "delete",
                        "options",
                        "head",
                    ):
                        op_count += 1
            openapi_operation_count = op_count

    api_name = None
    if contract_path.is_file() or str(contract_path) != ".":
        parent_dir_name = contract_path.resolve().parent.name
        api_name = slugify(parent_dir_name)
        if api_name in ("core", "", "."):
            warnings.append(
                f"Derived api-name '{api_name}' from contract.md's parent folder "
                f"looks generic/wrong. contract.md should live at "
                f"core/<api-name>/contract.md — confirm the intended api-name "
                f"with the user rather than trusting this."
            )

    report = {
        "ok": len(errors) == 0,
        "api_name": api_name,
        "contract_path": str(contract_path),
        "openapi_path": str(openapi_path),
        "openapi_operation_count": openapi_operation_count,
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
