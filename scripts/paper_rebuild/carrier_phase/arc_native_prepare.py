"""Registered, one-shot ARC schedule/config preparation; never native/evaluation.

Boundedly decodes three SEALED detailed-result files which contain phase z/G/Q.
Only identity/time/fingerprint/status fields affect preparation; phase_math_calls=0.
No NPZ, raw, reference, NAV, or scientific-provider payload is opened.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import time
import traceback

ROOT = Path(__file__).resolve().parents[3]
SCRATCH = Path("/home/kaiwen/research/LegSA-GINS-SCRATCH")
STAGE = SCRATCH / "TRUSTED_HEADING_CONTINUATION_20261007/ARC_NATIVE_TELEMETRY_REPAIR01"
PLAN_REL = "docs/paper_rebuild/TRUSTED_HEADING_CONTINUATION_20261007/ARC_NATIVE_PREPARE_REPAIR_PLAN.json"
SOURCE_REL = "scripts/paper_rebuild/carrier_phase/arc_native_prepare.py"
SIDS = ("BY2", "BY2H", "BY2O")
BLOCKS = (274, 270, 377)
LEGAL = (240, 243, 377)
WINDOWS = ((66., 340.), (413., 683.), (3186., 3563.))
BASES = (1772784000., 1772784000., 1772780400.)
TIME_SCALE = "UTC_UNIX_MINUS_REGISTERED_BASE_SECONDS"
META_KEYS = ("stage_id", "protocol_id", "case_id", "run_id", "run_label", "outputpath")
ARC_KEYS = ("arc_clone_mode", "arc_source_events_path", "arc_source_events_sha256",
            "arc_schedule_manifest_sha256", "arc_source_time_scale_id",
            "arc_source_time_mapping_id", "arc_availability_policy")
CSV_FIELDS = ("schema_version sequence_id block_id endpoint_id role source_time_s "
              "source_time_bits_hex replay_execution_time_s actual_available_time_s "
              "availability_mode epoch_index endpoint_model_fingerprint").split()
ROW_ID = ("sequence", "block_index", "first_epoch_index", "last_epoch_index",
          "start_s", "end_s", "interval_s", "status", "endpoint_models_available")
NA_FIELDS = ("actual_available_time_s", "actual_latency_s", "joint_covariance_m2",
             "direction_point_ecef", "attitude_rank")
SAFE = re.compile(r"^[A-Za-z0-9_.:+-]+$")
FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
KEY_LINE = re.compile(rb"^([A-Za-z0-9_]+)[ \t]*:[ \t]*(.*?)(?:\r?\n)?$")
BUDGET = dict(prepare_invocations=1, opportunity_decodes=1, detailed_result_decodes=3,
              detailed_result_rows=921, fixed_blocks=921, endpoint_rows=1842,
              config_outputs=3, event_csv_outputs=3, loader_calls_in_prepare=0,
              native_calls=0, evaluator_calls=0, phase_math_calls=0, npz_reads=0,
              provider_payload_reads=0, reference_reads=0, raw_reads=0,
              source_and_metadata_hash_passes=2, automatic_retries=0)


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def emit(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def pin(path):
    data = path.read_bytes()
    return dict(path=str(path), sha256=sha(data), size_bytes=len(data))


def bits(value):
    require(math.isfinite(value), "nonfinite source time")
    return struct.pack(">d", value).hex()


def number(value):
    require(not isinstance(value, bool), "boolean used as source time")
    result = float(value)
    require(math.isfinite(result), "nonfinite source time")
    return result


def natural(value):
    if isinstance(value, int) and not isinstance(value, bool):
        result = value
    else:
        require(isinstance(value, str) and re.fullmatch(r"[0-9]+", value), "invalid index")
        result = int(value)
    require(result >= 0, "negative index")
    return result


def config_tokens(payload):
    """Read flat keys only; untouched line bytes remain the scientific contract."""
    result = {}
    for line in payload.splitlines(keepends=True):
        if not line.strip() or line.lstrip().startswith(b"#"):
            continue
        m = KEY_LINE.fullmatch(line)
        require(m is not None, "unsupported original config syntax")
        key, raw = m[1].decode(), m[2].strip().decode()
        require(key not in result, "duplicate config key: " + key)
        result[key] = raw
    return result


def scalar(token):
    if token.startswith('"'):
        return json.loads(token)
    if token.startswith("'") and token.endswith("'"):
        return token[1:-1]
    return token


def clone_config(payload, fields):
    require(tuple(fields) == META_KEYS + ARC_KEYS, "config edit allowlist")
    old = config_tokens(payload)
    require(all(k in old for k in META_KEYS) and not any(k in old for k in ARC_KEYS),
            "unexpected old metadata/ARC config fields")
    lines = []
    for line in payload.splitlines(keepends=True):
        m = KEY_LINE.fullmatch(line)
        if m and m[1].decode() in META_KEYS:
            k = m[1].decode()
            lines.append((k + ": " + json.dumps(fields[k]) + "\n").encode())
        else:
            lines.append(line)
    require(not lines or lines[-1].endswith(b"\n"), "old config requires terminal newline")
    lines.extend((k + ": " + json.dumps(fields[k]) + "\n").encode() for k in ARC_KEYS)
    new = b"".join(lines)

    def untouched(data):
        return b"".join(line for line in data.splitlines(keepends=True)
                        if not (KEY_LINE.fullmatch(line) and
                                KEY_LINE.fullmatch(line)[1].decode() in fields))
    require(untouched(payload) == untouched(new), "unapproved scientific config byte change")
    require({k:v for k,v in config_tokens(new).items() if k not in fields} ==
            {k:v for k,v in old.items() if k not in fields}, "unapproved config token change")
    return new


def registered(commit):
    path = ROOT / PLAN_REL
    payload = path.read_bytes()
    frozen = subprocess.check_output(["git", "show", commit + ":" + PLAN_REL], cwd=ROOT)
    require(payload == frozen, "registration plan bytes changed")
    plan = json.loads(payload)
    require(plan["schema"] == "trusted_heading.arc_native.prepare.v1" and
            plan["status"] == "REGISTERED_READY", "prepare draft is not executable")
    require(plan["stage"] == str(STAGE) and plan["budget"] == BUDGET, "fixed stage/budget")
    require(plan["allowed_config_edit_keys"] == list(META_KEYS + ARC_KEYS), "config edit gate")
    require(plan["source_time_scale_id"] == TIME_SCALE, "registered local UTC time scale")
    require([(s["sequence_id"],s["blocks"],s["legal_model_blocks"],tuple(s["window_s"]),s["base_time_unix_s"])
             for s in plan["sequences"]] == list(zip(SIDS,BLOCKS,LEGAL,WINDOWS,BASES)),
            "fixed sequence order/full denominator")
    for rel, expected in plan["source_pins"].items():
        current = (ROOT / rel).read_bytes()
        require(sha(current) == expected, "source drift: " + rel)
        require(current == subprocess.check_output(["git","show",commit+":"+rel],cwd=ROOT),
                "source not in registration: " + rel)
    require(SOURCE_REL in plan["source_pins"], "prepare source must be pinned")
    require(not STAGE.exists(), "prepare stage already exists: no retry or alternate stage")
    return plan, payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registration-commit", required=True)
    args = parser.parse_args()
    plan, registered_bytes = registered(args.registration_commit)
    # Stage creation is the one-shot reservation; even a failed decode consumes it.
    STAGE.mkdir()
    (STAGE/"REGISTERED_PLAN.json").write_bytes(registered_bytes)
    emit(STAGE/"PREPARE_RESERVATION.json", dict(registration_commit=args.registration_commit,
         started_unix_s=time.time(), budget=BUDGET, automatic_retry=False))
    started = time.monotonic()
    counts = Counter(opportunity_decodes=0, detailed_result_decodes=0,
                     detailed_result_rows=0, fixed_blocks=0, endpoint_rows=0,
                     native_calls=0, evaluator_calls=0, phase_math_calls=0, npz_reads=0,
                     provider_payload_reads=0, reference_reads=0, raw_reads=0)
    payloads = {}
    try:
        # The whitelist is a registered closed set, not paths learned from data.
        for key, spec in plan["metadata_inputs"].items():
            path = Path(spec["path"])
            require(path.is_absolute() and path.resolve() == path, "metadata path alias/symlink")
            require(spec["kind"] in ("sealed_metadata","original_config","sealed_detailed_result"),
                    "unapproved metadata read class")
            require(path.stat().st_size == spec["size_bytes"] <= plan["limits"]["max_input_bytes"], "input size budget before read")
            data = path.read_bytes()
            require(len(data) == spec["size_bytes"] and sha(data) == spec["sha256"],
                    "metadata pin mismatch: " + key)
            require(len(data) <= plan["limits"]["max_input_bytes"], "input byte budget")
            payloads[key] = data
        require(sum(map(len,payloads.values())) <= plan["limits"]["total_input_bytes"], "total input budget")
        read_json = lambda key: json.loads(payloads[key])
        complete, summary = read_json("arc_complete"), read_json("arc_summary")
        require(complete["status"] == summary["status"] ==
                "COMPLETE_SAVED_MODEL_GEOMETRY_QUALIFICATION_NOT_NAVIGATION" and
                complete["completed_blocks"] == summary["total_fixed_blocks"] == 921 and
                complete["summary_sha256"] == sha(payloads["arc_summary"]), "ARC seal chain")
        for key, name in [("arc_opportunities","OPPORTUNITIES.csv")] + [
                (sid+"_details",sid+"_DETAILS.jsonl.gz") for sid in SIDS]:
            require(summary["output_sha256"][name] == sha(payloads[key]), "ARC sealed output " + name)
        old, old_prepared, old_seal = (read_json(k) for k in ("old_plan","old_prepared","old_native_seal"))
        require(old["schema"] == "trusted_heading.full_window_navigation.v1" and
                old_prepared["status"] == "PREPARED" and old_seal["status"] == "SEALED" and
                old_seal["solver_calls"] == 6 and
                old_prepared["plan_sha256"] == old_seal["plan_sha256"] == sha(payloads["old_plan"]),
                "old native seal chain")
        require(old["registration_commit"] == plan["old_native_registration_commit"], "old native identity")
        rawx_registration, v3_lock = read_json("rawx_registration"), read_json("v3_lock")
        reader = csv.DictReader(io.StringIO(payloads["arc_opportunities"].decode("utf-8")))
        require(reader.fieldnames == plan["opportunity_columns"], "opportunity schema changed")
        opportunities = []
        for row in reader:
            require(len(opportunities) < 921 and None not in row, "opportunity denominator/columns")
            opportunities.append(row)
        counts["opportunity_decodes"] += 1
        require(len(opportunities) == 921, "incomplete opportunities")
        runs, input_declarations, global_manifests = [], {}, []
        offset = 0
        known_fingerprints = set()
        for spec in plan["sequences"]:
            sid, n, legal_n = spec["sequence_id"], spec["blocks"], spec["legal_model_blocks"]
            old_run = next(x for x in old["runs"] if x["run_id"] == sid+"__PVT_CONTROL")
            old_seq = next(x for x in old["sequences"] if x["sequence_id"] == sid)
            rawx_seq = next(x for x in rawx_registration["sequences"] if x["sequence"] == sid)
            v3_seq = next(x for x in v3_lock["sequences"] if x["sequence_id"] == sid)
            provider_manifest = read_json(sid+"_provider_manifest")
            require(old_seq["base_time_unix_s"] == rawx_seq["base_time"] ==
                    v3_seq["base_time_unix_s"] == provider_manifest["audit"]["base_time"] ==
                    spec["base_time_unix_s"], "time base provenance mismatch")
            require(old_run["window"] == old_seq["full_window_s"] == v3_seq["full_window_s"] ==
                    provider_manifest["audit"]["window_seconds"] == spec["window_s"], "window provenance")
            require(provider_manifest["audit"]["imu"]["timestamp_and_gyro_tokens_unchanged"] is True,
                    "calibrated IMU time tokens changed")
            imu_declared = provider_manifest["variants"]["V2s"]["providers"]["imupath"]
            require(all(imu_declared[k] == old_run["providers"]["imupath"][k]
                        for k in ("path","sha256")), "IMU declared source identity")
            cfg_pin = plan["metadata_inputs"][sid+"_config"]
            require(cfg_pin["path"] == old_run["config"]["path"] and
                    cfg_pin["sha256"] == old_run["config"]["sha256"], "old control config identity")
            cfg_payload = payloads[sid+"_config"]
            cfg = config_tokens(cfg_payload)
            get = lambda key, default="": scalar(cfg.get(key,default))
            require(get("runtime_contract") == "research_experiment" and
                    get("heading_source_policy") == "pvt_priority_control" and
                    get("dual_yaw_prediction_model") == "euler_yaw" and
                    get("baseline3d_source") == "external_carrier" and
                    [float(get("starttime")),float(get("endtime"))] == spec["window_s"],
                    "unchanged scientific navigation contract")
            require(get("attitude_clone_mode","off") == "off" and
                    not get("foot_pair_events_path") and
                    all(get(k,"false") == "false" for k in
                        ("enable_qa_fallback","qa_active_mode","enable_multi_state_qm")),
                    "foot/QA/QM must remain off")
            for key, item in old_run["providers"].items():
                require(get(key) == item["path"], "provider config path changed: " + key)
                input_declarations[item["path"]] = item
            require(get("external_carrier_baseline_path") == old_run["carrier"]["path"], "carrier identity")
            input_declarations[old_run["carrier"]["path"]] = old_run["carrier"]
            require(old_run["providers"] == spec["providers_declared_pins"] and
                    old_run["carrier"] == spec["carrier_declared_pin"], "registered provider declaration")
            local = opportunities[offset:offset+n]
            endpoint_rows, blocks = [], []
            status_counts = Counter()
            previous_end = -math.inf
            # These files contain phase matrices. Decode bounded rows, project
            # identity only; never invoke phase algorithms or use matrix values.
            counts["detailed_result_decodes"] += 1
            with gzip.GzipFile(fileobj=io.BytesIO(payloads[sid+"_details"])) as stream:
                for block_index, op in enumerate(local):
                    line = stream.readline(plan["limits"]["max_detail_line_bytes"]+1)
                    require(line and len(line) <= plan["limits"]["max_detail_line_bytes"], "detail line budget/EOF")
                    counts["detailed_result_decoded_bytes"] += len(line)
                    require(counts["detailed_result_decoded_bytes"] <= plan["limits"]["max_total_detail_decoded_bytes"] and
                            time.monotonic()-started <= plan["limits"]["wall_s"], "detail decoded-byte/time budget")
                    detail = json.loads(line)
                    row = detail["row"]
                    counts["detailed_result_rows"] += 1
                    require(op["sequence"] == row["sequence"] == sid and
                            natural(op["block_index"]) == row["block_index"] == block_index and
                            natural(op["first_epoch_index"]) == row["first_epoch_index"] == 5*block_index and
                            natural(op["last_epoch_index"]) == row["last_epoch_index"] == 5*block_index+4,
                            "sequence/block/epoch identity mismatch")
                    for key in ("start_s","end_s","interval_s"):
                        require(bits(number(op[key])) == bits(number(row[key])), "exact time identity: " + key)
                    start, end = number(row["start_s"]), number(row["end_s"])
                    require(spec["window_s"][0] <= start < end < spec["window_s"][1] and
                            start > previous_end and bits(end-start) == bits(number(row["interval_s"])),
                            "window/overlap/duration identity")
                    previous_end = end
                    status = row["status"]
                    require(status == op["status"] and status in
                            ("LEGAL_SAME_ARC_CONTRAST","ENDPOINT_MODEL_UNAVAILABLE"), "unexpected status")
                    require(all(row[k] is None and op[k] == "" for k in NA_FIELDS), "availability/state NA boundary")
                    require(row["navigation_admitted"] is False and op["navigation_admitted"] == "False",
                            "unexpected navigation admission")
                    available = status == "LEGAL_SAME_ARC_CONTRAST"
                    require(row["endpoint_models_available"] is available and
                            op["endpoint_models_available"] == str(available), "model status identity")
                    if available:
                        fps = [detail["epoch0_fingerprint"],detail["epoch1_fingerprint"]]
                        matches = [FINGERPRINT.fullmatch(fp) for fp in fps]
                        require(all(matches) and fps[0] != fps[1],
                                "missing/unsafe endpoint model fingerprint")
                        require(not any(fp in known_fingerprints for fp in fps), "reused endpoint model fingerprint")
                        known_fingerprints.update(fps)
                        model_status = [{"status":"BUILT"},{"status":"BUILT"}]
                        fp_status = "PRESERVED_SEALED_PHASE_EPOCH_FINGERPRINT_SHA256"
                        # PhaseEpoch.fingerprint hashes its header plus working
                        # phase/geometry/covariance arrays, not an NPZ file.
                        phase_epoch_hashes = list(fps)
                    else:
                        require("epoch0_fingerprint" not in detail and "epoch1_fingerprint" not in detail,
                                "unexpected unavailable-block fingerprint schema")
                        model_status = detail["endpoint_model_status"]
                        require(isinstance(model_status,list) and len(model_status)==2 and
                                all(isinstance(s,dict) and isinstance(s.get("status"),str) for s in model_status) and
                                any(s["status"] != "BUILT" for s in model_status), "missing endpoint status identity")
                        fps, phase_epoch_hashes = ["",""], [None,None]
                        fp_status = "NOT_SERIALIZED_FOR_ENDPOINT_UNAVAILABLE_BLOCK"
                    block_id = sid+":BLOCK:"+str(block_index)
                    endpoints = []
                    for role, t, epoch, fp, ms, mh in zip(
                            ("START","END"),(start,end),(5*block_index,5*block_index+4),fps,model_status,phase_epoch_hashes):
                        eid = sid+":EPOCH:"+str(epoch)
                        require(SAFE.fullmatch(eid) and SAFE.fullmatch(block_id), "unsafe derived ID")
                        token = format(t,".17g")
                        require(bits(float(token)) == bits(t), "binary64 round trip")
                        event = dict(zip(CSV_FIELDS,("1",sid,block_id,eid,role,token,bits(t),token,"",
                                     "SOURCE_TIME_REPLAY_ASSUMPTION",str(epoch),fp)))
                        endpoint_rows.append(event)
                        endpoints.append(dict(event=event,model_status=ms,fingerprint_status=fp_status,
                             phase_epoch_fingerprint_sha256=mh,model_content_sha256=None,
                             model_content_sha256_status="UNKNOWN_NOT_READ_OR_RECONSTRUCTED",
                             actual_available_time_s=None,
                             endpoint_id_provenance="DERIVED_SEQUENCE_AND_ORIGINAL_EPOCH_INDEX_NOT_RAWX_KEY"))
                    blocks.append(dict(sequence_id=sid,block_index=block_index,status=status,
                                       first_epoch_index=5*block_index,last_epoch_index=5*block_index+4,
                                       endpoints=endpoints))
                    status_counts[status] += 1
                    del detail  # Do not retain z/G/Q arrays in the output manifest.
                require(stream.read(1) == b"", "extra detailed-result records")
            require(status_counts == Counter(LEGAL_SAME_ARC_CONTRAST=legal_n,
                    **({"ENDPOINT_MODEL_UNAVAILABLE":n-legal_n} if n>legal_n else {})), "fixed status denominator")
            require(len({x["endpoint_id"] for x in endpoint_rows}) == 2*n, "endpoint reuse")
            out = STAGE/"SCHEDULES"/sid
            out.mkdir(parents=True)
            events_path = out/"ARC_SOURCE_EVENTS.csv"
            with events_path.open("w",newline="") as f:
                writer = csv.DictWriter(f,CSV_FIELDS,lineterminator="\n")
                writer.writeheader();writer.writerows(endpoint_rows)
            events_pin = pin(events_path)
            mapping = dict(source_time_scale_id=TIME_SCALE,time_mapping_source_id=spec["time_mapping_source_id"],
                 base_time_unix_s=spec["base_time_unix_s"],
                 rawx_saved_formula="315964800 + gps_week*604800 + gps_tow_seconds - leap_seconds - registered_base",
                 native_imu_formula="Go2 timestamp - registered_base + frozen_zero_offset",
                 original_phase_time_label="GPS_WEEK_TOW__SAVED_LOCAL_BASE",
                 original_phase_time_label_is_inexact_name_only=True,
                 native_imu_existing_timestamp_token_precision_decimals=6,
                 original_saved_endpoint_double_preserved=True,imu_timestamp_snapping=False,
                 physical_synchronization_calibrated=False,actual_arrival_known=False,
                 provenance_keys=["rawx_registration","v3_lock","old_plan",sid+"_provider_manifest"],
                 provenance_source_pins=plan["time_definition_source_pins"])
            manifest_path = out/"ARC_SOURCE_EVENTS_MANIFEST.json"
            emit(manifest_path,dict(schema="trusted_heading.arc_native.schedule.v1",sequence_id=sid,
                 registered_plan_sha256=sha(registered_bytes),registration_commit=args.registration_commit,
                 events=events_pin,blocks=blocks,block_count=n,endpoint_count=2*n,status_counts=status_counts,
                 time_mapping=mapping,identity_fields_only_used=True,phase_math_calls=0,
                 source_detail_contains_phase_matrices=True,
                 source_pins={k:plan["metadata_inputs"][k] for k in
                      ("arc_complete","arc_summary","arc_opportunities",sid+"_details")},
                 fingerprint_does_not_control_clone=True,actual_available_time_s=None))
            manifest_pin = pin(manifest_path)
            rid = sid+"__ARC_EMPTY_MODEL"
            fields = dict(zip(META_KEYS,("TRUSTED_HEADING_ARC_NATIVE_TELEMETRY_20261007",
                       "ARC_EMPTY_MODEL_EXACT_SOURCE_TIME_V1",rid,rid,rid,str(STAGE/"UNUSED_DEFAULT"/sid))))
            fields.update(dict(zip(ARC_KEYS,("NULL_ARC_DIAGNOSTIC",str(events_path),events_pin["sha256"],
                          manifest_pin["sha256"],TIME_SCALE,spec["time_mapping_source_id"],
                          "source_time_replay_assumption"))))
            config_path = STAGE/"CONFIGS"/(rid+".yaml")
            config_path.parent.mkdir(exist_ok=True)
            config_path.write_bytes(clone_config(cfg_payload,fields))
            runs.append(dict(sequence_id=sid,run_id=rid,config=pin(config_path),events=events_pin,
                 manifest=manifest_pin,providers=old_run["providers"],carrier=old_run["carrier"],
                 block_count=n,legal_model_blocks=legal_n,window=spec["window_s"],
                 old_config=old_run["config"],original_checker_echo=old_run["checker_echo"],metadata_fields=fields,
                 shared_config_for_arms=["ARC_NULL","ARC_TELEMETRY"],
                 other_original_config_line_bytes_unchanged=True,time_mapping=mapping))
            global_manifests.append(manifest_pin)
            counts["fixed_blocks"] += n;counts["endpoint_rows"] += 2*n
            offset += n
        require(dict((k,counts[k]) for k in ("opportunity_decodes","detailed_result_decodes",
                "detailed_result_rows","fixed_blocks","endpoint_rows")) ==
                dict((k,BUDGET[k]) for k in ("opportunity_decodes","detailed_result_decodes",
                "detailed_result_rows","fixed_blocks","endpoint_rows")), "completed traversal budget")
        require(len(known_fingerprints) == 1720, "known model fingerprint full denominator")
        # Second HASH pass only: no second opportunity/detail decode and no provider opens.
        for key,spec in plan["metadata_inputs"].items():
            path = Path(spec["path"])
            require(path.stat().st_size == spec["size_bytes"] <= plan["limits"]["max_input_bytes"],
                    "post metadata size budget before read: " + key)
            require(sha(path.read_bytes()) == spec["sha256"], "post metadata drift: " + key)
        for rel,expected in plan["source_pins"].items():
            require(sha((ROOT/rel).read_bytes()) == expected, "post source drift: " + rel)
        require(time.monotonic()-started <= plan["limits"]["wall_s"], "prepare total wall budget")
        emit(STAGE/"ARC_SOURCE_EVENTS_MANIFEST.json",dict(schema="trusted_heading.arc_native.schedules.v1",
             total_blocks=921,total_endpoints=1842,known_fingerprint_blocks=860,
             unrecorded_fingerprint_blocks=61,schedules=global_manifests,
             counts=dict(counts),actual_available_time_s=None))
        prepared = dict(schema="arc_native_telemetry.prepared/v1",stage=str(STAGE),
             stage_alias="ARC_NATIVE_TELEMETRY_REPAIR01",registration_commit=args.registration_commit,
             registered_plan_sha256=sha(registered_bytes),source_pins=plan["source_pins"],
             metadata_inputs=plan["metadata_inputs"],aliases=old["aliases"],
             old_plan=plan["metadata_inputs"]["old_plan"],old_native_seal=plan["metadata_inputs"]["old_native_seal"],
             binary=plan["binary"],library=plan["library"],
             binary_pins_scope="DECLARED_FROZEN_LOCAL_BUILD_PINS_CHECKED_BY_LATER_LOADER_RUNNER",
             inputs=list(input_declarations.values()),runs=runs,total_blocks=921,total_endpoints=1842,
             input_pins_scope="INHERITED_SEALED_DECLARATIONS_NOT_REHASHED_PROVIDER_PAYLOADS_DURING_PREPARE",
             real_hv_scope="UNCHANGED_STATUS_A1_ROTATED_NED_PROVIDER_NOT_SYNTHETIC_BODY_HV",
             time_mapping_scope="COMMON_UTC_MINUS_REGISTERED_BASE_NO_PHYSICAL_SYNC_OR_ARRIVAL_CLAIM",
             counts=dict(counts),budget=BUDGET,native_budget=0,loader_calls=0,evaluator_calls=0)
        emit(STAGE/"PLAN.json",prepared)
        emit(STAGE/"PREPARED.json",dict(status="PREPARED_METADATA_ONLY_NO_NATIVE",
             plan_sha256=sha((STAGE/"PLAN.json").read_bytes()),counts=dict(counts),
             detailed_result_read_scope="THREE_SEALED_RESULTS_CONTAIN_PHASE_VALUES_IDENTITY_ONLY_USED",
             native_calls=0,loader_calls=0,evaluator_calls=0,phase_math_calls=0))
        print(json.dumps(dict(status="PREPARED_METADATA_ONLY_NO_NATIVE",counts=dict(counts))),flush=True)
    except BaseException as exc:
        emit(STAGE/"PREPARE_FAILED.json",dict(status="FAILED_NO_AUTOMATIC_RETRY",error=repr(exc),
             traceback=traceback.format_exc(),counts=dict(counts)))
        raise


if __name__ == "__main__":
    main()
