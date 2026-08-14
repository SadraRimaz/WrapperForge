#!/usr/bin/env python3
"""
smoke_test_server.py — verify a QC server honors the fixed process
convention: binds to PORT and responds 200 on GET /health.

This does NOT start the server itself (start commands differ per
language and this script stays language-agnostic on purpose). It
assumes a server is already running at the given port and just checks
the one thing every language's server must get right before any
audit.py-style differential testing can work against it.

Usage:
    python3 smoke_test_server.py <port> [--timeout SECONDS]

Example:
    # in one terminal: PORT=8080 python3 wrappers/mock-api/python/server/main.py
    python3 smoke_test_server.py 8080

Exit code 0 and prints "OK" if /health returns 200 within the timeout.
Exit code 1 with a clear error otherwise (connection refused, timeout,
non-200 status).
"""

import argparse
import sys
import time
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", type=int, help="Port the server should be listening on")
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Seconds to wait for the server to come up (default: 10)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="Seconds between retries (default: 0.5)",
    )
    args = parser.parse_args()

    url = f"http://127.0.0.1:{args.port}/health"
    deadline = time.monotonic() + args.timeout
    last_error = None

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    print(f"OK: GET {url} -> 200")
                    return 0
                last_error = f"GET {url} -> {resp.status} (expected 200)"
        except urllib.error.URLError as e:
            last_error = f"GET {url} failed: {e}"
        time.sleep(args.interval)

    print(f"ERROR: {last_error or 'server did not respond within timeout'}", file=sys.stderr)
    print(
        "Check that the server: (1) is actually running, (2) reads its port "
        "from the PORT env var rather than hardcoding one, (3) exposes "
        "GET /health returning 200.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
