#!/usr/bin/env python3
"""Capture exact pre-carrier priors once with the unchanged BY2O VECTOR experiment."""
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
    previous = nr.read(a.previous_plan)
    old = previous["runs"][0]
    assert old["arm"] == "VECTOR" and old["sequence_id"] == "BY2O"
    payload = nr.checked(old["config"]).read_bytes()
    cfg = yaml.safe_load(payload)
    assert cfg["heading_source_policy"] == "configured"
    assert cfg["support_pose_mode"] == "REPLACE_SUPPORT"
    assert cfg["support_pose_observed_axes"] == "body0_xy"
    for item in [old["carrier"], *old["providers"].values()]:
        nr.checked(item)
    a.output.mkdir(parents=True, exist_ok=False)
    (a.output / "BINARY").mkdir()
    binary = a.output / "BINARY/legsa_v23_port_core_demo"
    shutil.copy2(a.binary, binary)
    rid = "BY2O__VECTOR_PRIOR"
    fields = dict(run_id=rid, run_label=rid, case_id=rid, outputpath=str(a.output / "NATIVE" / rid))
    content, changes = clone_config(payload, fields)
    actual = yaml.safe_load(content)
    assert {k:v for k,v in actual.items() if k not in fields} == {k:v for k,v in cfg.items() if k not in fields}
    (a.output / "CONFIGS").mkdir()
    config = a.output / "CONFIGS" / (rid + ".yaml")
    config.write_bytes(content)
    run = dict(old, run_id=rid, arm="VECTOR_PRIOR", config=nr.pin(config), changes=changes)
    sources = [nr.pin(ROOT / f) for f in a.source]
    plan = dict(schema="partial_direction_exact_prior.v1", runner=nr.pin(__file__),
                previous_plan=nr.pin(a.previous_plan), binary=nr.pin(binary), source_pins=sources,
                runs=[run], sequences=previous["sequences"], evaluator=previous["evaluator"],
                aliases=previous["aliases"], scenario_masks=previous["scenario_masks"],
                reference_online=False, native_budget=1, evaluator_budget=0,
                scientific_change="none; log exact-event pre-carrier common-state prior only",
                decision="Read all 117 partial and 41 two-component covers with exact prior; domain overlap is not posterior mode probability. Do not reuse RP or foot as an independent prior.",
                required_comparison="All saved numeric state/bias/STD values match the previous VECTOR run. No reference/evaluator, no noise or gate change.")
    nr.emit(a.output / "PLAN.json", plan)
    print(json.dumps({"prepared":str(a.output),"binary":plan["binary"],"plan_sha256":nr.digest(a.output / "PLAN.json")}))


def compare(a):
    plan = nr.read(a.output / "PLAN.json")
    oldplan = nr.read(nr.checked(plan["previous_plan"]))
    oldroot = Path(plan["previous_plan"]["path"]).parent / "NATIVE" / oldplan["runs"][0]["run_id"]
    newroot = a.output / "NATIVE" / plan["runs"][0]["run_id"]
    native = nr.read(newroot / "RESULT.json")
    assert native["status"] == "COMPLETED" and native["online_reference_opens"] == 0
    names = ["LegSA_PORT_NAV.nav", "KF_GINS_Navresult.nav", "KF_GINS_STD.txt", "KF_GINS_IMU_ERR.txt", "LegSA_PORT_STD.csv"]
    pairs = []
    for name in names:
        before, after = oldroot / name, newroot / name
        same = before.read_bytes() == after.read_bytes()
        pairs.append(dict(file=name, before=nr.pin(before), after=nr.pin(after), byte_equal=same))
    result = dict(status="PASS" if all(x["byte_equal"] for x in pairs) else "STATE_PARITY_REQUIRES_INSPECTION",
                  files=pairs, native_calls=1, evaluator_calls=0, online_reference_opens=0,
                  plan_sha256=nr.digest(a.output / "PLAN.json"))
    nr.emit(a.output / "NUMERICAL_PARITY.json", result)
    print(json.dumps({"status":result["status"],"files":[{"file":x["file"],"byte_equal":x["byte_equal"]} for x in pairs]}))


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("command",choices=["prepare","native","compare"])
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--previous-plan",type=Path)
    p.add_argument("--binary",type=Path)
    p.add_argument("--source",action="append",default=[])
    p.add_argument("--timeout",type=float,default=1200.)
    a=p.parse_args();a.output=a.output.resolve()
    if a.command=="prepare":prepare(a)
    elif a.command=="native":nr.native(SimpleNamespace(output=a.output,timeout=a.timeout))
    else:compare(a)
