#!/usr/bin/env python3
"""Run N4H2F process_data yaw-noise provenance audit.

中文说明：只读外部 KF-GINS 脚本，variant `.gnss` 只生成到临时目录；
不修改外部源码，不提交 artifacts。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.evaluation.actual_input_yaw_variant_match import (  # noqa: E402
    compare_actual_input_to_variants,
    write_actual_input_yaw_variant_match_report,
)
from legsa_gins.source_audit.process_data_noise_provenance import (  # noqa: E402
    audit_process_data_script,
    audit_run_final_mainline,
    generate_yaw_variant_inputs,
    make_process_data_noise_provenance_report,
    write_json_report,
)
from legsa_gins.evaluation.replay_reference_mapping_audit import locate_n4h2_replay_outputs  # noqa: E402
from legsa_gins.visualization.startup_transient_audit import update_visual_case_review_with_audits  # noqa: E402


def run(args: argparse.Namespace) -> dict:
    external = Path(args.external_source_root)
    dual_root = Path(args.dual_root)
    n4h2_root = Path(args.n4h2_artifacts_root)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    process_data = external / "bin" / "process_data.py"
    run_mainline = external / "scripts" / "run_final_mainline.py"
    process_audit = audit_process_data_script(process_data)
    run_audit = audit_run_final_mainline(run_mainline)
    variant_output = Path(tempfile.gettempdir()) / "legsa_n4h2f_yaw_variants"
    replay_locations = locate_n4h2_replay_outputs(n4h2_root)
    fallback_input = (replay_locations.get("located_files") or {}).get("input_gnss")
    generation = generate_yaw_variant_inputs(
        variant_output,
        process_data_path=process_data,
        fallback_input_gnss=fallback_input,
    )
    variant_inputs = generation.get("variant_inputs") or {}
    match = compare_actual_input_to_variants(dual_root / "input.gnss", variant_inputs)
    fixed_std = None
    # The yaw-std runner owns the detailed observation-std evidence; keep this flag independent.
    match["fixed_yaw_std_1p5_detected"] = fixed_std
    provenance = make_process_data_noise_provenance_report(process_audit, run_audit, generation, match)
    write_json_report(output / "RUN_FINAL_MAINLINE_PROVENANCE_REPORT.json", run_audit)
    write_actual_input_yaw_variant_match_report(output / "ACTUAL_INPUT_YAW_VARIANT_MATCH_REPORT.json", match)
    write_json_report(output / "PROCESS_DATA_NOISE_PROVENANCE_REPORT.json", provenance)
    update_visual_case_review_with_audits(output)
    return provenance


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dual-root", default=str(Path.home() / "legsa_external_artifacts" / "dual_final_v23_nominal"))
    parser.add_argument("--n4h2-artifacts-root", default=str(Path.home() / "legsa_n4h2_artifacts"))
    parser.add_argument("--external-source-root", default=str(Path.home() / "KF-GINS"))
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    report = run(parse_args(argv))
    print(json.dumps({"actual_yaw_noise_injection_status": report.get("actual_yaw_noise_injection_status")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
