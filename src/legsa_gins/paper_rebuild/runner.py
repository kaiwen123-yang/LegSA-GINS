"""Independent raw-to-clean-runtime runner for the paper rebuild.

The runner has no discovery fallback. Every filesystem anchor comes from one
explicit ignored local config, and every solver input must be represented in a
fresh clean-input manifest under the configured provider root.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .manifest import (
    ManifestContractError,
    assert_run_manifest,
    git_code_state,
    read_hash_lock,
    sha256_file,
    sha256_text,
    verify_raw_sources,
    write_json_atomic,
)
from .paths import CleanPaths, PathContractError, guard_path, legacy_reason, load_clean_paths


INPUT_MANIFEST_NAME = "CLEAN_INPUT_MANIFEST.json"
APPROVED_METHODS = frozenset(
    {
        "single_antenna_EKF",
        "basic_dual_yaw_EKF",
        "strong_dual_yaw_EKF",
        "LegSA_Paper_V1",
    }
)
SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class CleanRunError(RuntimeError):
    """A clean-input, solver, or output contract failed."""


@dataclass(frozen=True)
class CleanInputBundle:
    root: Path
    imu: Path
    gnss: Path
    dual_yaw: Path
    go2_attitude: Path
    go2_horizontal_velocity: Path
    raw_source_hashes: dict[str, str]
    provider_hashes: dict[str, str]
    provider_relpaths: dict[str, str]
    source_roles: dict[str, Any]
    yaw_contract: dict[str, Any]
    generator_code_commit: str
    generator_config_hash: str
    local_path_config_hash: str


@dataclass(frozen=True)
class PreparedRun:
    method: str
    run_id: str
    output_dir: Path
    config_path: Path
    config_text: str
    command: tuple[str, ...]
    bundle: CleanInputBundle


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CleanRunError(f"Cannot read JSON contract {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CleanRunError(f"JSON contract must be an object: {path.name}")
    return payload


def _artifact_relative(entry: Any, role: str) -> str:
    value = entry.get("relative_path") if isinstance(entry, Mapping) else entry
    if not isinstance(value, str) or not value or value.startswith("/") or ".." in Path(value).parts:
        raise CleanRunError(f"Invalid clean artifact relative path for {role}")
    return value.replace("\\", "/")


def load_clean_input_bundle(paths: CleanPaths) -> CleanInputBundle:
    root = guard_path(paths.provider_root, role="clean provider root", allowed_root=paths.clean_root)
    manifest_path = guard_path(
        root / INPUT_MANIFEST_NAME,
        role="clean input manifest",
        allowed_root=paths.clean_root,
        must_exist=True,
        regular_file=True,
    )
    payload = _load_json(manifest_path)
    if payload.get("data_mode") != "real_by2_raw":
        raise CleanRunError("Clean input manifest data_mode must be real_by2_raw")
    for flag in (
        "synthetic_data_used",
        "semisynthetic_data_used",
        "trace_used_online",
        "receiver_imu_as_body_imu",
        "final_v23_output_solver_input",
        "LegSA_output_solver_input",
        "per_case_tuning",
        "output_only_correction",
        "epoch_deleted_for_metric",
    ):
        if payload.get(flag) is not False:
            raise CleanRunError(f"Clean input manifest forbidden flag is not false: {flag}")
    if payload.get("old_runtime_input_count") != 0:
        raise CleanRunError("Clean input manifest reports legacy runtime inputs")
    generator_commit = payload.get("generator_code_commit")
    generator_config_hash = payload.get("generator_config_hash")
    local_path_config_hash = payload.get("local_path_config_hash")
    if payload.get("generator_worktree_dirty") is not False:
        raise CleanRunError("Clean input provider generation was not from a clean worktree")
    if not all(
        isinstance(value, str) and value
        for value in (generator_commit, generator_config_hash, local_path_config_hash)
    ):
        raise CleanRunError("Clean input provider provenance fields are incomplete")
    try:
        current_commit, current_dirty = git_code_state(paths.code_root)
    except ManifestContractError as exc:
        raise CleanRunError(str(exc)) from exc
    if current_dirty or generator_commit != current_commit:
        raise CleanRunError("Clean input providers do not match the current clean Git commit")
    if local_path_config_hash != sha256_file(paths.config_path):
        raise CleanRunError("Clean input local path config hash changed after provider generation")

    raw_hashes = payload.get("raw_source_hashes")
    declared_hashes = payload.get("provider_hashes")
    artifacts = payload.get("artifacts")
    if not isinstance(raw_hashes, Mapping) or not raw_hashes:
        raise CleanRunError("Clean input manifest has no raw source hashes")
    if not isinstance(declared_hashes, Mapping) or not declared_hashes:
        raise CleanRunError("Clean input manifest has no provider hashes")
    if not isinstance(artifacts, Mapping):
        raise CleanRunError("Clean input manifest has no artifacts mapping")

    required_roles = {
        "imu_runtime_input",
        "gnss_runtime_input",
        "dual_yaw_provider",
        "go2_attitude_prior",
        "go2_horizontal_velocity_prior",
    }
    missing = sorted(required_roles - set(artifacts))
    if missing:
        raise CleanRunError("Clean input artifacts missing roles: " + ",".join(missing))

    provider_paths: dict[str, Path] = {}
    provider_relpaths: dict[str, str] = {}
    actual_provider_hashes: dict[str, str] = {}
    for role, entry in artifacts.items():
        relative = _artifact_relative(entry, str(role))
        candidate = guard_path(
            root / relative,
            role=f"clean provider {role}",
            allowed_root=root,
            must_exist=True,
            regular_file=True,
        )
        actual = sha256_file(candidate)
        expected = declared_hashes.get(role)
        if not isinstance(expected, str) or actual != expected:
            raise CleanRunError(f"Clean provider hash mismatch: {role}")
        provider_paths[str(role)] = candidate
        provider_relpaths[str(role)] = relative
        actual_provider_hashes[str(role)] = actual

    lock = read_hash_lock(paths.raw_hash_lock)
    verified_raw = verify_raw_sources(paths.raw_root, raw_hashes.keys(), lock)
    if dict(raw_hashes) != verified_raw:
        raise CleanRunError("Clean input raw hashes do not match the immutable raw hash lock")

    yaw_contract = payload.get("yaw_contract")
    if not isinstance(yaw_contract, Mapping):
        raise CleanRunError("Clean input manifest has no yaw contract")
    required_yaw = {
        "gnss_order": "GNSS2-GNSS1",
        "lateral_to_body_offset_deg": 90.0,
        "wrap_safe_residual": True,
        "physical_baseline_gate_pass": True,
        "trace_sign_or_offset_selection": False,
    }
    for key, expected in required_yaw.items():
        if yaw_contract.get(key) != expected:
            raise CleanRunError(f"Clean yaw contract mismatch: {key}")

    return CleanInputBundle(
        root=root,
        imu=provider_paths["imu_runtime_input"],
        gnss=provider_paths["gnss_runtime_input"],
        dual_yaw=provider_paths["dual_yaw_provider"],
        go2_attitude=provider_paths["go2_attitude_prior"],
        go2_horizontal_velocity=provider_paths["go2_horizontal_velocity_prior"],
        raw_source_hashes=verified_raw,
        provider_hashes=actual_provider_hashes,
        provider_relpaths=provider_relpaths,
        source_roles=dict(payload.get("source_roles") or {}),
        yaw_contract=dict(yaw_contract),
        generator_code_commit=generator_commit,
        generator_config_hash=generator_config_hash,
        local_path_config_hash=local_path_config_hash,
    )


def _numeric_rows(path: Path, minimum_columns: int) -> list[list[float]]:
    rows: list[list[float]] = []
    with path.open("r", encoding="utf-8", errors="strict") as handle:
        for number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                values = [float(value) for value in stripped.split()]
            except ValueError as exc:
                raise CleanRunError(f"Non-numeric clean input row in {path.name}:{number}") from exc
            if len(values) < minimum_columns or not all(math.isfinite(value) for value in values):
                raise CleanRunError(f"Invalid clean input row in {path.name}:{number}")
            rows.append(values)
    if len(rows) < 2:
        raise CleanRunError(f"Clean input has fewer than two rows: {path.name}")
    return rows


def _attitude_at_or_after(path: Path, time_value: float) -> tuple[float, float]:
    import csv

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                timestamp = float(row.get("time") or "nan")
                roll = math.degrees(float(row.get("roll_rad") or "nan"))
                pitch = math.degrees(float(row.get("pitch_rad") or "nan"))
            except ValueError:
                continue
            if timestamp >= time_value and all(math.isfinite(value) for value in (roll, pitch)):
                return roll, pitch
    return 0.0, 0.0


def _quoted(path: Path) -> str:
    return '"' + str(path).replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_clean_runtime_config(method: str, bundle: CleanInputBundle, output_dir: Path) -> str:
    """Create a new source-derived config; no historical runtime config is read."""

    if method not in APPROVED_METHODS:
        raise CleanRunError(f"Method is outside clean paper scope: {method}")
    imu_rows = _numeric_rows(bundle.imu, 7)
    gnss_rows = _numeric_rows(bundle.gnss, 15)
    start = max(imu_rows[0][0], gnss_rows[0][0])
    available_end = min(imu_rows[-1][0], gnss_rows[-1][0])
    end = min(available_end, start + 10.0)
    if end <= start + 0.1:
        raise CleanRunError("Clean IMU/GNSS overlap is too short for smoke")
    init_gnss = next((row for row in gnss_rows if row[0] >= start), gnss_rows[0])
    roll_deg, pitch_deg = _attitude_at_or_after(bundle.go2_attitude, start)
    init_yaw_deg = init_gnss[13] % 360.0

    basic = method == "basic_dual_yaw_EKF"
    single = method == "single_antenna_EKF"
    paper = method == "LegSA_Paper_V1"
    strong = method == "strong_dual_yaw_EKF"
    if paper and "raw_doppler_provider" not in bundle.provider_relpaths:
        raise CleanRunError("LegSA_Paper_V1 requires a freshly generated Raw Doppler provider")

    raw_path = bundle.root / bundle.provider_relpaths["raw_doppler_provider"] if paper else None
    lines = [
        "# Generated clean-rebuild runtime config; this file is runtime-only.",
        "phase: PAPER10_CLEAN0",
        f"run_label: CLEAN0_BY2_{method}_smoke",
        f"algorithm_id: {method}",
        f"ablation_variant: CLEAN0_BY2_{method}",
        f"imupath: {_quoted(bundle.imu)}",
        f"gnsspath: {_quoted(bundle.gnss)}",
        f"outputpath: {_quoted(output_dir)}",
        "clean_input_provenance_label: clean_rebuild_raw_hash_locked",
        "config_policy_evidence_status: paper_rebuild_explicit_config_only",
        "imudatalen: 7",
        "imudatarate: 500",
        f"starttime: {start:.12g}",
        f"endtime: {end:.12g}",
        f"initpos: [ {init_gnss[1]:.12g}, {init_gnss[2]:.12g}, {init_gnss[3]:.12g} ]",
        f"initvel: [ {init_gnss[7]:.12g}, {init_gnss[8]:.12g}, {init_gnss[9]:.12g} ]",
        f"initatt: [ {roll_deg:.12g}, {pitch_deg:.12g}, {init_yaw_deg:.12g} ]",
        "initgyrbias: [ 0.0, 0.0, 0.0 ]",
        "initaccbias: [ 0.0, 0.0, 0.0 ]",
        "initgyrscale: [ 0.0, 0.0, 0.0 ]",
        "initaccscale: [ 0.0, 0.0, 0.0 ]",
        "initposstd: [ 10.0, 10.0, 10.0 ]",
        "initvelstd: [ 1.0, 1.0, 1.0 ]",
        "initattstd: [ 2.0, 2.0, 2.0 ]",
        "arw: [ 0.985, 0.985, 0.985 ]",
        "vrw: [ 0.077, 0.077, 0.077 ]",
        "gbstd: [ 9.38, 9.38, 9.38 ]",
        "abstd: [ 77.8, 77.8, 77.8 ]",
        "gsstd: [ 0.0, 0.0, 0.0 ]",
        "asstd: [ 0.0, 0.0, 0.0 ]",
        "corrtime: 1.0",
        "antlever: [ 0.0, 0.0, -0.25 ]",
        "initbgstd: [ 9.38, 9.38, 9.38 ]",
        "initbastd: [ 77.8, 77.8, 77.8 ]",
        "initsgstd: [ 0.0, 0.0, 0.0 ]",
        "initsastd: [ 0.0, 0.0, 0.0 ]",
        f"enable_basic_dual_yaw_baseline: {'true' if basic else 'false'}",
        f"enable_dual_yaw_update: {'false' if single else 'true'}",
        "basic_dual_yaw_fixed_std_deg: 1.5",
        "basic_dual_yaw_residual_sign: official_ref_sign_minus",
        f"enable_receiver_velocity_update: {'false' if basic else 'true'}",
        "receiver_velocity_stress_mode: none",
        "receiver_velocity_std_scale: 1.0",
        f"enable_raw_doppler: {'true' if paper else 'false'}",
        f"raw_doppler_factor_path: {_quoted(raw_path) if raw_path else ''}",
        "raw_doppler_mode: doppler_ls_velocity",
        "raw_doppler_R_scale: 1.0",
        f"enable_source_aware_weighting: {'true' if paper else 'false'}",
        "source_aware_policy_version: clean_v1_conservative_innovation_covariance",
        f"source_aware_mode: {'lsim_oim' if paper else 'off'}",
        "source_aware_no_R_shrink: true",
        f"enable_go2_attitude_weak_prior: {'true' if paper else 'false'}",
        f"go2_attitude_prior_path: {_quoted(bundle.go2_attitude) if paper else ''}",
        "go2_attitude_prior_std_roll_deg: 1.6",
        "go2_attitude_prior_std_pitch_deg: 1.6",
        f"enable_go2_horizontal_velocity_prior: {'true' if paper else 'false'}",
        f"enable_go2_velocity_prior_diagnostic: {'true' if paper else 'false'}",
        f"go2_horizontal_velocity_prior_path: {_quoted(bundle.go2_horizontal_velocity) if paper else ''}",
        "go2_horizontal_velocity_prior_vertical_disabled: true",
        "go2_position_prior_enabled: false",
        "go2_velocity_prior_enabled: false",
        "go2_yaw_prior_enabled: false",
        "go2_vertical_velocity_prior_enabled: false",
        "enable_go2_proprioceptive_joint_factor: false",
        "enable_multi_state_qm: false",
        "enable_fgo_feedback: false",
        "fgo_feedback_path: ''",
        "qa_passive_logging_enabled: false",
        "enable_qa_fallback: false",
        "qa_active_mode: false",
        "diagnostic_only: false",
        "diagnostic_stress_only: false",
        "proposed_factor_claim: false",
        "paper_performance_claim: false",
        "no_outperform_final_v23_claim: true",
        "trace_solver_input: false",
        "final_v23_output_solver_input: false",
        "legsa_output_solver_input: false",
        "per_case_tuning: false",
        "output_only_correction: false",
        "bad_epoch_deletion_for_metric: false",
        "fgo: false",
        f"disable_source_aware: {'false' if paper else 'true'}",
        f"disable_go2: {'false' if paper else 'true'}",
        "disable_qm: true",
        f"disable_raw_doppler: {'false' if paper else 'true'}",
        "disable_fgo_feedback: true",
        f"strong_dual_yaw_mode: {'true' if strong else 'false'}",
    ]
    return "\n".join(lines) + "\n"


class CleanPaperRunner:
    """Prepare and run one bounded clean BY2 smoke."""

    def __init__(self, config_path: str | Path):
        self.paths = load_clean_paths(config_path)

    def prepare(self, *, method: str, run_id: str | None = None, replace: bool = False) -> PreparedRun:
        if method not in APPROVED_METHODS:
            raise CleanRunError(f"Method is outside clean paper scope: {method}")
        selected_run_id = run_id or method
        if not SAFE_RUN_ID_RE.fullmatch(selected_run_id):
            raise CleanRunError("run_id contains unsafe path characters")
        bundle = load_clean_input_bundle(self.paths)
        output_dir = guard_path(
            self.paths.runtime_root / "smoke" / selected_run_id,
            role="clean smoke output",
            allowed_root=self.paths.clean_root,
        )
        reason = legacy_reason(output_dir)
        if reason:
            raise CleanRunError(f"Clean smoke output has legacy dependency: {reason}")
        if output_dir.exists():
            if not replace:
                raise CleanRunError("Clean smoke output already exists; use an explicit replace request")
            if output_dir.is_symlink() or not output_dir.is_dir():
                raise CleanRunError("Clean smoke replacement target must be an exact real directory")
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        config_text = build_clean_runtime_config(method, bundle, output_dir)
        config_path = output_dir / "runtime_config" / "CLEAN_RUNTIME_CONFIG.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(config_text, encoding="utf-8")
        exe = guard_path(
            self.paths.port_core_exe,
            role="port-core executable",
            allowed_root=self.paths.code_root,
            must_exist=True,
            regular_file=True,
        )
        command = (str(exe), "--config", str(config_path), "--output-dir", str(output_dir))
        return PreparedRun(
            method=method,
            run_id=selected_run_id,
            output_dir=output_dir,
            config_path=config_path,
            config_text=config_text,
            command=command,
            bundle=bundle,
        )

    def run(
        self,
        *,
        method: str = "basic_dual_yaw_EKF",
        run_id: str | None = None,
        timeout_seconds: int = 300,
        replace: bool = False,
    ) -> dict[str, Any]:
        try:
            code_commit_before, code_dirty_before = git_code_state(self.paths.code_root)
        except ManifestContractError as exc:
            raise CleanRunError(str(exc)) from exc
        if code_dirty_before:
            raise CleanRunError("Clean smoke requires a clean committed Git worktree")
        prepared = self.prepare(method=method, run_id=run_id, replace=replace)
        start = time.monotonic()
        try:
            completed = subprocess.run(
                list(prepared.command),
                cwd=self.paths.code_root,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            completed = subprocess.CompletedProcess(
                prepared.command,
                124,
                stdout=str(exc.stdout or ""),
                stderr=str(exc.stderr or "") + "\nclean smoke timeout",
            )
        elapsed = time.monotonic() - start
        logs = prepared.output_dir / "logs"
        logs.mkdir(exist_ok=True)
        (logs / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (logs / "stderr.txt").write_text(completed.stderr, encoding="utf-8")

        solver_manifest_path = prepared.output_dir / "RUN_MANIFEST.json"
        solver_manifest: dict[str, Any] = {}
        if solver_manifest_path.is_file():
            solver_manifest = _load_json(solver_manifest_path)
            shutil.copy2(solver_manifest_path, prepared.output_dir / "SOLVER_RUN_MANIFEST.json")

        expected_outputs = (
            prepared.output_dir / "LegSA_PORT_NAV.nav",
            prepared.output_dir / "LegSA_PORT_STD.csv",
            prepared.output_dir / "EVAL_NAV.csv",
        )
        output_issues = [path.name for path in expected_outputs if not path.is_file() or path.stat().st_size == 0]
        yaw_updates = int(solver_manifest.get("yaw_update_count") or 0)
        position_updates = int(solver_manifest.get("position_update_count") or 0)
        solver_forbidden = [
            field
            for field in ("trace_solver_input", "final_v23_output_solver_input", "output_only_correction")
            if solver_manifest.get(field) is True
        ]
        terminal_pass = (
            completed.returncode == 0
            and not output_issues
            and not solver_forbidden
            and position_updates > 0
        )
        if method == "basic_dual_yaw_EKF":
            terminal_pass = terminal_pass and yaw_updates > 0

        eval_path = prepared.output_dir / "EVAL_NAV.csv"
        eval_rows = (
            max(0, sum(1 for _ in eval_path.open("r", encoding="utf-8")) - 1)
            if eval_path.is_file()
            else 0
        )

        code_commit, code_dirty = git_code_state(self.paths.code_root)
        if code_commit != code_commit_before or code_dirty:
            terminal_pass = False
            output_issues.append("git_code_state_changed_during_run")
        manifest = {
            "schema_version": "paper-rebuild-run-manifest-v1",
            "run_id": prepared.run_id,
            "algorithm_id": method,
            "case_id": "BY2_CLEAN_SMOKE",
            "data_mode": "real_by2_raw",
            "raw_source_hashes": prepared.bundle.raw_source_hashes,
            "provider_hashes": prepared.bundle.provider_hashes,
            "provider_relpaths": prepared.bundle.provider_relpaths,
            "synthetic_data_used": False,
            "semisynthetic_data_used": False,
            "trace_used_online": False,
            "receiver_imu_as_body_imu": False,
            "final_v23_output_solver_input": False,
            "LegSA_output_solver_input": False,
            "per_case_tuning": False,
            "output_only_correction": False,
            "epoch_deleted_for_metric": False,
            "old_runtime_input_count": 0,
            "code_commit": code_commit,
            "code_worktree_dirty_at_run": code_dirty,
            "config_hash": sha256_text(prepared.config_text),
            "terminal_status": "PASS" if terminal_pass else "FAIL",
            "solver_returncode": completed.returncode,
            "runtime_seconds": round(elapsed, 6),
            "runner": "legsa_gins.paper_rebuild.runner.CleanPaperRunner",
            "runner_command_alias": "<PORT_CORE_EXE> --config <CLEAN_RUNTIME_CONFIG> --output-dir <CLEAN_SMOKE_OUTPUT>",
            "solver_manifest_file": "SOLVER_RUN_MANIFEST.json" if solver_manifest else "",
            "solver_output_issues": output_issues + [f"forbidden_solver_flag:{field}" for field in solver_forbidden],
            "source_roles_file": "source_role.json",
            "provider_lineage_file": "provider_lineage.json",
            "source_role_manifest": "source_role.json",
            "provider_lineage_manifest": "provider_lineage.json",
            "provider_generator_commit": prepared.bundle.generator_code_commit,
            "provider_generation_config_hash": prepared.bundle.generator_config_hash,
            "local_path_config_hash": prepared.bundle.local_path_config_hash,
            "solver_input_roles": ["imu_runtime_input", "gnss_runtime_input"],
            "supporting_provider_roles": [
                "dual_yaw_provider",
                "go2_attitude_prior",
                "go2_horizontal_velocity_prior",
            ],
            "metric_cross_check": {
                "namespace": "clean_smoke_runtime_health_not_paper_performance",
                "eval_nav_row_count": eval_rows,
                "position_update_count": position_updates,
                "yaw_update_count": yaw_updates,
            },
            "yaw_contract": prepared.bundle.yaw_contract,
            "paper_performance_claim": False,
        }
        assert_run_manifest(manifest)
        write_json_atomic(solver_manifest_path, manifest)
        write_json_atomic(
            prepared.output_dir / "source_role.json",
            {
                "data_mode": "real_by2_raw",
                "source_roles": prepared.bundle.source_roles,
                "trace": "evaluation_only_not_used_by_this_smoke",
                "go2_position_velocity_yaw_truth": False,
            },
        )
        write_json_atomic(
            prepared.output_dir / "provider_lineage.json",
            {
                "provider_hashes": prepared.bundle.provider_hashes,
                "provider_relpaths": prepared.bundle.provider_relpaths,
                "raw_source_hashes": prepared.bundle.raw_source_hashes,
                "yaw_contract": prepared.bundle.yaw_contract,
                "old_runtime_input_count": 0,
                "generator_code_commit": prepared.bundle.generator_code_commit,
                "generator_config_hash": prepared.bundle.generator_config_hash,
                "generator_worktree_dirty": False,
                "local_path_config_hash": prepared.bundle.local_path_config_hash,
                "solver_input_roles": ["imu_runtime_input", "gnss_runtime_input"],
            },
        )
        write_json_atomic(
            prepared.output_dir / "eval_metrics.json",
            {
                "metric_namespace": "clean_smoke_runtime_health_not_paper_performance",
                "eval_nav_row_count": eval_rows,
                "position_update_count": position_updates,
                "yaw_update_count": yaw_updates,
                "trace_evaluation_performed": False,
                "paper_performance_claim": False,
            },
        )
        status_text = "PASS\n" if terminal_pass else (
            f"FAIL returncode={completed.returncode} missing={','.join(output_issues)} "
            f"forbidden={','.join(solver_forbidden)} "
            f"position_updates={position_updates} yaw_updates={yaw_updates}\n"
        )
        (prepared.output_dir / "terminal_status.txt").write_text(status_text, encoding="utf-8")
        if not terminal_pass:
            raise CleanRunError(status_text.strip())
        return manifest
