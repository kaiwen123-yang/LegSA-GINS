"""Read-only compact handoff from terminal protocol-v2 artifacts.

Structure and metric whitelist follow c541_pack_v2. No metric recomputation,
provider/solver/evaluator calls, raw opens, overwrites or cleanup occur here.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import zipfile

import pandas as pd
import yaml

from ..manifest import sha256_file
from .aggregate import AGGREGATE_FILES

IDENT = {"run_id", "run_order", "execution_key", "case_id", "method_id", "matrix",
    "effective_configuration_id", "role", "case_family", "degradation_id", "seed_id",
    "output_root", "evaluation_status", "technical_failure", "algorithm_failure",
    "finite_output", "reference_identity", "protocol_id", "evaluator_version", "evaluator_contract",
    "solver_terminal_status", "dataset_id", "data_mode", "synthetic_data_used", "semisynthetic_data_used",
    "trace_used_online", "controlled_degradation_applied", "uncertainty_status", "v3_std_policy",
    "code_commit", "config_hash", "native_nav_sha256", "eval_nav_sha256", "std_sha256",
    "native_execution_code_commit", "validation_code_commit", "continuation_code_commit",
    "validation_config_hash", "original_native_reused"}
KEEP_COL = re.compile(
    r"^(east|north|up|horizontal|position_3d|attitude_norm|roll|pitch|yaw)_"
    r"(rmse|mae|bias|signed_mean|signed_median|standard_deviation|median|"
    r"median_absolute_error|p50_absolute|p90_absolute|p95_absolute|p99_absolute|"
    r"max_absolute|p50|p90|p95|p99|max|final|final_signed_error|final_absolute_error)"
    r"(_m|_deg|_mps)?$|^(fault_window|post_window|pre_window|during_window)_|^recovery|^time_to"
    r"|coverage|finite|output_epoch|duration|_dt_sec|max_gap|sigma|z_rmse|calibration"
    r"|normalized_squared|_count$|touch_rate|residual_p95|runtime_seconds")
KEEP_BIG = re.compile(
    r"^(east|north|up|horizontal|position_3d|attitude_norm|roll|pitch|yaw)_"
    r"(rmse|bias|signed_mean|standard_deviation|median|p95|p95_absolute|max|max_absolute)"
    r"(_m|_deg|_mps)?$|^(fault_window|post_window|pre_window)_.*(rmse|p95|max)"
    r"|coverage_[123]sigma|calibration_ratio|z_rmse|coverage_ratio|finite_ratio")
REP_TYPES = {"D04", "D12", "D27", "D58", "D60"}
CONFIGS = {"single_antenna_EKF", "basic_dual_yaw_EKF", "AB0000", "AB1011", "AB1111"}
SERIES_COLS = ["time", "err_n_m", "err_e_m", "err_u_m", "horizontal_err_m",
               "position_3d_err_m", "roll_err_deg", "pitch_err_deg", "yaw_err_deg"]


def _safe_file(path, root):
    path, root = Path(path), Path(root).resolve()
    if path.is_symlink() or not path.is_file() or root not in path.resolve().parents:
        raise ValueError("Handoff source must be a regular file inside this stage: " + str(path))
    if any(p.is_symlink() for p in path.parents if p != root and root in p.parents):
        raise ValueError("Symlink source ancestor")
    return path


def _json(path, payload):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def _gz_frame(frame, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
                frame.to_csv(text, index=False)


def validate_archive(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or archive.testzip() is not None:
            raise ValueError("Archive duplicate member or CRC failure")
        if any(Path(name).is_absolute() or ".." in Path(name).parts for name in names):
            raise ValueError("Unsafe archive member")
        manifest = json.loads(archive.read("PACKAGE_MANIFEST.json"))
        if set(names) != set(manifest["members"]) | {"PACKAGE_MANIFEST.json"}:
            raise ValueError("Archive member coverage changed")
        for name, identity in manifest["members"].items():
            content = archive.read(name)
            if len(content) != identity["size_bytes"] or hashlib.sha256(content).hexdigest() != identity["sha256"]:
                raise ValueError("Archive member identity mismatch: " + name)
        probe = json.loads(archive.read("IDENTITY_PROBE.json"))
        if probe.get("passed") is not True:
            raise ValueError("Archive identity probe failed")
        recovery = probe.get('io_recovery_identity')
        if recovery is not None:
            if (recovery.get('status') != 'PASS_FULL_EXECUTION_ZERO_PENDING_AND_AGGREGATE'
                    or recovery.get('archive_pending_count') != 0
                    or recovery.get('resolved_run_count') != 5973 or recovery.get('resolved_evaluation_count') != 11946):
                raise ValueError('Archive recovery identity is incomplete')
            for name, expected in recovery['package_members'].items():
                if manifest['members'].get(name) != expected:
                    raise ValueError('Archive recovery provenance member missing or changed')
            for pin in recovery.get('posthoc_evaluation_seals', []):
                if manifest['members'].get(pin['package_member'], {}).get('sha256') != pin['sha256']:
                    raise ValueError('Archive post-hoc evaluation seal changed or was omitted')
            acceptance = recovery.get('posthoc_acceptance')
            if acceptance and manifest['members'].get('recovery_provenance/'+acceptance['path'], {}).get('sha256') != acceptance['sha256']:
                raise ValueError('Archive explicit post-hoc acceptance missing or changed')
            for name, expected in (('FULL_RUN_IDENTITIES.json.gz', 5973), ('FULL_EVALUATION_IDENTITIES.json.gz', 11946)):
                rows = json.loads(gzip.decompress(archive.read('recovery_provenance/'+name)))
                if len(rows) != expected:
                    raise ValueError('Archive resolved identity count changed')
            restart = probe.get('restart_identity') or {}
            if restart.get('restart_STOPPED_sha256'):
                historical = [key for key in manifest['members'] if key.startswith('found/RESTARTS__') and key.endswith('__STOPPED.json')]
                if len(historical) != 1 or manifest['members'][historical[0]]['sha256'] != restart['restart_STOPPED_sha256']:
                    raise ValueError('Historical restart stop was hidden or changed')
        return {"passed": True, "member_count": len(names), "size_bytes": Path(path).stat().st_size,
                "sha256": sha256_file(path), "identity_probe": probe}



RECOVERY_IDENTITY_FIELDS = frozenset((
    'run_id', 'dataset_id', 'case_id', 'method_id', 'effective_configuration_id',
    'effective_profile', 'evaluator_version', 'terminal_status', 'solver_terminal_status',
    'evaluation_status', 'protocol_id', 'code_commit', 'original_native_code_commit',
    'native_execution_code_commit', 'validation_code_commit', 'continuation_code_commit',
    'archive_code_commit', 'io_fix_code_commit', 'config_hash', 'validation_config_hash',
    'executable_sha256', 'evaluator_sha256', 'native_nav_sha256', 'eval_nav_sha256',
    'std_sha256', 'provider_hashes', 'raw_source_hashes', 'output_root', 'archive_receipt',
    'evaluation_output_root', 'error_series_source', 'summary_source', 'native_run_manifest',
    'posthoc_evaluation_seal', 'original_native_reused', 'synthetic_data_used',
    'semisynthetic_data_used', 'trace_used_online'))


def recovery_metadata(stage):
    """Read actual terminal recovery evidence; never reinterpret an unfinished stop."""
    stage = Path(stage).resolve()
    parent = stage/'IO_RECOVERY'
    if not parent.exists():
        return None
    execution_path = _safe_file(stage/'EXECUTION_COMPLETE.json', stage)
    execution = json.loads(execution_path.read_text())
    if (execution.get('status') != 'EXECUTION_COMPLETE_PENDING_AGGREGATE'
            or execution.get('run_count') != 5973 or execution.get('evaluation_count') != 11946
            or execution.get('archive_pending_count') != 0):
        raise ValueError('Actual full execution and zero archive pending required before handoff')
    candidates = []
    for root in sorted(parent.iterdir()):
        if root.is_symlink():
            raise ValueError('Symlink I/O recovery directory')
        if not root.is_dir() or not (root/'IO_FIX_FREEZE.json').is_file():
            continue
        freeze = json.loads(_safe_file(root/'IO_FIX_FREEZE.json', stage).read_text())
        if freeze.get('io_fix_code_commit') == execution.get('io_fix_code_commit'):
            candidates.append((root, freeze))
    if len(candidates) != 1:
        raise ValueError('Full execution does not identify exactly one I/O recovery freeze')
    root, freeze = candidates[0]
    if (freeze.get('status') != 'IO_FIX_FROZEN'
            or freeze.get('scientific_code_commit') != execution.get('code_commit')):
        raise ValueError('I/O recovery scientific/fix code identity mismatch')
    scientific = _safe_file(freeze['scientific_contract_path'], stage)
    continuation = _safe_file(freeze['continuation_freeze_path'], stage)
    if (sha256_file(scientific) != freeze['scientific_contract_sha256']
            or sha256_file(continuation) != freeze['continuation_freeze_sha256']):
        raise ValueError('I/O recovery contract/continuation freeze changed')
    protocol = yaml.safe_load(scientific.read_text())['protocol_id']
    pending = {}
    pending_path = root/'ARCHIVE_PENDING_LEDGER.jsonl'
    if pending_path.exists():
        for line in _safe_file(pending_path, stage).read_text().splitlines():
            row = json.loads(line)
            if row['status'] == 'ARCHIVE_PENDING':
                pending[row['run_id']] = row
            elif row['status'] == 'ARCHIVE_RESOLVED':
                pending.pop(row['run_id'], None)
            else:
                raise ValueError('Unknown archive pending ledger event')
    if pending:
        raise ValueError('Archive pending ledger is not empty at handoff')
    for version in ('v3', 'v2'):
        terminal = json.loads(_safe_file(stage/'13_AGGREGATE'/version/'FINAL_EVALUATION_SUMMARY.json', stage).read_text())
        if (terminal.get('aggregate_completed') is not True or terminal.get('unique_evaluated') != 5951
                or terminal.get('logical_evaluated') != 7033 or terminal.get('protocol_id') != protocol
                or terminal.get('evaluator_version') != version):
            raise ValueError('Full protocol-v2 aggregate identity is incomplete or mismatched')
    run_path, evaluation_path = (root/name for name in ('FULL_RUN_RECORDS.json', 'FULL_EVALUATION_RECORDS.json'))
    runs = json.loads(_safe_file(run_path, stage).read_text())
    evaluations = json.loads(_safe_file(evaluation_path, stage).read_text())
    run_ids = {r['run_id'] for r in runs}
    evaluation_ids = {(r['run_id'], r['evaluator_version']) for r in evaluations}
    if (len(runs) != 5973 or len(run_ids) != 5973 or len(evaluations) != 11946
            or evaluation_ids != {(key, version) for key in run_ids for version in ('v3', 'v2')}
            or sum(r.get('dataset_id') == 'BY2' for r in runs) != 5951):
        raise ValueError('Full resolved run/evaluation identity coverage differs')
    terminal_by_run = {row['run_id']: row.get('terminal_status') for row in runs}
    allowed_evaluation = {'COMPLETED': 'COMPLETED',
                          'ALGORITHM_FAILURE_ALL_YAW_REJECTED': 'NOT_RUN_ALGORITHM_FAILURE'}
    if any(value not in allowed_evaluation for value in terminal_by_run.values()):
        raise ValueError('Unsupported or unfinished native run in final resolved identities')
    if any(row.get('evaluation_status') != allowed_evaluation[terminal_by_run[row['run_id']]] for row in evaluations):
        raise ValueError('Resolved native/evaluator terminal pair is incomplete or inconsistent')
    members = {execution_path}
    metadata_filenames = {
        'IO_FIX_FREEZE.json', 'SCIENTIFIC_CONTRACT.yaml', 'IO_FIX_VALIDATION.json',
        'BATCH008_INPUT_AUDIT.json', 'BATCH001_007_LEDGER_AUDIT.json', 'CONTINUATION_RESOURCE_BASELINE.json',
        'BATCH008_INPUT_ACCEPTANCE.json', 'POSTHOC_RUN_01963_EVALUATION_SEAL.json',
        'BATCH_RESULT.json', 'ARCHIVE_IO_RESULT.json', 'BATCH_ARCHIVE_GATE.json',
        'CLEANUP_COMPLETE.json', 'IO_STOP_LEDGER.jsonl'}
    row_projections = []
    # An explicit filename whitelist prevents arbitrary result JSON from
    # bypassing the frozen numerical-column whitelist. Row tables are reduced
    # to identity fields only, with full original source hashes retained.
    for directory in (root, root/'BATCH_008_RECOVERY'):
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file() or path in (run_path, evaluation_path):
                continue
            if path.name in metadata_filenames:
                members.add(_safe_file(path, stage))
            elif (path.suffix in ('.json', '.jsonl') and
                  (any(token in path.stem for token in ('RUN', 'EVALUATION', 'RECOVERED'))
                   or path.name == 'ARCHIVE_PENDING_LEDGER.jsonl')):
                _safe_file(path, stage)
                payload = ([json.loads(line) for line in path.read_text().splitlines() if line.strip()]
                           if path.suffix == '.jsonl' else json.loads(path.read_text()))
                rows = payload if isinstance(payload, list) else ([payload] if 'run_id' in payload else payload.get('records', []))
                if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                    raise ValueError('Recovery identity source is not a row table')
                projected = []
                for row in rows:
                    identity_row = {key: value for key, value in row.items() if key in RECOVERY_IDENTITY_FIELDS}
                    identity_row.update({key: row[key] for key in ('status', 'batch', 'round', 'utc') if key in row})
                    job = row.get('job')
                    if isinstance(job, dict):
                        identity_row['job_record_identity'] = {key: value for key, value in job.get('record', {}).items()
                                                              if key in RECOVERY_IDENTITY_FIELDS}
                        identity_row['job_evaluation_identities'] = [{key: value for key, value in value.items()
                            if key in RECOVERY_IDENTITY_FIELDS} for value in job.get('evaluations', [])]
                    projected.append(identity_row)
                row_projections.append({'source': path.relative_to(stage).as_posix(),
                    'sha256': sha256_file(path), 'source_rows': len(rows), 'rows': projected})
    notes = stage/'BATCH_LEDGER.notes'
    if notes.exists():
        members.add(_safe_file(notes, stage))
    posthoc = []
    for row in runs:
        if 'posthoc_evaluation_seal' not in row:
            continue
        pin = row['posthoc_evaluation_seal']
        path = _safe_file(pin['path'], stage)
        if (sha256_file(path) != pin['sha256'] or pin.get('historical_full_file_seal_available') is not False
                or pin.get('run_id', row['run_id']) != row['run_id'] or pin.get('versions') != ['v3', 'v2']
                or pin.get('annotation') != 'sealed post-hoc after archival interruption; content verified against scratch (size+sha256)'):
            raise ValueError('Post-hoc evaluation seal identity/annotation mismatch')
        seal = json.loads(path.read_text())
        if (seal.get('run_id') != row['run_id'] or seal.get('annotation') != pin['annotation']
                or seal.get('historical_full_file_seal_available') is not False
                or seal.get('versions') != ['v3', 'v2']):
            raise ValueError('Post-hoc seal body differs from its declared identity')
        members.add(path)
        posthoc.append({'run_id': row['run_id'], **pin})
    acceptance_identity = None
    if posthoc:
        acceptance_path = _safe_file(root/'BATCH008_INPUT_ACCEPTANCE.json', stage)
        acceptance = json.loads(acceptance_path.read_text())
        if (acceptance.get('status') != 'ACCEPTED_AUTHORIZED_POSTHOC_SEAL'
                or len(posthoc) != 1
                or acceptance.get('posthoc_evaluation_seal') != next(r['posthoc_evaluation_seal'] for r in runs if 'posthoc_evaluation_seal' in r)):
            raise ValueError('Post-hoc seal requires its exact explicit acceptance metadata')
        if not notes.is_file():
            raise ValueError('I/O recovery bookkeeping notes are missing from handoff provenance')
        members.add(acceptance_path)
        acceptance_identity = {'path': acceptance_path.relative_to(stage).as_posix(), 'sha256': sha256_file(acceptance_path)}
    identity = {'status': 'PASS_FULL_EXECUTION_ZERO_PENDING_AND_AGGREGATE',
        'io_root': root.relative_to(stage).as_posix(), 'io_fix_code_commit': freeze['io_fix_code_commit'],
        'scientific_code_commit': freeze['scientific_code_commit'], 'archive_pending_count': 0,
        'resolved_run_count': len(runs), 'resolved_evaluation_count': len(evaluations),
        'posthoc_evaluation_seals': posthoc, 'posthoc_acceptance': acceptance_identity,
        'historical_stops_preserved': True,
        'full_run_records_source': {'path': run_path.relative_to(stage).as_posix(), 'sha256': sha256_file(run_path)},
        'full_evaluation_records_source': {'path': evaluation_path.relative_to(stage).as_posix(), 'sha256': sha256_file(evaluation_path)},
        'identity_projection': 'all run/version identities retained; no extra numerical fields outside existing metric whitelist'}
    return {'identity': identity, 'members': sorted(members), 'row_projections': row_projections,
        'runs': [{key: value for key, value in row.items() if key in RECOVERY_IDENTITY_FIELDS} for row in runs],
        'evaluations': [{key: value for key, value in row.items() if key in RECOVERY_IDENTITY_FIELDS} for row in evaluations]}


def copy_recovery_metadata(recovery, stage, target):
    if recovery is None:
        return None
    stage, target = Path(stage), Path(target)
    identity = dict(recovery['identity'])
    copied = {}
    for source in recovery['members']:
        relative = 'recovery_provenance/'+source.relative_to(stage).as_posix()
        destination = target/relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        copied[relative] = {'sha256': sha256_file(source), 'size_bytes': source.stat().st_size}
        if sha256_file(destination) != copied[relative]['sha256']:
            raise ValueError('Recovery metadata copy changed bytes')
    for name, rows in (('FULL_RUN_IDENTITIES.json.gz', recovery['runs']),
                       ('FULL_EVALUATION_IDENTITIES.json.gz', recovery['evaluations'])):
        relative = 'recovery_provenance/'+name
        destination = target/relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as raw:
            with gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0) as compressed:
                compressed.write((json.dumps(rows, ensure_ascii=False, allow_nan=False)+'\n').encode())
        copied[relative] = {'sha256': sha256_file(destination), 'size_bytes': destination.stat().st_size}
    projection_sources = []
    for projection in recovery.get('row_projections', []):
        relative = 'recovery_provenance/identity_tables/'+projection['source']+'.identity.json.gz'
        destination = target/relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as raw:
            with gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0) as compressed:
                compressed.write((json.dumps(projection['rows'], ensure_ascii=False, allow_nan=False)+'\n').encode())
        copied[relative] = {'sha256': sha256_file(destination), 'size_bytes': destination.stat().st_size}
        projection_sources.append({key: value for key, value in projection.items() if key != 'rows'} | {'package_member': relative})
    identity['row_projection_sources'] = projection_sources
    identity['package_members'] = copied
    identity['posthoc_evaluation_seals'] = [{**pin, 'package_member':
        'recovery_provenance/'+Path(pin['path']).relative_to(stage).as_posix()}
        for pin in identity['posthoc_evaluation_seals']]
    return identity


def pack(stage, output_zip, *, package_dir=None):
    stage, output_zip = Path(stage).resolve(), Path(output_zip).expanduser().absolute()
    if output_zip.exists() or output_zip.is_symlink():
        raise FileExistsError("Refuse existing handoff ZIP: " + str(output_zip))
    target = Path(package_dir).expanduser().absolute() if package_dir else output_zip.with_suffix("")
    if target.exists() or target.is_symlink() or target == stage or stage in target.parents:
        raise FileExistsError("Handoff workspace must be fresh and outside stage")
    recovery = recovery_metadata(stage)
    target.mkdir(parents=True, exist_ok=False)
    recovery_identity = copy_recovery_metadata(recovery, stage, target)
    headers, probes, source_rows, subset_manifest = {}, {}, [], []
    for version in ("v3", "v2"):
        aggregate_root = stage / "13_AGGREGATE" / version
        evaluation_root = stage / "12_OFFLINE_EVALUATION" / version
        terminal = json.loads(_safe_file(aggregate_root / "FINAL_EVALUATION_SUMMARY.json", stage).read_text())
        if terminal.get("aggregate_completed") is not True or terminal.get("unique_evaluated") != 5951 or terminal.get("logical_evaluated") != 7033:
            raise ValueError("Complete matrix aggregate required before handoff")
        if any(not (aggregate_root / name).is_file() for name in AGGREGATE_FILES):
            raise ValueError("Required Canonical aggregate table absent")
        for source in sorted(aggregate_root.iterdir()):
            if source.suffix not in (".csv", ".json"):
                continue
            _safe_file(source, stage)
            rel = Path("13_AGGREGATE") / version / source.name
            if source.suffix == ".csv":
                frame = pd.read_csv(source, dtype=str, keep_default_na=False, low_memory=False)
                before = len(frame)
                if "metric_name" in frame.columns and before > 20000:
                    frame = frame[frame.metric_name.str.contains(KEEP_BIG, regex=True, na=False)]
                headers[rel.as_posix()] = list(frame.columns)
                _gz_frame(frame, target / (rel.as_posix()+".gz"))
                source_rows.append({"source": source.relative_to(stage).as_posix(), "sha256": sha256_file(source),
                                    "rows_full": before, "rows_kept": len(frame), "column_filter": "c541_pack_v2 KEEP_BIG only above 20000 rows"})
            else:
                (target / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target / rel)
        full = {}
        for name in ("UNIQUE_EVALUATION_RESULTS.csv", "LOGICAL_EVALUATION_RESULTS.csv"):
            source = _safe_file(evaluation_root / name, stage)
            frame = pd.read_csv(source, dtype=str, keep_default_na=False, low_memory=False)
            full[name] = frame
            rel = Path("12_OFFLINE_EVALUATION") / version / name
            headers["FULL_"+rel.as_posix()] = list(frame.columns)
            kept = frame[[c for c in frame.columns if c in IDENT or KEEP_COL.search(c)]]
            _gz_frame(kept, target / (rel.as_posix()+".gz"))
            source_rows.append({"source": source.relative_to(stage).as_posix(), "sha256": sha256_file(source),
                                "rows_full": len(frame), "rows_kept": len(kept), "columns_full": len(frame.columns), "columns_kept": len(kept.columns)})
        unique, logical = full["UNIQUE_EVALUATION_RESULTS.csv"], full["LOGICAL_EVALUATION_RESULTS.csv"]
        clean = unique.case_id == "C00_clean_normal"
        case_count = unique.case_id.nunique()
        if len(unique) != 5951 or len(logical) != 7033 or case_count != 541:
            raise ValueError("Handoff table identity counts differ")
        if unique.duplicated(["case_id", "effective_configuration_id"]).any() or unique.effective_configuration_id.nunique() != 11:
            raise ValueError("Handoff duplicate or missing configuration")
        if len(unique[clean]) != 11 or (unique[clean].evaluation_status != "COMPLETED").any():
            raise ValueError("Eleven completed C00 anchors required")
        selected = unique[unique.effective_configuration_id.isin(CONFIGS) & (unique.degradation_id.isin(REP_TYPES) | clean)]
        for row in selected.to_dict("records"):
            item = {"evaluator_version": version, **{k: row[k] for k in ("run_id", "case_id", "degradation_id", "seed_id", "method_id", "effective_configuration_id")}}
            if row["evaluation_status"] != "COMPLETED":
                subset_manifest.append({**item, "status": row["evaluation_status"], "rows_full": 0, "rows_kept": 0})
                continue
            source = _safe_file(row["error_series_source"], stage)
            frame = pd.read_csv(source, usecols=SERIES_COLS)
            # Exact retained samples, no interpolation or metric recomputation.
            decimated = frame.iloc[::20]
            rel = Path("error_series_subset") / version / (row["run_id"]+".csv.gz")
            _gz_frame(decimated, target / rel)
            subset_manifest.append({**item, "status": "OK", "rows_full": len(frame), "rows_kept": len(decimated),
                                    "source_sha256": sha256_file(source), "sample_policy": "every 20th existing row; no interpolation"})
        nav_names = []
        # Both versions share the native NAV; include all eleven C00 configs.
        if version == "v3":
            for row in unique[clean].to_dict("records"):
                source = _safe_file(Path(row["output_root"]) / "NAV_10HZ.csv.gz", stage)
                rel = "C00_NAV_"+row["effective_configuration_id"]+".csv.gz"
                shutil.copyfile(source, target / rel)
                nav_names.append(rel)
        probes[version] = {"unique_rows": len(unique), "logical_rows": len(logical), "cases": int(case_count),
            "configs": sorted(unique.effective_configuration_id.unique().tolist()),
            "degradation_ids": int(unique.degradation_id.nunique()),
            "seeds": sorted(unique.seed_id.unique().tolist()), "families": sorted(unique.case_family.unique().tolist()),
            "eval_status": unique.evaluation_status.value_counts().to_dict(),
            "C00_yaw_rmse_by_config": dict(zip(unique[clean].effective_configuration_id, unique[clean].yaw_rmse_deg)),
            "C00_case_ids": sorted(unique[clean].case_id.unique().tolist()), "nav_files": nav_names}
        for name in ("EVALUATION_STATUS.json", "EVALUATION_FAILURES.csv", "FIELD_DEFINITIONS.md"):
            source = _safe_file(evaluation_root / name, stage)
            destination = target / "12_OFFLINE_EVALUATION" / version / name
            shutil.copyfile(source, destination)
    # Preserve original failed evidence and the separately authorized restart.
    restart_identity = None
    restart_directories = []
    restart_parent = stage/'RESTARTS'
    if restart_parent.exists():
        restarts = sorted(p for p in restart_parent.iterdir() if p.is_dir())
        if len(restarts) != 1:
            raise ValueError('Expected exactly one explicitly authorized protocol restart')
        restart = restarts[0]
        freeze = json.loads(_safe_file(restart/'CONTINUATION_FREEZE.json', stage).read_text())
        gate = json.loads(_safe_file(restart/'SEQUENCE_CONSISTENCY_GATE.json', stage).read_text())
        if gate['status'] != 'PASS':
            raise ValueError('Active sequence gate must pass before handoff')
        historical_stop = restart/'STOPPED.json'
        if historical_stop.exists() and recovery_identity is None:
            raise ValueError('Restart stop requires actual completed I/O recovery before handoff')
        restart_identity = {'active_sequence_gate': str((restart/'SEQUENCE_CONSISTENCY_GATE.json').relative_to(stage)),
            'active_sequence_gate_status': gate['status'], 'continuation_code_commit': freeze['code_commit'],
            'original_native_code_commit': freeze['original_execution_freeze']['code_commit'],
            'original_stage_STOPPED_and_gate_role': 'PRESERVED_PRE_RESTART_HISTORY',
            'original_native_reused_count': 33,
            'restart_STOPPED_role': 'PRESERVED_HISTORICAL_ARCHIVAL_INTERRUPTION' if historical_stop.exists() else None,
            'restart_STOPPED_sha256': sha256_file(historical_stop) if historical_stop.exists() else None,
            'resolved_by_io_recovery': recovery_identity is not None}
        restart_directories.append(restart)
        validation_root = restart/'REVALIDATION_RUNS'
        restart_directories.extend(sorted(p for p in validation_root.iterdir() if p.is_dir()))
    # Bounded identity/gate and registry copies; no traversal into providers/runs.
    for directory in (stage, stage / "00_PREREGISTRATION", stage / "01_REGISTRY", stage / "07_FULL_ALGORITHM_REGISTRY", *restart_directories):
        if not directory.is_dir():
            continue
        for source in sorted(directory.iterdir()):
            if not source.is_file() or source.suffix not in (".json", ".jsonl", ".csv", ".yaml") or source.stat().st_size > 20_000_000:
                continue
            _safe_file(source, stage)
            rel = Path("found") / "__".join(source.relative_to(stage).parts)
            (target / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target / rel)
    subset_path = target / "error_series_subset" / "SUBSET_MANIFEST.csv"
    pd.DataFrame(subset_manifest).to_csv(subset_path, index=False)
    _json(target / "HEADERS.json", headers)
    _json(target / "SOURCE_TABLE_ROWS.json", source_rows)
    _json(target / "IDENTITY_PROBE.json", {"passed": True, "versions": probes,
        "restart_identity": restart_identity, "io_recovery_identity": recovery_identity,
        "series_ok": sum(r["status"] == "OK" for r in subset_manifest),
        "series_algorithm_or_technical_unavailable": sum(r["status"] != "OK" for r in subset_manifest),
        "C00_native_NAV_10Hz_count": 11, "metric_recomputation_performed": False,
        "raw_reference_open_count": 0, "main_manuscript_evaluator": "v3", "parallel_evaluator": "v2"})
    members = {p.relative_to(target).as_posix(): {"sha256": sha256_file(p), "size_bytes": p.stat().st_size}
               for p in sorted(target.rglob("*")) if p.is_file()}
    _json(target / "PACKAGE_MANIFEST.json", {"schema_version": "canonical541_handoff_v3", "members": members,
        "aggregation_source": "protocol v2 CAL full matrix", "raw_payload_included": False, "metric_recomputation_performed": False})
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for source in sorted(target.rglob("*")):
            if source.is_file():
                archive.write(source, source.relative_to(target).as_posix())
    result = validate_archive(output_zip)
    _json(output_zip.with_suffix(".validation.json"), result)
    return {**result, "archive": str(output_zip), "package_dir": str(target)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--output", default=str(Path.home() / "c541_v2_handoff.zip"))
    parser.add_argument("--package-dir")
    args = parser.parse_args(argv)
    result = pack(args.stage_root, args.output, package_dir=args.package_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
    return 0
