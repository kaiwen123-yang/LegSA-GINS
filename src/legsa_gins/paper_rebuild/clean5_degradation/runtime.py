"""P-07 frozen-binary execution; no evaluator or raw reference import/call."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import yaml

from ..clean5_calibrated.runtime import patch_calibrated_config
from ..clean5_parity.runtime import bind_config, check_counters, scheduled_gnss_indices
from ..clean5_parity.scheduling import _provider, select_last_nearest
from ..clean5_sequence.solver_runner import audit_solver_openat
from ..clean5_sequence.solver_validation import validate_run_outputs, CONFIG_FLAG_TO_MANIFEST
from ..clean5_sequence.io_audit import audited_open_records, write_scope_audit
from ..manifest import sha256_file
from ..subprocess_guard import run_process_group
from .common import FLAGS, pinned, resolve, resolved_pins, read_csv, write_json, seal_roots
from .providers import build_base, generate_case


def selection(contract, reg):
    cases = read_csv(pinned(contract["sources"]["case_registry"], reg))
    selected = contract["selection"]["selected_case_ids"]
    lookup = {r["case_id"]: r for r in cases}
    if len(lookup) != 541 or len(selected) != 61 or len(set(selected)) != 61:
        raise ValueError("Case registry/selection identity mismatch")
    mechanically = [lookup["C00_clean_normal"]]
    for type_id in sorted({r["degradation_type_id"] for r in cases} - {"CLEAN"}):
        group = [r for r in cases if r["degradation_type_id"] == type_id]
        if len({r["degradation_parameters_json"] for r in group}) != 1:
            raise ValueError("Preregistered single-severity premise changed")
        mechanically.append(min(group, key=lambda r: int(r["seed_index"].split("_")[-1])))
    if [r["case_id"] for r in mechanically] != selected:
        raise ValueError("Selection differs from frozen mechanical rule")
    runs = read_csv(pinned(contract["sources"]["unique_run_registry"], reg))
    runs = [r for r in runs if r["case_id"] in selected]
    expected = {(c, m) for c in selected for m in contract["runtime"]["profiles"]}
    if len(runs) != 671 or {(r["case_id"], r["method_id"]) for r in runs} != expected:
        raise ValueError("All eleven unique profiles are required for every case")
    return mechanically, sorted(runs, key=lambda r: int(r["run_order"]))


def checkpoint(contract, reg, stage, name, resolution):
    """Require an explicit human resolution; never infer permission from time."""
    if resolution.get("mode") not in ("metadata_for_forbidden", "independent_hash_all"):
        raise ValueError("Raw checkpoint scope requires explicit human resolution")
    if not resolution.get("human_instruction"):
        raise ValueError("Missing literal human checkpoint instruction")
    entries = [r for r in read_csv(pinned(contract["sources"]["raw_lock"], reg)) if r["dataset"] == "BY2"]
    if len(entries) != 22:
        raise ValueError("Raw checkpoint must cover exactly 22 BY2 members")
    if resolution["mode"] == "independent_hash_all":
        output = stage / "01_CHECKPOINTS" / (name + ".json")
        output.parent.mkdir(parents=True, exist_ok=True)
        log = output.with_suffix('.strace')
        program = ("import sys,json;from legsa_gins.paper_rebuild.clean5_degradation.checkpoint_process import hash_members;"
                   "hash_members(sys.argv[1],sys.argv[2],sys.argv[3],json.loads(sys.argv[4]))")
        command = ["env", "PYTHONDONTWRITEBYTECODE=1", "PYTHONPATH=" + str(reg.code_root / "src"),
                   "strace", "-f", "-qq", "-yy", "-s", "4096", "-e", "trace=openat", "-o", str(log),
                   sys.executable, "-c", program, str(pinned(contract["sources"]["raw_lock"], reg)),
                   str(reg.raw_root), str(output), json.dumps(resolution, ensure_ascii=False)]
        completed = run_process_group(command, cwd=reg.code_root, timeout_seconds=1800,
                                     timeout_message="Raw checkpoint timeout", launch_failure_message="Raw checkpoint launch failure")
        opened = audited_open_records(log, reg.code_root)
        raw = [r for r in opened if reg.raw_root in Path(r["path"]).parents]
        expected = {str(reg.raw_root / r['relative_path']) for r in entries}
        scope = write_scope_audit(opened, raw_root=reg.raw_root, clean_root=reg.clean_root,
                                 allowed_write_roots=[output.parent])
        audit = {"passed": completed.returncode == 0 and len(raw) == 22
                 and {r['path'] for r in raw} == expected and scope['pass']
                 and all(r['return_code'] >= 0 and 'O_RDONLY' in r['flags'] for r in raw),
                 "raw_open_count": len(raw), "scope": scope, "resolution": resolution,
                 "exception_role": "HUMAN_AUTHORIZED_HASH_ONLY_CHECKPOINT_NOT_SOLVER_OR_PROVIDER",
                 "strace_sha256": sha256_file(log)}
        write_json(output.with_name(name + '_OPEN_AUDIT.json'), audit)
        payload = json.loads(output.read_text()) if output.is_file() else {}
        if not audit['passed'] or payload.get('passed_count') != 22:
            raise ValueError('Independent raw checkpoint failed: ' + completed.stderr[-1000:])
        return payload
    rows = []
    for entry in entries:
        source = reg.raw_root / entry["relative_path"]
        if source.is_symlink() or not source.is_file():
            raise ValueError("Missing/symlink immutable raw member")
        forbidden = source.name.startswith("trace_") or source.suffix in (".bag", ".fpl")
        stat = source.stat()
        digest = None if forbidden else sha256_file(source)
        passed = stat.st_size == int(entry["size_bytes"])
        passed &= (stat.st_mtime_ns == int(entry["mtime_ns"])) if forbidden else digest == entry["sha256"]
        rows.append({"relative_path": entry["relative_path"], "expected_sha256": entry["sha256"],
                     "actual_sha256": digest, "verification": "SEALED_HASH_PLUS_SIZE_MTIME_ONLY" if forbidden else "LIVE_SHA256",
                     "passed": bool(passed)})
    payload = {"members": rows, "member_count": 22, "passed_count": sum(r["passed"] for r in rows),
               "live_hash_count": sum(r["actual_sha256"] is not None for r in rows), "resolution": resolution,
               "trace_open_count": 0, "bag_open_count": 0, "fpl_open_count": 0}
    write_json(stage / "01_CHECKPOINTS" / (name + ".json"), payload)
    if payload["passed_count"] != 22:
        raise ValueError("Raw checkpoint mismatch")
    return payload


def generate_providers(contract, reg, stage, code_commit, contract_hash):
    """Reference-free provider subprocess; raw checkpoints occur in its parent."""
    cases, _ = selection(contract, reg)
    raw_hashes = {r['relative_path']: r['sha256'] for r in read_csv(pinned(contract['sources']['raw_lock'], reg))
                  if r['dataset'] == 'BY2'}
    if len(raw_hashes) != 22:
        raise ValueError('Provider lineage requires all22 locked raw member hashes')
    base = build_base(resolved_pins(contract["providers"]["roles"], reg),
                      auxiliary_roles=resolved_pins(contract["providers"]["auxiliary_roles"], reg),
                      base_time_s=contract["evaluation"]["base_time"], raw_input_hashes=raw_hashes)
    mappings = {m["case_id"]: m for m in contract["providers"]["mapping"]}
    bundles = {}
    for case in cases:
        mapping = resolved_pins(mappings[case["case_id"]], reg)
        mapping["equivalence_rule"] = contract["providers"]["semantic_evidence"]["equivalence_rule"]
        bundles[case["case_id"]] = generate_case(base, case, mapping, stage / "02_PROVIDERS",
                                                 code_commit=code_commit, config_hash=contract_hash)
        print("PROVIDER", case["case_id"], flush=True)
    write_json(stage / "02_PROVIDERS" / "PROVIDER_BUNDLES.json", bundles)


def prepare(contract, reg, stage, code_commit, resolution, local_config, contract_path):
    if stage.exists():
        raise FileExistsError("P-07 stage already exists; never overwrite/retry preparation")
    # Verify every preregistered non-reference scientific pin before generation.
    cases, runs = selection(contract, reg)
    for value in contract["sources"].values():
        for spec in value if isinstance(value, list) else [value]:
            pinned(spec, reg)
    pinned(contract["runtime"]["executable"], reg)
    pinned(contract["runtime"]["model"], reg)
    for row in runs:
        source = Path(row['runtime_config_path'])
        if source.is_symlink() or sha256_file(source) != row['runtime_config_file_hash']:
            raise ValueError('Selected original runtime configuration failed preregistered pin')
        cfg = yaml.safe_load(source.read_text())
        if cfg['run_id'] != row['run_id'] or cfg['case_id'] != row['case_id']:
            raise ValueError('Selected configuration registry identity mismatch')
    if (not resolution or not resolution.get("human_instruction")
            or resolution.get('mode') not in ('metadata_for_forbidden', 'independent_hash_all')):
        raise ValueError("Checkpoint scope unresolved; no provider generation")
    stage.mkdir(parents=True, exist_ok=False)
    checkpoint(contract, reg, stage, "BEFORE_PROVIDER", resolution)
    log = stage / "01_CHECKPOINTS/PROVIDER_OPENAT.strace"
    # Literal program, values passed as argv; never interpolate paths into code.
    program = ("import sys,yaml;from pathlib import Path;"
               "from legsa_gins.paper_rebuild.clean5_degradation.common import registry;"
               "from legsa_gins.paper_rebuild.clean5_degradation.runtime import generate_providers;"
               "generate_providers(yaml.safe_load(Path(sys.argv[1]).read_text()),registry(sys.argv[2]),"
               "Path(sys.argv[3]),sys.argv[4],sys.argv[5])")
    command = ["env", "PYTHONDONTWRITEBYTECODE=1", "OMP_NUM_THREADS=1", "OPENBLAS_NUM_THREADS=1",
               "PYTHONPATH=" + str(reg.code_root / "src"), "strace", "-f", "-qq", "-yy", "-s", "4096",
               "-e", "trace=openat", "-o", str(log), sys.executable, "-c", program,
               str(contract_path), str(local_config), str(stage), code_commit, sha256_file(contract_path)]
    completed = run_process_group(command, cwd=reg.code_root, timeout_seconds=1800,
        timeout_message="P07 provider timeout; no retry", launch_failure_message="P07 provider launch failure")
    (stage / "01_CHECKPOINTS/PROVIDER_STDOUT.log").write_text(completed.stdout)
    (stage / "01_CHECKPOINTS/PROVIDER_STDERR.log").write_text(completed.stderr)
    opened = audited_open_records(log, reg.code_root)
    forbidden = [r for r in opened if Path(r["path"]).name.startswith("trace_")
                 or Path(r["path"]).suffix in (".bag", ".fpl")]
    raw = [r for r in opened if reg.raw_root in Path(r["path"]).parents]
    scope = write_scope_audit(opened, raw_root=reg.raw_root, clean_root=reg.clean_root,
                              allowed_write_roots=[stage / "02_PROVIDERS"])
    audit = {"passed": completed.returncode == 0 and not forbidden and not raw and scope["pass"],
             "forbidden_open_count": len(forbidden), "raw_open_count": len(raw), "write_scope": scope,
             "exit_code": completed.returncode, "strace_sha256": sha256_file(log)}
    write_json(stage / "01_CHECKPOINTS/PROVIDER_STRACE_AUDIT.json", audit)
    if not audit["passed"]:
        raise RuntimeError("Provider generation/audit failed: " + completed.stderr[-2000:])
    bundles = json.loads((stage / "02_PROVIDERS/PROVIDER_BUNDLES.json").read_text())
    checkpoint(contract, reg, stage, "AFTER_PROVIDER", resolution)
    seal_roots(stage, ["02_PROVIDERS"], "04_SEAL/PROVIDER_SEAL.json",
               {"code_commit": code_commit, "case_count": 61, "data_mode": "real_base_controlled_degradation"})
    return runs, bundles


def expected_counts(config, gnss, imu):
    if gnss.ndim != 2 or gnss.shape[1] != 18 or not np.isfinite(gnss).all():
        raise ValueError("Nonfinite/non-18-column provider")
    if not np.isin(gnss[:, 15:18], [0, 1]).all():
        raise ValueError("Invalid GNSS validity bits")
    ids, schedule = scheduled_gnss_indices(gnss[:, 0], imu[:, 0], config["starttime"], config["endtime"])
    selected = gnss[ids]
    calls = selected[np.any(selected[:, 15:18] == 1, axis=1)]
    result = {**schedule, "eligible_rows": len(ids),
              "position_update_count": int(selected[:, 15].sum()),
              "receiver_velocity_update_count": int(selected[:, 16].sum()) if config["enable_receiver_velocity"] else 0,
              "dual_yaw_attempt_count": int(selected[:, 17].sum()) if config["enable_dual_yaw"] else 0,
              "source": "Frozen C++ scheduling replay on input timestamps and faulted GNSS18 validity bits",
              "source_output_used": False, "reference_used": False}
    result["gnss_call_count"] = len(calls)
    auxiliary = {}
    for module in ("RD", "RP", "HV"):
        provider = _provider(module, config)
        selected_count = static_pass = 0
        if provider["enabled"] and provider["solver_enabled"]:
            for instant in calls[:, 0]:
                index = select_last_nearest(provider["times"], instant, provider["tolerance"], provider["eligible"])
                if index is not None:
                    selected_count += 1
                    static_pass += int(provider["static"][index])
        auxiliary[module] = {"selected_count": selected_count, "static_pass_count": static_pass,
                             "static_reject_count": selected_count - static_pass,
                             "final_acceptance": "STATE_DEPENDENT" if module == "RD" and not config["enable_source_aware"] else "STATIC_GATE_EXACT"}
    result["auxiliary"] = auxiliary
    return result


def check_auxiliary(native, config, expected):
    failures = []
    actual = {}
    yaw_keys = ('dual_yaw_accepted_count', 'yaw_NORMAL', 'yaw_DOWNWEIGHT', 'yaw_REJECT')
    yaw = [native.get(key) for key in yaw_keys]
    if any(not isinstance(value, int) or value < 0 for value in yaw):
        failures.append('yaw_missing_or_invalid_terminal_count')
    elif (yaw[0] != yaw[1] + yaw[2] or sum(yaw[1:]) != expected['dual_yaw_attempt_count']
          or yaw[0] > expected['dual_yaw_attempt_count']):
        failures.append('yaw_terminal_partition_closure')
    keys = {"RD": ("raw_doppler_update_count", "raw_doppler_reject_count"),
            "RP": ("go2_attitude_weak_prior_update_count", "go2_attitude_weak_prior_reject_count"),
            "HV": ("go2_velocity_prior_update_count", "go2_velocity_prior_reject_count")}
    if config["source_aware_reject_extreme"]:
        raise ValueError("Frozen nonrejecting SA policy changed")
    for module, (update_key, reject_key) in keys.items():
        update, reject = native.get(update_key), native.get(reject_key)
        predicted = expected["auxiliary"][module]
        actual[module] = {"updates": update, "rejects": reject}
        if not isinstance(update, int) or not isinstance(reject, int):
            failures.append(module + "_missing_native_count")
            continue
        if update + reject != predicted["selected_count"] or reject < predicted["static_reject_count"] or not 0 <= update <= predicted["static_pass_count"]:
            failures.append(module + "_selection_closure")
        if predicted["final_acceptance"] == "STATIC_GATE_EXACT" and update != predicted["static_pass_count"]:
            failures.append(module + "_static_acceptance")
    sa = native.get("source_aware_evaluation_count")
    changed = native.get("source_aware_weight_changed_count")
    contribution = 0
    if config["enable_source_aware"]:
        terms = (("receiver_position", expected["position_update_count"], True),
                 ("receiver_velocity", expected["receiver_velocity_update_count"], True),
                 ("raw_doppler_velocity", expected["auxiliary"]["RD"]["static_pass_count"], True),
                 ("go2_attitude_roll_pitch", expected["auxiliary"]["RP"]["static_pass_count"], config["go2_attitude_prior_sourceaware"]),
                 ("go2_horizontal_velocity", expected["auxiliary"]["HV"]["static_pass_count"], config["go2_horizontal_velocity_prior_source_aware_enabled"]),
                 ("dual_antenna_yaw", native.get("dual_yaw_accepted_count") if isinstance(native.get("dual_yaw_accepted_count"), int) else 0, True))
        contribution = sum(count for source, count, enabled in terms
                           if enabled and config["source_aware_" + source + "_enabled"])
    if sa != contribution or not isinstance(changed, int) or not 0 <= changed <= contribution:
        failures.append("SA_source_contribution_closure")
    return {"pass": not failures, "failures": failures, "actual": actual,
            "source_aware_expected_from_terminal_yaw_acceptance": contribution,
            "source_aware_actual": sa, "source_aware_changed_actual": changed}


def validate_identity(native, config, source, bundle):
    expected = {key: config[key] for key in ('stage_id', 'protocol_id', 'case_id', 'run_id', 'data_mode', 'algorithm_id')}
    expected.update(phase=config['stage_id'], port_role=config['runtime_role'], clean_final_v23_parity_mode=True,
                    yaw_scheme_C_enabled=str(source['scheme_c']).lower() == 'true', go2_body_state_not_truth=True)
    expected.update({native_key: config[key] for key, native_key in CONFIG_FLAG_TO_MANIFEST.items()})
    expected.update({key: False for key in ('go2_position_truth_claim', 'go2_velocity_truth_claim',
                                           'go2_yaw_truth_claim', 'go2_contact_truth_claim')})
    mismatches = [key for key, value in expected.items()
                  if type(native.get(key)) is not type(value) or native.get(key) != value]
    if config['run_id'] != source['run_id'] or config['case_id'] != source['case_id']:
        mismatches.append('registry_case_run_identity')
    source_flags = {'enable_dual_yaw': 'dual_yaw', 'enable_receiver_velocity': 'receiver_velocity',
                    'enable_raw_doppler': 'raw_doppler', 'enable_source_aware': 'source_aware',
                    'enable_go2_roll_pitch_prior': 'go2_rp', 'enable_go2_horizontal_velocity_prior': 'go2_hv'}
    for key, field in source_flags.items():
        if config[key] is not (str(source[field]).lower() == 'true'):
            mismatches.append('registry_profile_' + key)
    roles = {'propagation_imu': ('imupath', 'source_backed_propagation'),
             'gnss_position_receiver_velocity_dual_yaw': ('gnsspath', 'validity_gated_measurements')}
    for flag, role, key, purpose in (
        ('enable_raw_doppler', 'raw_doppler_velocity', 'raw_doppler_factor_path', 'source_backed_auxiliary_velocity'),
        ('enable_go2_roll_pitch_prior', 'go2_roll_pitch_weak_prior', 'go2_attitude_prior_path', 'weak_prior_not_truth'),
        ('enable_go2_horizontal_velocity_prior', 'go2_horizontal_velocity_weak_prior', 'go2_horizontal_velocity_prior_path', 'horizontal_weak_prior_not_truth')):
        if config[flag]:
            roles[role] = (key, purpose)
    paths = native.get('actual_solver_input_paths')
    purposes = native.get('actual_solver_input_roles')
    if not isinstance(paths, dict) or not isinstance(purposes, dict) or set(paths) != set(roles) or set(purposes) != set(roles):
        mismatches.append('native_input_role_set')
    else:
        for role, (key, purpose) in roles.items():
            if paths[role] != config[key] or paths[role] != bundle['providers'][key]['path'] or purposes[role] != purpose:
                mismatches.append('native_input_' + role)
    if mismatches:
        raise ValueError('Native identity/input mismatch: ' + ','.join(mismatches))
    return {'passed': True, 'expected_identity': expected, 'actual_solver_input_paths': paths,
            'actual_solver_input_roles': purposes, 'source_registry_run_id': source['run_id']}


def validate_input_opens(log, expected_paths, reg, root, config_path):
    opened = audited_open_records(log, reg.code_root)
    expected = set(expected_paths.values())
    counts = {role: sum(r['path'] == path and r['return_code'] >= 0 and 'O_RDONLY' in r['flags'] for r in opened)
              for role, path in expected_paths.items()}
    extra = sorted({r['path'] for r in opened if reg.clean_root in Path(r['path']).parents
                    and r['path'] not in expected and Path(r['path']) != root and root not in Path(r['path']).parents
                    and Path(r['path']) != config_path})
    passed = all(count > 0 for count in counts.values()) and not extra
    if not passed:
        raise ValueError('Solver selected-provider open set mismatch')
    return {'passed': True, 'enabled_provider_open_counts': counts, 'unexpected_clean_input_paths': extra}


def one_run(source, chain, bundle, contract, reg, stage, code_commit, model, imu, gnss):
    family = "CLEAN5_DEGSUBSET_" + chain
    root = stage / "03_RUNS" / family / source["run_id"]
    root.mkdir(parents=True, exist_ok=False)
    record = {**FLAGS, "family": family, "chain": chain, "run_id": source["run_id"],
              "case_id": source["case_id"], "method_id": source["method_id"],
              "effective_profile": source["effective_profile"], "dataset_id": "BY2",
              "data_mode": "real_clean" if source["case_id"] == "C00_clean_normal" else "real_base_controlled_degradation",
              "controlled_degradation_applied": source["case_id"] != "C00_clean_normal",
              "code_commit": code_commit, "output_root": str(root), "retry_count": 0,
              "terminal_status": "NOT_STARTED", "source_registry_row": source,
              "raw_source_hashes": bundle['raw_input_hashes'],
              "raw_hash_lock": contract["sources"]["raw_lock"],
              "provider_hashes": {k: v["sha256"] for k, v in bundle["providers"].items()}}
    started = time.monotonic()
    try:
        original_path = Path(source["runtime_config_path"])
        if sha256_file(original_path) != source["runtime_config_file_hash"]:
            raise ValueError("Original selected runtime config changed")
        original = original_path.read_text()
        replacements = {k: v["path"] for k, v in bundle["providers"].items()}
        replacements["outputpath"] = str(root)
        if chain == "CAL":
            text, diff = patch_calibrated_config(original, replacements, model,
                model_sha256=contract["runtime"]["model"]["sha256"], model_commit=contract["runtime"]["model_freeze_commit"])
        else:
            text, diff = bind_config(original, replacements)
        config = yaml.safe_load(text)
        record.update(config_hash=hashlib.sha256(text.encode()).hexdigest(), config_byte_diff=diff,
                      native_identity={k: config[k] for k in ("stage_id", "protocol_id", "run_id", "case_id", "data_mode")},
                      executable_sha256=contract["runtime"]["executable"]["sha256"],
                      scientific_solver_commit=contract["runtime"]["scientific_solver_commit"])
        cfg_path = root / "DEGRADATION_RUNTIME_CONFIG.yaml"
        cfg_path.write_text(text)
        expected = expected_counts(config, gnss, imu)
        record["expected_counters"] = expected
        write_json(root / "RUN_STARTED.json", record)
        log = root / "SOLVER_OPENAT.strace"
        command = ["env", "OMP_NUM_THREADS=1", "OPENBLAS_NUM_THREADS=1", "MKL_NUM_THREADS=1",
                   "strace", "-f", "-qq", "-yy", "-s", "4096", "-e", "trace=openat", "-o", str(log),
                   str(resolve(contract["runtime"]["executable"]["path"], reg)), "--config", str(cfg_path),
                   "--output-dir", str(root), "--debug-update-timeline", "--debug-output-dir", str(root),
                   "--debug-max-rows", "1000000"]
        result = run_process_group(command, cwd=reg.code_root, timeout_seconds=contract["runtime"]["timeout_s"],
                                   timeout_message="P07 solver timeout; no retry", launch_failure_message="P07 solver launch failure")
        (root / "stdout.log").write_text(result.stdout)
        (root / "stderr.log").write_text(result.stderr)
        record.update(command=command, exit_code=result.returncode)
        record["strace_audit"] = audit_solver_openat(log, cwd=reg.code_root, raw_root=reg.raw_root,
                                                     clean_root=reg.clean_root, run_dir=root)
        if result.returncode != 0:
            raise RuntimeError("FAILED_NATIVE_SOLVER")
        native = json.loads((root / "RUN_MANIFEST.json").read_text())
        record['native_identity_audit'] = validate_identity(native, config, source, bundle)
        record['selected_provider_open_audit'] = validate_input_opens(log, native['actual_solver_input_paths'], reg, root, cfg_path)
        record["counter_audit"] = check_counters(native, config, expected)
        record["auxiliary_counter_audit"] = check_auxiliary(native, config, expected)
        record["counters"] = record["counter_audit"]["actual"]
        record["output_validation"] = validate_run_outputs(root, {"window_contract": {"t_start": 66., "t_end": 340.}})
        if not record["strace_audit"].get("pass", record["strace_audit"].get("passed", False)):
            raise RuntimeError("FAILED_SOLVER_OPEN_AUDIT")
        if not record["counter_audit"]["pass"]:
            raise RuntimeError("FAILED_COUNTER_AUDIT")
        if not record["auxiliary_counter_audit"]["pass"]:
            raise RuntimeError("FAILED_AUXILIARY_COUNTER_AUDIT")
        record["terminal_status"] = "COMPLETED"
    except Exception as error:
        record.update(terminal_status="FAILED_TECHNICAL", failure_type=type(error).__name__, failure=str(error))
    record["runtime_seconds"] = time.monotonic() - started
    write_json(root / "P07_RUN_TERMINAL.json", record)
    return record


def run_all(runs, bundles, contract, reg, stage, code_commit, resolution):
    pinned(contract['runtime']['executable'], reg)
    unique_pins = {v['path']: v for bundle in bundles.values() for v in bundle['providers'].values()}
    for spec in unique_pins.values():
        pinned(spec, reg)
    checkpoint(contract, reg, stage, "BEFORE_SOLVER", resolution)
    model = yaml.safe_load(pinned(contract["runtime"]["model"], reg).read_text())
    # Frozen model nests calibrated values under calibrated_model.
    if "vrw" not in model:
        model = model["calibrated_model"]
    imu = np.loadtxt(bundles["C00_clean_normal"]["providers"]["imupath"]["path"], ndmin=2)
    gnss = {case: np.loadtxt(bundle["providers"]["gnsspath"]["path"], ndmin=2) for case, bundle in bundles.items()}
    records = []
    with ThreadPoolExecutor(max_workers=contract["runtime"]["jobs"]) as pool:
        futures = [pool.submit(one_run, row, chain, bundles[row["case_id"]], contract, reg, stage,
                               code_commit, model, imu, gnss[row["case_id"]])
                   for chain in ("CAL", "V2S") for row in runs]
        for future in as_completed(futures):
            record = future.result()
            records.append(record)
            print("SOLVER", len(records), "/", len(futures), record["chain"], record["run_id"], record["terminal_status"], flush=True)
    records.sort(key=lambda r: (r["chain"], r["run_id"]))
    if len(records) != 1342:
        raise ValueError("Missing terminal runs")
    write_json(stage / "03_RUNS" / "RUN_RECORDS.json", records)
    pinned(contract['runtime']['executable'], reg)
    for spec in unique_pins.values():
        pinned(spec, reg)
    checkpoint(contract, reg, stage, "AFTER_SOLVER", resolution)
    seal_roots(stage, ["03_RUNS"], "04_SEAL/SOLVER_OUTPUT_SEAL.json",
               {"code_commit": code_commit, "run_count": len(records), "data_mode": "real_base_controlled_degradation",
                "terminal_counts": {chain: {status: sum(r["chain"] == chain and r["terminal_status"] == status for r in records)
                                    for status in sorted({r["terminal_status"] for r in records})} for chain in ("CAL", "V2S")}})
    return records
