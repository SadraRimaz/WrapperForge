#!/usr/bin/env python3
"""
promote.py — promote approved macro-planning drafts into core/<api-name>/.

This is the ONLY sanctioned way draft artifacts become "approved" content
under core/. It is intentionally dumb: it does not re-generate or edit
anything, it just verifies the required files exist in the draft folder
and copies them verbatim, refusing to run if the draft set is incomplete.

Usage:
    python3 promote.py <api-name> [--repo-root PATH]

Example:
    python3 promote.py mockapi
    python3 promote.py mockapi --repo-root /home/claude/WrapperForge/WrapperForge

Behavior:
    - Source:      <repo-root>/drafts/macro_output/<api-name>/
    - Destination: <repo-root>/core/<api-name>/
    - Required files in source: stage_plan.md, qc_interface.md,
      qc_interface.openapi.json, cases.json
    - contract.md is NOT touched by this script. It is hand-written and
      is expected to already live at core/<api-name>/contract.md before
      macro-planning ever runs (see SKILL.md).
    - Refuses to promote if any required file is missing.
    - Overwrites existing files at the destination (promotion is meant to
      be re-run after revisions), but never deletes files at the
      destination that aren't part of this promotion (e.g. contract.md).
    - Prints a summary of what was copied.
"""

import argparse
import shutil
import sys
from pathlib import Path

REQUIRED_FILES = [
    "stage_plan.md",
    "qc_interface.md",
    "qc_interface.openapi.json",
    "cases.json",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("api_name", help="API name/slug, e.g. 'mockapi'")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Path to the repo root (directory containing core/ and drafts/). Defaults to CWD.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    src = repo_root / "drafts" / "macro_output" / args.api_name
    dst = repo_root / "core" / args.api_name

    if not src.is_dir():
        print(f"ERROR: draft folder not found: {src}", file=sys.stderr)
        return 1

    missing = [f for f in REQUIRED_FILES if not (src / f).is_file()]
    if missing:
        print(
            f"ERROR: draft set at {src} is incomplete. Missing: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    dst.mkdir(parents=True, exist_ok=True)

    copied = []
    for f in REQUIRED_FILES:
        shutil.copy2(src / f, dst / f)
        copied.append(f)

    # Optional per-language guidance notes file, if the macro-planning
    # skill produced one — not required, promoted if present.
    optional = "language_notes.md"
    if (src / optional).is_file():
        shutil.copy2(src / optional, dst / optional)
        copied.append(optional)

    print(f"Promoted {len(copied)} file(s) from {src} to {dst}:")
    for f in copied:
        print(f"  - {f}")

    contract_path = dst / "contract.md"
    if not contract_path.is_file():
        print(
            f"\nNOTE: {contract_path} does not exist. contract.md is hand-written "
            "and is not part of this promotion — make sure it's in place before "
            "micro-agents (/implement-wrapper) read from core/."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
