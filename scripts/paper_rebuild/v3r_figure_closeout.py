#!/usr/bin/env python3
"""Second V3-01-R continuation: frozen-table figures and visual-gated closeout.

No aggregate, provider, native or evaluator entrypoint is called. Old exports
remain in place until machine and actual visual review both pass. G writes use
the existing retry/verified-write adapters; no rename or deletion is required.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import yaml

from legsa_gins.paper_rebuild.protocol_v3.aggregate_recovery import (
    SCIENCE_FREEZE, aggregation_guard, verify_render)
from legsa_gins.paper_rebuild.protocol_v3.resume_storage import (
    Heartbeat, persist, persist_bytes, read_json, report_output_io, safe)
from legsa_gins.paper_rebuild.manifest import sha256_file

REVIEW_SHA = "f25d6f830e7743856c60d71d3c6293342b5e84d218b4e41c0005ad650143fc0d"
REPAIR = "76153ae374a100ee70f5b8b6bb2a9d03f7f7bc72"
MANIFESTS = ("07_AGGREGATE/AGGREGATE_MANIFEST.json",
             "07C_FAILURE_FAMILY_CONFIG/MANIFEST.json",
             "07D_CLASSIFICATION_PROVENANCE/MANIFEST.json")
CONTROL = "00_CONTROL/FIGURE_CLOSEOUT_SECOND_CONTINUATION"
CANDIDATE = "08_FIGURES/SECOND_CONTINUATION"


def now():
    return datetime.now(timezone.utc).isoformat()


def metadata(**values):
    return dict(utc=now(), data_mode="retained_results_figure_closeout",
                synthetic_data_used=False, semisynthetic_data_used=True,
                native_calls=0, evaluator_calls=0, aggregate_calls=0, **values)


def checked(root, pins):
    for name, expected in pins.items():
        path = safe(root / name)
        if root not in path.parents or sha256_file(path) != expected:
            raise RuntimeError("HARD_STOP_TABLE_OR_PRIOR_EVIDENCE_HASH_CHANGED: " + name)


def snapshot(root, control):
    if control.exists():
        raise FileExistsError("Preserve the existing second-continuation attempt")
    review_path = root / "09_HANDOFF/TABLE_REVIEW.json"
    if sha256_file(review_path) != REVIEW_SHA:
        raise RuntimeError("HARD_STOP_REVIEW_BASELINE_CHANGED")
    review = read_json(review_path)
    checked(root, review["source_sha256"])
    pins = dict(review["source_sha256"])
    for name in MANIFESTS:
        manifest = read_json(root / name)
        for child, digest in manifest["files_sha256"].items():
            pins[str(Path(name).parent / child)] = digest
    checked(root, pins)
    csv_count = sum(name.endswith(".csv") for name in pins)
    if csv_count != 59 or len(pins) != 65:
        raise RuntimeError("HARD_STOP_REVIEWED_TABLE_INVENTORY")
    # These are immutable historical gate receipts, not operational views.
    immutable = {"09_HANDOFF/TABLE_REVIEW.json": REVIEW_SHA}
    recovery = root / "00_CONTROL/AGGREGATE_RECOVERY"
    for path in sorted(recovery.glob("*HARD_STOP.json")):
        immutable[str(path.relative_to(root))] = sha256_file(path)
    for name in ("FINAL_RUN_RECORDS.json", "FINAL_EVALUATION_RECORDS.json", "STATUS.json"):
        immutable[name] = sha256_file(root / name)
    history = [root / name for name in ("00_CONTROL/STATE.json", "00_CONTROL/PROGRESS.txt",
               "00_CONTROL/SUMMARY.txt", "09_HANDOFF/VISUAL_REVIEW.json")]
    history += sorted(path for path in (root / "08_FIGURES").rglob("*") if path.is_file())
    for name in ("00_CONTROL/SUMMARY.json",):
        if (root / name).exists():
            history.append(root / name)
    history_pins = {}
    for source in history:
        relative = source.relative_to(root)
        payload = safe(source).read_bytes()
        persist_bytes(control / "PREVIOUS" / relative, payload)
        history_pins[str(relative)] = sha256_file(source)
    result = metadata(status="PASS_REVIEWED_TABLE_BASELINE", science_freeze=SCIENCE_FREEZE,
                      aggregation_repair_commit=REPAIR, csv_count=csv_count,
                      manifest_bound_file_count=62, files_sha256=pins,
                      immutable_sha256=immutable, previous_files_sha256=history_pins)
    persist(control / "BASELINE.json", result)
    return result


def unchanged(root, control):
    baseline = read_json(control / "BASELINE.json")
    checked(root, baseline["files_sha256"])
    checked(root, baseline["immutable_sha256"])
    checked(control / "PREVIOUS", baseline["previous_files_sha256"])
    return baseline


def render(roots, root, control, commit):
    from legsa_gins.paper_rebuild.protocol_v3 import figures
    if (control / "HARD_STOP.json").exists() or (root / CANDIDATE).exists():
        raise RuntimeError("HARD_STOP_NO_AUTOMATIC_FIGURE_RETRY")
    unchanged(root, control)
    with aggregation_guard(roots["raw_root"], roots["code_root"]) as guard:
        with report_output_io(root):
            writer = figures.write_json

            def stop_failed_figure(path, entry):
                writer(path, entry)
                if Path(path).name == "FIGURE_MANIFEST.json" and entry.get("status") != "RENDERED":
                    raise RuntimeError("HARD_STOP_FIGURE_QA: " + entry.get("figure_id", "UNKNOWN")
                                       + ": " + entry.get("reason", ""))

            figures.write_json = stop_failed_figure
            try:
                result = figures.render(root, roots=roots, code_freeze=SCIENCE_FREEZE,
                                        output=root / CANDIDATE)
            finally:
                figures.write_json = writer
        verify_render(root, result, figure_root=root / CANDIDATE)
        baseline = unchanged(root, control)
    receipt = metadata(status="PASS_TEN_FIGURES_MACHINE_QA_TABLES_UNCHANGED",
                       figure_repair_commit=commit, access_guard=guard,
                       csv_count=baseline["csv_count"], files_sha256=baseline["files_sha256"],
                       baseline_sha256=sha256_file(control / "BASELINE.json"),
                       render_manifest_sha256=sha256_file(root / CANDIDATE / "RENDER_MANIFEST.json"),
                       qa_checks=sum(len(entry["qa"]) for entry in result["figures"]),
                       exports=sum(len(entry["output_sha256"]) for entry in result["figures"]))
    persist(control / "MACHINE_QA_AND_TABLE_IDENTITY.json", receipt)
    return receipt


def complete(roots, root, control, commit):
    if (control / "HARD_STOP.json").exists() or (root / "00_CONTROL/DONE.json").exists():
        raise RuntimeError("Preserve an existing stop or DONE")
    baseline = unchanged(root, control)
    machine = read_json(control / "MACHINE_QA_AND_TABLE_IDENTITY.json")
    if (machine.get("status") != "PASS_TEN_FIGURES_MACHINE_QA_TABLES_UNCHANGED"
            or machine.get("baseline_sha256") != sha256_file(control / "BASELINE.json")
            or machine.get("files_sha256") != baseline["files_sha256"]):
        raise RuntimeError("HARD_STOP_MACHINE_TABLE_RECEIPT_BINDING")
    visual = read_json(control / "VISUAL_REVIEW.json")
    render_path = root / CANDIDATE / "RENDER_MANIFEST.json"
    rendered = read_json(render_path)
    expected = {entry["figure_id"] for entry in rendered["figures"]}
    if (machine["figure_repair_commit"] != commit or visual.get("status") != "PASS"
            or visual.get("actual_raster_review") is not True
            or set(visual.get("reviewed_figures", [])) != expected
            or len(visual["reviewed_figures"]) != 10
            or any(visual.get("figure_results", {}).get(key, {}).get("status") != "PASS" for key in expected)
            or visual.get("render_manifest_sha256") != sha256_file(render_path)
            or machine["render_manifest_sha256"] != sha256_file(render_path)):
        raise RuntimeError("HARD_STOP_ACTUAL_VISUAL_QA_REQUIRED")
    with aggregation_guard(roots["raw_root"], roots["code_root"]) as guard:
        verify_render(root, rendered, figure_root=root / CANDIDATE)
        # Old canonical files must still equal the preserved previous version.
        checked(root, {name: digest for name, digest in baseline["previous_files_sha256"].items()
                       if name.startswith("08_FIGURES/") or name == "09_HANDOFF/VISUAL_REVIEW.json"})
        expected_files = {"RENDER_MANIFEST.json", "CAPTIONS.md", "FIGURE_INDEX.md"}
        expected_files.update(key + "/" + key + "." + ext for key in expected for ext in ("png", "pdf", "svg"))
        expected_files.update(key + "/FIGURE_MANIFEST.json" for key in expected)
        sources = sorted(path for path in (root / CANDIDATE).rglob("*") if path.is_file())
        if {str(path.relative_to(root / CANDIDATE)) for path in sources} != expected_files:
            raise RuntimeError("HARD_STOP_FIGURE_FILE_INVENTORY")
        for source in sources:
            destination = root / "08_FIGURES" / source.relative_to(root / CANDIDATE)
            Heartbeat._replace_operational(destination, source.read_bytes())
            if sha256_file(destination) != sha256_file(source):
                raise RuntimeError("HARD_STOP_FIGURE_PUBLICATION_HASH")
        Heartbeat._replace_operational(root / "09_HANDOFF/VISUAL_REVIEW.json",
                                      (control / "VISUAL_REVIEW.json").read_bytes())
        verify_render(root, rendered)
        unchanged(root, control)
        done = metadata(status="DONE_MATRIX_AGGREGATE_FIGURES_MACHINE_QA", science_freeze=SCIENCE_FREEZE,
                        aggregation_repair_commit=REPAIR, figure_repair_commit=commit,
                        native_terminal_count=6468, evaluator_terminal_count=12936, completed_batches=279,
                        native_calls_in_recovery=0, evaluator_calls_in_recovery=0,
                        aggregate_manifest_sha256=sha256_file(root / MANIFESTS[0]),
                        full_ablation_failure_appendix_sha256=sha256_file(root / MANIFESTS[1]),
                        render_manifest_sha256=sha256_file(root / "08_FIGURES/RENDER_MANIFEST.json"),
                        visual_review_status="PASS", visual_review_sha256=sha256_file(root / "09_HANDOFF/VISUAL_REVIEW.json"),
                        table_hashes_unchanged=True, csv_count=59, original_hard_stop_preserved=True,
                        table_identity_receipt_sha256=sha256_file(control / "MACHINE_QA_AND_TABLE_IDENTITY.json"),
                        package_status="PENDING", access_guard=guard)
        Heartbeat._replace_operational(root / "00_CONTROL/SUMMARY.json", (json.dumps(done, indent=2) + "\n").encode())
        Heartbeat._replace_operational(root / "00_CONTROL/SUMMARY.txt", (
            "DONE " + done["utc"] + "\n10/10 machine and actual visual QA; 30 exports.\n"
            "59 CSV and 62 manifest-bound files unchanged. No native, evaluator or aggregate calls.\n"
            "Original hard stops and previous figures/visual review preserved. Handoff pending.\n"
            + json.dumps(done, indent=2) + "\n").encode())
        state = read_json(root / "00_CONTROL/STATE.json")
        state.update(phase="DONE", status="DONE", updated_utc=done["utc"], visual_review_status="PASS",
                     second_continuation_completion=done, latest_hard_stop=None, package_status="PENDING")
        Heartbeat._replace_operational(root / "00_CONTROL/STATE.json", (json.dumps(state, indent=2) + "\n").encode())
        Heartbeat._replace_operational(root / "00_CONTROL/PROGRESS.txt", (
            "phase=DONE status=DONE native=6468/6468 evaluator_terminal_slots=12936/12936 archived_batches=279/279\n"
            "machine_QA=PASS visual_QA=PASS tables=UNCHANGED native/evaluator/aggregate_calls=0\n"
            "DONE_UTC=" + done["utc"] + "\n").encode())
        persist(control / "COMPLETION.json", done)
        persist(root / "00_CONTROL/DONE.json", done)
    return done


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-config", type=Path, required=True)
    parser.add_argument("--phase", choices=("baseline", "render", "complete"), required=True)
    parser.add_argument("--figure-repair-commit")
    args = parser.parse_args()
    roots = yaml.safe_load(args.local_config.read_text())["paths"]
    root = safe(Path(roots["clean_root"]) / "stages/CLEAN8_PROTOCOL_V3")
    control = root / CONTROL
    if not os.path.ismount("/mnt/g") or Path("/mnt/g") not in root.parents:
        raise RuntimeError("Mounted G evidence root required")
    cache = safe(roots["protocol_v3_scratch"]) / "AGGREGATE_RECOVERY_CACHE"
    for key, folder in (("MPLCONFIGDIR", "matplotlib"), ("XDG_CACHE_HOME", "xdg"), ("TMPDIR", "tmp")):
        (cache / folder).mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(cache / folder)
    os.environ["MPLBACKEND"] = "Agg"
    if args.phase != "baseline" and not args.figure_repair_commit:
        parser.error("--figure-repair-commit is required")
    try:
        result = snapshot(root, control) if args.phase == "baseline" else globals()[
            "render" if args.phase == "render" else "complete"](roots, root, control, args.figure_repair_commit)
    except Exception as exc:
        if control.exists() and not (control / "HARD_STOP.json").exists():
            persist(control / "HARD_STOP.json", metadata(status="HARD_STOP", phase=args.phase,
                                                        error=str(exc), automatic_retry=False))
        if (root / "00_CONTROL/STATE.json").exists():
            state = read_json(root / "00_CONTROL/STATE.json")
            state.update(phase="HARD_STOP", status="HARD_STOP", updated_utc=now(),
                         second_continuation_hard_stop=str(control / "HARD_STOP.json"))
            Heartbeat._replace_operational(root / "00_CONTROL/STATE.json", (json.dumps(state, indent=2) + "\n").encode())
        raise
    print(json.dumps({key: value for key, value in result.items() if key not in
                      ("files_sha256", "previous_files_sha256", "immutable_sha256")}, indent=2))


if __name__ == "__main__":
    main()
