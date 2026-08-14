#!/usr/bin/env python3
"""
preflight.py — validate inputs before /implement-wrapper drafts an
implementation plan or writes any code.

Usage:
    python3 preflight.py <api-name> <language> [--repo-root PATH]

Example:
    python3 preflight.py mock-api python
    python3 preflight.py mock-api go --repo-root /home/claude/WrapperForge/WrapperForge

What it checks:
    - <language> is one of: python, go, javascript.
    - core/<api-name>/ exists and contains all required approved
      artifacts: contract.md, stage_plan.md, qc_interface.md,
      qc_interface.openapi.json. This mirrors macro-planning's
      promote.py incomplete-draft-set refusal, one level down: an
      incomplete/unapproved core/<api-name>/ is treated as a hard
      stop, not something to work around.
    - qc_interface.openapi.json parses as valid JSON.
    - Whether wrappers/<api-name>/<language>/ already has files in it
      (informational only — re-running for a language that was already
      built is allowed, e.g. after a plan revision, but the agent
      should be aware it may be overwriting prior output).

This script does not write anything (aside from nothing — it's fully
read-only). It prints a small JSON report to stdout:

    {
      "ok": true/false,
      "api_name": "...",
      "language": "...",
      "core_dir": "...",
      "errors": [...],
      "warnings": [...],
      "existing_wrapper_files": [...]
    }
"""

import argparse
import json
import sys
from pathlib import Path

VALID_LANGUAGES = ("python", "go", "javascript")

REQUIRED_CORE_FILES = [
    "contract.md",
    "stage_plan.md",
    "qc_interface.md",
    "qc_interface.openapi.json",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("api_name", help="API name/slug, e.g. 'mock-api'")
    parser.add_argument("language", help="One of: python, go, javascript")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Path to the repo root (directory containing core/ and wrappers/). Defaults to CWD.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    errors = []
    warnings = []

    language = args.language.strip().lower()
    if language not in VALID_LANGUAGES:
        errors.append(
            f"Invalid language '{args.language}'. Must be one of: "
            f"{', '.join(VALID_LANGUAGES)}."
        )

    core_dir = repo_root / "core" / args.api_name
    if not core_dir.is_dir():
        errors.append(
            f"core/{args.api_name}/ not found at {core_dir}. Run /macro-planning "
            "and get it approved for this API before running /implement-wrapper."
        )
    else:
        missing = [f for f in REQUIRED_CORE_FILES if not (core_dir / f).is_file()]
        if missing:
            errors.append(
                f"core/{args.api_name}/ is incomplete. Missing: {', '.join(missing)}. "
                "This means macro-planning hasn't been fully approved/promoted for "
                "this API yet."
            )

        openapi_path = core_dir / "qc_interface.openapi.json"
        if openapi_path.is_file():
            try:
                json.loads(openapi_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errors.append(f"qc_interface.openapi.json is not valid JSON: {e}")

    existing_wrapper_files = []
    if language in VALID_LANGUAGES:
        wrapper_dir = repo_root / "wrappers" / args.api_name / language
        if wrapper_dir.is_dir():
            existing_wrapper_files = sorted(
                str(p.relative_to(wrapper_dir)) for p in wrapper_dir.rglob("*") if p.is_file()
            )
            if existing_wrapper_files:
                warnings.append(
                    f"wrappers/{args.api_name}/{language}/ already has "
                    f"{len(existing_wrapper_files)} file(s). Proceeding will "
                    "overwrite/update them — confirm that's intended."
                )

    report = {
        "ok": len(errors) == 0,
        "api_name": args.api_name,
        "language": language,
        "core_dir": str(core_dir),
        "errors": errors,
        "warnings": warnings,
        "existing_wrapper_files": existing_wrapper_files,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
