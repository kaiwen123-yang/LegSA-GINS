#!/usr/bin/env python3
"""One matched full BY2O support/carrier pair for scalar-vs-vector LSIM semantics."""
import argparse
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import yaml
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts/paper_rebuild/carrier_phase")]
import continuous_heading_navigation as nr
from navigation_trial import clone_config


def prepare(a):
    original = nr.read(a.support_plan)
    template = next(r for r in original["runs"] if r["arm"] == "REPLACE_SUPPORT")
    payload = nr.checked(template["config"]).read_bytes()
    cfg = yaml.safe_load(payload)
    assert cfg["support_pose_mode"] == "REPLACE_SUPPORT"
    assert cfg["heading_source_policy"] == "configured"
    assert cfg.get("go2_body_velocity_discrepancy_mode", "off") == "off"
    assert cfg.get("support_pose_observed_axes", "body0_xy") == "body0_xy"
    old_binary = nr.read(a.legacy_plan)["binary"]
    assert old_binary["sha256"] == "c42f1609d98fe7d60e96b5e477420393acae3ae544075e48ea9cc28d39ebe327"
    nr.checked(old_binary)
    full = nr.read(a.full_plan)["runs"][0]["carrier"]
    for item in [template["carrier"], full, original["scenario_masks"], *template["providers"].values()]:
        nr.checked(item)
    # Current production diff is restricted to measurement metadata and its LSIM consumer.
    source_paths = ["cpp/legsa_v23_port_core/include/legsa_v23_port_core/source_aware/measurement_source.hpp",
                    "cpp/legsa_v23_port_core/src/source_aware/source_aware_policy.cpp",
                    "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp"]
    source_pins = [nr.pin(ROOT / x) for x in source_paths]
    binaries = {"LEGACY": Path(old_binary["path"]), "VECTOR": a.binary.resolve()}
    assert binaries["VECTOR"].is_file()
    a.output.mkdir(parents=True, exist_ok=False)
    runs = []
    scientific = None
    for arm, source in binaries.items():
        child = a.output / arm
        (child / "BINARY").mkdir(parents=True)
        binary = child / "BINARY/legsa_v23_port_core_demo"
        shutil.copy2(source, binary)
        rid = "BY2O__" + arm
        fields = dict(run_id=rid, run_label=rid, case_id=rid, outputpath=str(child / "NATIVE" / rid),
                      go2_body_velocity_discrepancy_mode="off", support_pose_observed_axes="body0_xy")
        content, changes = clone_config(payload, fields)
        actual = yaml.safe_load(content)
        science = {k: v for k, v in actual.items() if k not in ("run_id", "run_label", "case_id", "outputpath")}
        if scientific is None:
            scientific = science
        assert scientific == science
        for k, v in cfg.items():
            if k not in fields:
                assert actual[k] == v, k
        config = child / "CONFIGS" / (rid + ".yaml")
        config.parent.mkdir()
        config.write_bytes(content)
        run = dict(template, run_id=rid, arm=arm, config=nr.pin(config), template=template["config"], changes=changes)
        plan = dict(schema="vector_direction_sa_native_child.v1", runner=nr.pin(__file__), binary=nr.pin(binary),
                    runs=[run], sequences=original["sequences"], evaluator=original["evaluator"], aliases=original["aliases"],
                    scenario_masks=original["scenario_masks"], reference_online=False, native_budget=1, evaluator_budget=1)
        nr.emit(child / "PLAN.json", plan)
        runs.append(dict(arm=arm, child_plan=nr.pin(child / "PLAN.json"), binary=nr.pin(binary), run_id=rid))
    plan = dict(schema="vector_direction_sa_matched_support_pilot.v1", runner=nr.pin(__file__),
                support_plan=nr.pin(a.support_plan), full_plan=nr.pin(a.full_plan), legacy_plan=nr.pin(a.legacy_plan),
                source_pins=source_pins, runs=runs, sequences=original["sequences"],
                scenario_masks=original["scenario_masks"], carrier=template["carrier"], full_carrier=full,
                scientific_config_equal=True, scientific_difference="external 3D carrier declares scalar yaw std not applicable; only scalar-yaw LSIM std rules skip it",
                native_budget=2, evaluator_budget=2, reference_online=False,
                frozen_items=["actual ROLLING carrier vectors and full anisotropic covariance", "foot XY endpoints and SDK replacement timing", "all noise/thresholds/initialization/IMU", "common state, hard NIS, OIM and dependency replay"],
                interpretation="Mechanism and reference-relative single-window diagnostic; not independent truth, new frozen transfer or total-goal completion.",
                criterion="Confirm removal of coordinate-dependent scalar penalty, real common R/v/p effects, and report all fixed-window yaw/H/Up/tail/coverage. At least 5 percent whole-window heading improvement is a material relative heading signal; without a material navigation benefit do not claim the total goal achieved. No new parameter runs.")
    nr.emit(a.output / "PLAN.json", plan)
    print(json.dumps({"prepared": str(a.output), "plan_sha256": nr.digest(a.output / "PLAN.json"), "runs": runs}, indent=2))


def execute(a, kind):
    plan = nr.read(a.output / "PLAN.json")
    records = []
    for run in plan["runs"]:
        child_plan = nr.checked(run["child_plan"])
        args = SimpleNamespace(output=child_plan.parent, timeout=a.timeout)
        getattr(nr, kind)(args)
        terminal = child_plan.parent / ("ALL_NATIVE_SEALED.json" if kind == "native" else "EVALUATION_COMPLETE.json")
        records.append(dict(arm=run["arm"], terminal=nr.pin(terminal)))
    nr.emit(a.output / ("ALL_NATIVE_SEALED.json" if kind == "native" else "EVALUATION_COMPLETE.json"),
            dict(plan_sha256=nr.digest(a.output / "PLAN.json"), children=records, calls=len(records)))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["prepare", "native", "evaluate"])
    p.add_argument("--output", type=Path, required=True)
    for key in ["support-plan", "full-plan", "legacy-plan", "binary"]:
        p.add_argument("--" + key, type=Path)
    p.add_argument("--timeout", type=float, default=1200.)
    a = p.parse_args()
    a.output = a.output.resolve()
    if a.command == "prepare":
        prepare(a)
    else:
        execute(a, a.command)
