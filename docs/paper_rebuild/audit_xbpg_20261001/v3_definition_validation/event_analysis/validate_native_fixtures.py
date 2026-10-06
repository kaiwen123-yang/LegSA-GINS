#!/usr/bin/env python3
"""Read six already-produced NEW candidate synthetic streams. Native calls: zero."""
import argparse
import json
from pathlib import Path

import analyze_events as a

SELECTED = [
    ("n16_baseline", "BASELINE", "hv2d_quality_1p5", "<VALIDATION_BUILD_ROOT>/fixtures_N16_ONLY/baseline/hv2d_quality_1p5/observer/events.jsonl"),
    ("n16_candidate", "N16_ONLY", "hv2d_quality_1p5", "<VALIDATION_BUILD_ROOT>/fixtures_N16_ONLY/candidate_on/hv2d_quality_1p5/observer/events.jsonl"),
    ("n12_baseline", "BASELINE", "dx_zero", "<VALIDATION_BUILD_ROOT>/N12_tests_v1/baseline/dx_zero/observer/events.jsonl"),
    ("n12_candidate", "N12_ONLY", "dx_zero", "<VALIDATION_BUILD_ROOT>/N12_tests_v1/candidate/dx_zero/observer/events.jsonl"),
    ("n09_accepted_res3", "N09_RP_ONLY", "accepted_res3", "<VALIDATION_BUILD_ROOT>/N09_RP_ONLY_fixture_v1/candidate_on/accepted_res3/observer/events.jsonl"),
    ("n09_rejected_res3", "N09_RP_ONLY", "rejected_res3", "<VALIDATION_BUILD_ROOT>/N09_RP_ONLY_fixture_v1/candidate_on/rejected_res3/observer/events.jsonl"),
]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--roots", type=Path, required=True)
    p.add_argument("--output-alias", required=True)
    args = p.parse_args()
    aliases = json.loads(args.roots.read_text())["aliases"]
    if not args.output_alias.startswith("<VALIDATION_ROOT>/analysis/"):
        raise ValueError("OUTPUT_MUST_BE_ISOLATED_VALIDATION_ANALYSIS")
    output = a.resolve(args.output_alias, aliases)
    output.mkdir(parents=True, exist_ok=False)
    rows, summaries = [], {}
    for name, candidate, run, source in SELECTED:
        summary = a.scan_stream(a.resolve(source, aliases), output/name, source_alias=source,
            run_id=run, candidate_id=candidate, group="SYNTHETIC", data_mode="synthetic_fixture_only",
            identity=dict(source="new candidate native fixtures already produced; no native launched by analyzer"))
        summaries[name] = summary
        rows.append(dict(label=name, source_path=source, candidate_id=candidate, run_id=run,
            stream_status=summary["stream_status"], analysis_status=summary["analysis_status"],
            events_read=summary["events_read"], source_sha256=summary["source_sha256"],
            SA_counts=summary["sa_validation_counts"], covariance=summary["covariance"],
            stream_error=summary["stream_error"], diagnostic_anomalies=summary["diagnostic_anomalies"]))
    pairs = []
    for name in ("n16", "n12"):
        try:
            s = a.compare_caches(output/(name+"_candidate"), output/(name+"_baseline"), output/(name+"_comparison"))
            pairs.append(dict(name=name, status=s["analysis_status"], measurements=s["measurement_counts"],
                              first_differences=list(s["first_differences"]), common_IMU_counts=s["common_IMU_counts"]))
        except Exception as exc:
            pairs.append(dict(name=name, status="FAILED", error=type(exc).__name__+":"+str(exc)))
    passed = all(r["analysis_status"] == "VALIDATED" for r in rows) and all(p["status"] == "VALIDATED" for p in pairs)
    receipt = dict(status="PASS" if passed else "FAIL_RETAINED", data_mode="synthetic_fixture_only",
        synthetic_data_used=True, semisynthetic_data_used=False, streams=rows, comparisons=pairs,
        selected_existing_new_synthetic_streams=len(rows), complete_stream_scans=sum(s["complete_payload_scan_count"] for s in summaries.values()),
        raw_event_lines_read=sum(s["events_read"] for s in summaries.values()),
        new_native_processes=0, real_native_calls=0, evaluator_calls=0, provider_calls=0,
        real_event_reads=0, source_sha256=a.sha(Path(__file__)), analyzer_sha256=a.sha(Path(a.__file__)),
        output_root=args.output_alias,
        coverage_notes=["N12 dx_zero uses public helper calls without newImuProcess, so COVARIANCE_HEALTH coverage is zero, not missing IMU coverage.",
                        "N09 accepted/rejected res3 streams validate scheduler schema; no baseline native fixture was rerun.",
                        "These are analyst tests over synthetic inputs, never real-data performance evidence."])
    a.write_json(output/"FIXTURE_ANALYSIS_RECEIPT.json", receipt)
    print(a.js(receipt))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
