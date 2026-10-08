#!/usr/bin/env python3
"""Read BY2 events and report input coverage; never import or run a navigator."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from legsa_gins.paper_rebuild.joint_navigation.real_data import By2InputConfig, load_by2_events


def json_value(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("body", "imu", "gnss", "carrier-plan", "calibration-model"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--noise-profile", type=Path, default=ROOT / "configs/paper_rebuild/horizontal_literature/hartley/stage_payload/04_METHOD_CONTRACTS/GO2_IMU_ALLAN_90MIN_RECOVERED_V1.yaml")
    parser.add_argument("--start", type=float, default=66.)
    parser.add_argument("--end", type=float, default=340.)
    parser.add_argument("--key-dt", type=float, default=.1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = load_by2_events(By2InputConfig(
        args.body, args.imu, args.gnss, args.carrier_plan,
        args.calibration_model, args.noise_profile,
        start_s=args.start, end_s=args.end, key_dt_s=args.key_dt))
    payload = dict(status="INPUT_CONVERSION_ONLY_NOT_NAVIGATION_EVIDENCE",
                   input_summary=result["input_summary"], metadata=result["metadata"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(json_value(payload), stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(json_value(result["input_summary"]), ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
