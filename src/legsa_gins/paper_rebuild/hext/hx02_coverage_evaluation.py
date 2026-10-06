"""HX-02 coverage-aware statistics child for sparse IMU-point NAV (GINav).

Registered, reference-free evaluator child (strace-audited: the reference must
not be opened). Definitions follow the CLEAN4 coverage-aware GINav record with
the v3 window convention (closed window, per-sequence base_time):
  * expected epochs = integer seconds k with w0 <= k <= w1;
  * row coverage = valid NAV rows inside the window / expected epochs;
  * temporal coverage = (last - first valid output time) / (w1 - w0);
  * maximum gap = largest spacing between adjacent valid rows;
  * a new segment starts when the adjacent spacing exceeds 1.5 s.
Missing leading output stays in the denominators; nothing is filled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

SCHEMA = "hx02.coverage_evaluation.v1"
SEGMENT_SPLIT_S = 1.5


def coverage(times_rel_s: Sequence[float], window: Sequence[float]) -> dict[str, Any]:
    start, end = map(float, window)
    times = np.asarray(times_rel_s, dtype=float)
    if np.any(~np.isfinite(times)) or np.any(np.diff(times) <= 0.0):
        raise ValueError("coverage input times must be finite and strictly increasing")
    inside = times[(times >= start) & (times <= end)]
    expected = int(math.floor(end) - math.ceil(start) + 1)
    gaps = np.diff(inside)
    return {
        "schema": SCHEMA, "window_seconds": [start, end], "window_duration_s": end - start,
        "expected_integer_epochs": expected, "valid_rows_in_window": int(inside.size),
        "row_coverage_fraction": inside.size / expected if expected else None,
        "first_valid_rel_s": float(inside[0]) if inside.size else None,
        "last_valid_rel_s": float(inside[-1]) if inside.size else None,
        "output_span_s": float(inside[-1] - inside[0]) if inside.size else 0.0,
        "temporal_coverage_fraction": float(inside[-1] - inside[0]) / (end - start) if inside.size else 0.0,
        "max_gap_s": float(np.max(gaps)) if gaps.size else None,
        "segment_count": int(1 + np.count_nonzero(gaps > SEGMENT_SPLIT_S)) if inside.size else 0,
        "leading_missing_s": float(inside[0] - start) if inside.size else end - start,
        "segment_split_s": SEGMENT_SPLIT_S,
        "definitions": __doc__.split("Definitions follow", 1)[1].strip(),
    }


def evaluate(spec: Mapping[str, Any]) -> dict[str, Any]:
    outdir = Path(spec["outdir"])
    outdir.mkdir(parents=True, exist_ok=False)
    payload = Path(spec["nav"]).read_bytes()
    if hashlib.sha256(payload).hexdigest() != spec["nav_sha256"]:
        raise ValueError("coverage NAV SHA-256 mismatch")
    rows = [line.split() for line in payload.decode("utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith(("#", "%", "index"))]
    times = [float(row[1]) for row in rows]
    result = {**coverage(times, spec["window"]), "sequence_id": spec["sequence_id"],
              "nav_sha256": spec["nav_sha256"], "nav_rows": len(rows), "reference_opened": False}
    with (outdir / "COVERAGE_METRICS.json").open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    args = parser.parse_args(argv)
    evaluate(json.loads(args.spec.read_text(encoding="utf-8")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
