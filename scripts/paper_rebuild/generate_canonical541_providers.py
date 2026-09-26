#!/usr/bin/env python3
"""Generate C00 first, then 540 provider packages with effect validation."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from build_canonical541_manifest import load_base, load_local
from legsa_gins.paper_rebuild.canonical541.execution_plan import (
    validate_code_freeze_gate, validate_provider_gate,
)
from legsa_gins.paper_rebuild.canonical541.provider_generator import (
    resolve_provider_index, sha256_file, write_case_provider,
)
from legsa_gins.paper_rebuild.canonical541.raw_audit import ensure_raw_checkpoint
from legsa_gins.paper_rebuild.manifest import git_code_state


EXPECTED_RAW_LOCK_SHA256 = "f6e5d7965d17857e5b4a846501883f4675f2331a1164fab3de9e5ba9470f1ad7"
EXPECTED_FULL_LOCK_ROWS = 9980


def normalize_promoted_resolved_path(*, actual_path, cases_root, finalized):
    """Record an internal provider path at its post-promotion identity.

    Provider aggregates are assembled while case packages still live below an
    attempt-owned ``.staging_*/CASES`` directory.  Persisting that resolved
    path would become stale after the atomic rename to ``FINALIZED``.  Only
    paths inside the current cases root are rebased; external fresh-provider
    pointers retain their exact resolved identity.
    """

    actual = Path(actual_path).resolve(strict=True)
    cases = Path(cases_root).resolve(strict=True)
    promoted = Path(finalized).resolve(strict=False)
    provider_root = promoted.parent.resolve(strict=True)
    try:
        relative = actual.relative_to(cases)
    except ValueError:
        try:
            actual.relative_to(provider_root)
        except ValueError:
            return actual
        # 中文说明：provider root 内、但不属于当前 CASES/FINALIZED 的路径
        # 是旧 attempt 残留，不能伪装成 external pointer 写入 aggregate。
        raise RuntimeError(f"stale internal provider staging path: {actual}")
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError(f"unsafe provider promotion-relative path: {relative}")
    return (promoted / relative).resolve(strict=False)


def raw_checkpoint(paths, stage, phase):
    audits = stage / "16_AUDITS"
    audits.mkdir(parents=True, exist_ok=True)
    return ensure_raw_checkpoint(
        raw_root=paths["raw_root"],
        hash_lock_path=paths["clean_root"] / "01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK.csv",
        expected_lock_sha256=EXPECTED_RAW_LOCK_SHA256,
        expected_full_lock_rows=EXPECTED_FULL_LOCK_ROWS,
        output_root=audits,
        phase=phase,
    )


def normalize(row):
    output = dict(row)
    for key in ("case_index", "seed_value"): output[key] = int(output[key]) if output.get(key) not in ("", None) else output.get(key)
    for key in ("requires_randomness", "seed_effective", "independent_realization", "trace_eval_only", "final_v23_output_solver_input_allowed", "legsa_output_solver_input_allowed", "go2_truth_claim_allowed", "synthetic_data_used", "semisynthetic_data_used"):
        output[key] = str(output.get(key)).lower() == "true"
    output["anchor_time_s"] = float(output["anchor_time_s"]) if output.get("anchor_time_s") else output.get("anchor_time_s")
    return output


def csv_bytes(rows):
    import io
    items = list(rows); fields = list(items[0]) if items else ["empty"]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader(); writer.writerows(items)
    return buffer.getvalue().encode("utf-8")


def write_identical_csvs(paths, rows):
    payload = csv_bytes(rows); digest = hashlib.sha256(payload).hexdigest()
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        if sha256_file(path) != digest: raise RuntimeError("CSV alias hash mismatch")
    return digest


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--local-config", required=True); parser.add_argument("--jobs", type=int, default=12)
    parser.add_argument("--code-freeze-commit", required=True); parser.add_argument("--executable", required=True)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 16: raise SystemExit("provider jobs must be 1..16")
    paths = load_local(Path(args.local_config).resolve(strict=True)); stage = paths["runtime_root"]
    repo = Path(__file__).resolve().parents[2]; executable = Path(args.executable).resolve(strict=True)
    commit, dirty = git_code_state(repo)
    if dirty or commit != args.code_freeze_commit:
        raise SystemExit("provider generation requires exact clean code-freeze commit")
    validate_code_freeze_gate(
        stage_root=stage.resolve(strict=True), executable=executable,
        code_freeze_commit=args.code_freeze_commit,
    )
    pre_provider_raw = raw_checkpoint(paths, stage, "PRE_PROVIDER")
    base = load_base(paths); manifest = stage / "02_MATRIX_SPEC_LOCK/CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv"
    with manifest.open("r", encoding="utf-8-sig", newline="") as handle: cases = [normalize(row) for row in csv.DictReader(handle)]
    provider_root = paths["provider_root"]; provider_root.mkdir(parents=True, exist_ok=True)
    finalized = provider_root / "FINALIZED"
    final_out = stage / "06_PROVIDER_READY"
    if finalized.is_dir() and (final_out / "PROVIDER_GATE.json").is_file():
        report = validate_provider_gate(
            stage_root=stage, provider_root=provider_root, case_manifest=manifest,
        )
        post_provider_raw = raw_checkpoint(paths, stage, "POST_PROVIDER")
        print(json.dumps({**report, "resume_revalidated": True,
                          "raw_checkpoints": {"PRE_PROVIDER": pre_provider_raw,
                                              "POST_PROVIDER": post_provider_raw}},
                         indent=2, sort_keys=True))
        return
    attempt_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"_{os.getpid()}"
    attempt = provider_root / f".staging_{attempt_id}"; attempt.mkdir(parents=True, exist_ok=False)
    resumed_finalized = finalized.is_dir()
    if resumed_finalized:
        cases_root = finalized
        ready = [
            json.loads((cases_root / case["case_id"] / "04_PROVIDER_READY/provider_ready_manifest.json").read_text(encoding="utf-8"))
            for case in cases
        ]
    else:
        cases_root = attempt / "CASES"; cases_root.mkdir(parents=True, exist_ok=False)
        clean_root = cases_root / cases[0]["case_id"]
        ready = [write_case_provider(base=base, case=cases[0], case_root=clean_root)]
        def generate(case): return write_case_provider(base=base, case=case, case_root=cases_root / case["case_id"], clean_case_root=clean_root)
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = {pool.submit(generate, case): case["case_id"] for case in cases[1:]}
            for future in as_completed(futures): ready.append(future.result())
    ready.sort(key=lambda row: cases.index(next(case for case in cases if case["case_id"] == row["case_id"])))
    out = attempt / "AGGREGATES"; out.mkdir(parents=True, exist_ok=False)
    if len(ready) != 541 or not all(row["provider_ready"] for row in ready):
        raise SystemExit("provider generation did not close 541/541; staging preserved")
    summaries=[]; detail=[]; components=[]; provider_hashes=[]
    for case in cases:
        root=cases_root/case["case_id"]
        summary=json.loads((root/"03_EFFECT_VALIDATION/effect_validation_summary.json").read_text(encoding="utf-8"))
        summaries.append({key:value for key,value in summary.items() if key != "detail_rows"})
        with (root/"03_EFFECT_VALIDATION/effect_validation_detail.csv").open("r",encoding="utf-8-sig",newline="") as handle:
            for row in csv.DictReader(handle): detail.append({"case_id":case["case_id"],**row})
        generation=json.loads((root/"02_PROVIDERS/provider_generation_log.json").read_text(encoding="utf-8"))
        for ordinal,row in enumerate(generation.get("components",()),start=1):
            components.append({"case_id":case["case_id"],"component_index":ordinal,
                               "component":row.get("component"),"affected_source":row.get("affected_source"),
                               "affected_epoch_count":row.get("affected_epoch_count"),"status":row.get("status"),
                               "details_json":json.dumps(row.get("details") or {},sort_keys=True,separators=(",",":"))})
        index=json.loads((root/"02_PROVIDERS/provider_index.json").read_text(encoding="utf-8"))
        resolved = resolve_provider_index(root)
        for row in index["provider_files"]:
            actual_path = resolved[row["source"]]
            provider_hashes.append({
                "case_id":case["case_id"], "source":row["source"],
                "sha256":sha256_file(actual_path), "size_bytes":actual_path.stat().st_size,
                "semantic_sha256":row["semantic_sha256"], "storage_mode":row["storage_mode"],
                "pointer_target_case":row.get("pointer_case_id", ""),
                "pointer_target_source":row.get("pointer_source", ""),
                "resolved_path": str(normalize_promoted_resolved_path(
                    actual_path=actual_path, cases_root=cases_root, finalized=finalized,
                )),
            })
    ready_hash = write_identical_csvs(
        (out/"CANONICAL_BY2_PROVIDER_READY_MANIFEST.csv", out/"CANONICAL541_PROVIDER_READY_MANIFEST.csv", out/"PROVIDER_READY_MANIFEST.csv"), ready)
    effect_hash = write_identical_csvs(
        (out/"CANONICAL541_EFFECT_VALIDATION_RESULTS.csv", out/"EFFECT_VALIDATION_RESULT_TABLE.csv"), summaries)
    write_identical_csvs((out/"EFFECT_VALIDATION_DETAIL_TABLE.csv",), detail)
    write_identical_csvs((out/"COMPONENT_VALIDATION_TABLE.csv",), components)
    write_identical_csvs((out/"PROVIDER_SHA256_MANIFEST.csv",), provider_hashes)
    write_identical_csvs((out/"EFFECT_VALIDATION_FAILURES.csv",),
                         [row for row in summaries if str(row.get("passed")).lower() != "true"])
    report = {"provider_generation": len(ready), "effect_validation": sum(row["effect_validation_passed"] for row in ready),
              "provider_ready": sum(row["provider_ready"] for row in ready), "trace_open_count": 0, "raw_mutation": 0,
              "provider_sha_rows": len(provider_hashes),
              "provider_sha_closure": len(provider_hashes) == 541 * 8,
              "finalized_provider_root": str(finalized), "ready_manifest_sha256": ready_hash,
              "effect_result_sha256": effect_hash, "attempt_id": attempt_id,
              "code_freeze_commit": args.code_freeze_commit,
              "executable_sha256": sha256_file(executable),
              "resume_reconciled_from_finalized": resumed_finalized,
              "passed": len(ready) == 541 and len(provider_hashes) == 541 * 8 and all(row["provider_ready"] for row in ready)}
    (out / "PROVIDER_GATE.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (attempt / "PROMOTION_JOURNAL.json").write_text(json.dumps(report, indent=2, sort_keys=True)+"\n",encoding="utf-8")
    if not report["passed"]:
        raise SystemExit("provider aggregate gate failed; staging preserved")
    # Pointer rows are case-relative.  Cases and their aggregate gate are promoted
    # only after every 541/541 + 4,328-row closure check above has passed.
    if not resumed_finalized:
        os.replace(cases_root, finalized)
    if final_out.exists():
        if not final_out.is_dir() or any(final_out.iterdir()):
            raise SystemExit("partial/nonempty provider-ready root exists; staging preserved")
        final_out.rmdir()
    os.replace(out, final_out)
    validated = validate_provider_gate(
        stage_root=stage, provider_root=provider_root, case_manifest=manifest,
    )
    post_provider_raw = raw_checkpoint(paths, stage, "POST_PROVIDER")
    print(json.dumps({**report, "post_promotion_validation": validated,
                      "raw_checkpoints": {"PRE_PROVIDER": pre_provider_raw,
                                          "POST_PROVIDER": post_provider_raw}},
                     indent=2, sort_keys=True))


if __name__ == "__main__": main()
