"""
Deterministic RNG helpers for the mock Tasks API.

The backend is started with a SEED env var (see main.py). All
"server-generated" randomness (priority_score, created_at jitter) is
derived from a single random.Random(seed) instance scoped to that
process, so that two separate process starts with the same SEED
produce identical output given the same sequence of calls.
"""

import random
from datetime import datetime, timedelta, timezone


class SeededGenerator:
    """Wraps a single random.Random instance for all generated fields."""

    def __init__(self, seed: int):
        self.seed = seed
        self._rng = random.Random(seed)
        # Fixed anchor so created_at jitter is reproducible across runs,
        # not just internally consistent within one run.
        self._epoch = datetime(2025, 1, 1, tzinfo=timezone.utc)

    def priority_score(self) -> float:
        """A pseudo-random priority score in [0, 100), rounded to 2dp."""
        return round(self._rng.uniform(0, 100), 2)

    def created_at(self) -> str:
        """An ISO 8601 UTC timestamp, jittered from a fixed epoch."""
        jitter_seconds = self._rng.randint(0, 60 * 60 * 24 * 365)
        ts = self._epoch + timedelta(seconds=jitter_seconds)
        return ts.isoformat()
