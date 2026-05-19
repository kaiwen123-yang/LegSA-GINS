"""N9B0B degradation runner dry-run precheck.

This module is intentionally runner-only. It reads the cleaned N9B0A2 matrix
contracts, builds dry-run registries, and writes precheck reports. It does not
generate degraded inputs, random arrays, solver outputs, evaluator outputs, or
figures.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


EXPECTED_COUNTS = {
    "full": 81,
    "family": 81,
    "pilot": 10,
    "applicability": 891,
    "seed_plan": 567,
    "runner_availability": 6,
}

MATRIX_FILES = {
    "applicability": "N9B0A_ALGORITHM_APPLICABILITY_MATRIX_CLEANED",
    "family": "N9B0A_DEGRADATION_FAMILY_MATRIX_CLEANED",
    "seed_plan": "N9B0A_RANDOM_SEED_PLAN_CLEANED",
    "runner_availability": "N9B0A_RUNNER_AVAILABILITY_MATRIX_CLEANED",
    "pilot": "N9B1_PILOT_CASE_PLAN_CLEANED",
    "full": "N9B2_FULL_DEGRADATION_MATRIX_PLAN_CLEANED",
}

RUNNER_CRITICAL_FIELDS = {
    "full": [
        "case_id",
        "family",
        "parameters",
        "deterministic_or_random",
        "random_seed",
        "random_values_required",
        "applicable_algorithms",
        "diagnostic_only_algorithms",
        "not_applicable_algorithms",
        "expected_outputs",
        "execution_status",
    ],
    "family": [
        "case_id",
        "family_code",
        "case_kind",
        "deterministic_or_random",
        "random_values_required",
        "seed_template",
        "applicable_algorithms",
        "diagnostic_only_algorithms",
        "not_applicable_algorithms",
        "execution_status",
    ],
    "pilot": [
        "pilot_case_id",
        "case_id",
        "family_code",
        "applicable_algorithms",
        "diagnostic_only_algorithms",
        "not_applicable_algorithms",
        "runner_required",
        "expected_outputs",
        "execution_status",
    ],
    "applicability": ["case_id", "family_code", "algorithm_group", "applicability", "reason"],
    "seed_plan": [
        "case_id",
        "family_code",
        "deterministic_or_random",
        "seed",
        "random_values_required",
        "array_created",
        "execution_status",
    ],
    "runner_availability": ["component", "availability", "executable", "N9B0A_status", "notes"],
}

ALLOWED_ROUTING_STATUSES = {
    "applicable",
    "diagnostic_only",
    "fixed_reference",
    "reference_only",
    "not_applicable",
    "blocked",
}

FORBIDDEN_EXECUTION_OUTPUT_NAMES = {
    "NAV",
    "STD",
    "EVAL_NAV",
    "RUN_MANIFEST",
    "FGO_FEEDBACK_OBSERVATIONS",
    "FGO_SMOOTHED_NAV",
    "FGO_FACTOR_TABLE",
}

FUTURE_RUNTIME_SUBDIRS = [
    "inputs_degraded",
    "algorithm_outputs",
    "official_eval",
    "figures",
    "case_review",
    "manifests",
    "randomness",
    "logs",
]


@dataclass(frozen=True)
class MatrixBundle:
    matrix_root: Path
    full: list[dict[str, str]]
    family: list[dict[str, str]]
    pilot: list[dict[str, str]]
    applicability: list[dict[str, str]]
    seed_plan: list[dict[str, str]]
    runner_availability: list[dict[str, str]]


@dataclass(frozen=True)
class CaseRecord:
    case_id: str
    family: str
    severity: str
    parameters: str
    deterministic_or_random: str
    random_seed: str
    random_values_required: bool
    applicable_algorithms: list[str]
    diagnostic_only_algorithms: list[str]
    not_applicable_algorithms: list[str]
    expected_perturbation: str
    expected_output_types: list[str]
    priority: str
    status: str


@dataclass(frozen=True)
class GeneratorCapability:
    generator_id: str
    family_codes: list[str]
    capability_scope: str
    interface_only: bool
    random_arrays_created: bool
    degraded_inputs_created: bool
    status: str


def discover_cleaned_matrix_root(base: Path | None = None) -> Path:
    search_root = base or Path.cwd()
    matches = sorted(search_root.glob("*/N9B0A2_VALIDATION_JSON_HYGIENE_FIX/cleaned_matrix"))
    if not matches:
        raise FileNotFoundError("cleaned_matrix root not found under workspace")
    return matches[0]


def load_json_rows(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} is not a JSON array")
    return [{str(k): _norm(v) for k, v in row.items()} for row in payload]


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [{str(k): _norm(v) for k, v in row.items()} for row in reader]


def load_matrix_bundle(matrix_root: Path | None = None) -> MatrixBundle:
    root = matrix_root or discover_cleaned_matrix_root()
    rows: dict[str, list[dict[str, str]]] = {}
    for key, stem in MATRIX_FILES.items():
        json_path = root / f"{stem}.json"
        csv_path = root / f"{stem}.csv"
        if not json_path.exists() or not csv_path.exists():
            raise FileNotFoundError(f"missing cleaned matrix pair for {key}: {stem}")
        json_rows = load_json_rows(json_path)
        csv_rows = load_csv_rows(csv_path)
        if len(json_rows) != len(csv_rows):
            raise ValueError(f"CSV/JSON row count mismatch for {key}")
        rows[key] = json_rows
    return MatrixBundle(matrix_root=root, **rows)


def validate_matrix_bundle(bundle: MatrixBundle) -> dict[str, Any]:
    issues: list[str] = []
    counts = {
        "full": len(bundle.full),
        "family": len(bundle.family),
        "pilot": len(bundle.pilot),
        "applicability": len(bundle.applicability),
        "seed_plan": len(bundle.seed_plan),
        "runner_availability": len(bundle.runner_availability),
    }
    for key, expected in EXPECTED_COUNTS.items():
        if counts[key] != expected:
            issues.append(f"{key} count {counts[key]} != expected {expected}")
    for key in MATRIX_FILES:
        for row_index, row in enumerate(getattr(bundle, key)):
            for field in RUNNER_CRITICAL_FIELDS[key]:
                if not row.get(field, "").strip():
                    issues.append(f"{key}[{row_index}] blank runner-critical field {field}")
    case_ids = [row["case_id"] for row in bundle.full]
    duplicate_ids = sorted({case_id for case_id in case_ids if case_ids.count(case_id) > 1})
    if duplicate_ids:
        issues.append(f"duplicate full matrix case_id values: {duplicate_ids}")
    issues.extend(_validate_randomness_rows(bundle.seed_plan, bundle.full))
    issues.extend(_validate_applicability_rows(bundle.applicability))
    return {
        "status": "pass" if not issues else "fail",
        "matrix_root": _display_path(bundle.matrix_root),
        "expected_counts": EXPECTED_COUNTS,
        "actual_counts": counts,
        "case_id_unique": not duplicate_ids,
        "issues": issues,
    }


def build_case_registry(bundle: MatrixBundle) -> list[CaseRecord]:
    records: list[CaseRecord] = []
    for row in bundle.full:
        records.append(
            CaseRecord(
                case_id=row["case_id"],
                family=row["family"],
                severity=row.get("severity", ""),
                parameters=row["parameters"],
                deterministic_or_random=row["deterministic_or_random"],
                random_seed=row["random_seed"],
                random_values_required=_bool(row["random_values_required"]),
                applicable_algorithms=_split_semicolon(row["applicable_algorithms"]),
                diagnostic_only_algorithms=_split_semicolon(row["diagnostic_only_algorithms"]),
                not_applicable_algorithms=_split_semicolon(row["not_applicable_algorithms"]),
                expected_perturbation=_expected_perturbation(row),
                expected_output_types=_split_semicolon(row["expected_outputs"]),
                priority=row["priority"],
                status="dryrun_registered_not_executable",
            )
        )
    return records


def build_generator_capability_matrix() -> list[GeneratorCapability]:
    specs = [
        ("gnss_outage", ["A"], "GNSS outage masks"),
        ("deterministic_downsample", ["B"], "GNSS deterministic sampling drop"),
        ("position_noise", ["C"], "GNSS position noise"),
        ("position_spike", ["D"], "GNSS position spike"),
        ("std_inflation", ["E"], "GNSS observation std inflation"),
        ("receiver_velocity", ["F"], "receiver velocity observation degradation"),
        ("raw_doppler", ["G"], "Raw Doppler observation degradation"),
        ("yaw_dropout_noise_spike_bias_std", ["H"], "dual yaw degradations"),
        ("source_aware", ["I"], "source-aware diagnostic routing"),
        ("go2_legged", ["J", "K"], "Go2 and legged source degradations"),
        ("feedback_fgo_diagnostic", ["L"], "feedback and FGO diagnostic routing"),
        ("mixed_composition", ["M"], "combined degradation composition"),
        ("normal_sanity", ["M"], "normal-condition pilot sanity mapping"),
    ]
    return [
        GeneratorCapability(
            generator_id=generator_id,
            family_codes=families,
            capability_scope=scope,
            interface_only=True,
            random_arrays_created=False,
            degraded_inputs_created=False,
            status="declared_interface_only",
        )
        for generator_id, families, scope in specs
    ]


class ApplicabilityRouter:
    def __init__(self, rows: Iterable[dict[str, str]]) -> None:
        self._map = {
            (row["case_id"], row["algorithm_group"]): (row["applicability"], row["reason"])
            for row in rows
        }

    def route(self, case_id: str, algorithm_group: str) -> dict[str, str]:
        status, reason = self._map.get(
            (case_id, algorithm_group),
            ("blocked", "case/algorithm pair absent from cleaned applicability matrix"),
        )
        if status not in ALLOWED_ROUTING_STATUSES:
            return {
                "case_id": case_id,
                "algorithm_group": algorithm_group,
                "routing_status": "blocked",
                "reason": f"unsupported applicability status {status}",
            }
        return {
            "case_id": case_id,
            "algorithm_group": algorithm_group,
            "routing_status": status,
            "reason": reason,
        }


class RandomnessManager:
    def __init__(self, seed_rows: Iterable[dict[str, str]]) -> None:
        self.seed_rows = list(seed_rows)

    def manifest_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for row in self.seed_rows:
            rows.append(
                {
                    "case_id": row["case_id"],
                    "family_code": row["family_code"],
                    "deterministic_or_random": row["deterministic_or_random"],
                    "seed": row["seed"],
                    "random_values_required": row["random_values_required"],
                    "array_created": row["array_created"],
                    "status": "metadata_only_no_random_array",
                }
            )
        return rows


class RuntimePathPlanner:
    def __init__(self, runtime_root: Path) -> None:
        self.runtime_root = runtime_root

    def planned_paths(self) -> dict[str, str]:
        return {name: _display_path(self.runtime_root / name) for name in FUTURE_RUNTIME_SUBDIRS}

    def create_report_dirs(self) -> None:
        for name in [
            "00_supervisor",
            "01_plan",
            "runner_design",
            "dryrun_precheck",
            "pilot_readiness",
            "reports",
            "matrix",
            "summary",
            "blocked_runner_items",
            "tests_runtime",
        ]:
            (self.runtime_root / name).mkdir(parents=True, exist_ok=True)


def validate_context_paths(paths: dict[str, Path | None] | None = None) -> dict[str, Any]:
    checked: dict[str, dict[str, Any]] = {}
    for name, path in (paths or {}).items():
        if path is None:
            checked[name] = {"provided": False, "exists": False, "path": ""}
            continue
        checked[name] = {
            "provided": True,
            "exists": path.exists(),
            "path": _display_path(path),
        }
    required = [name for name in ["normal_package_root", "r4e3_root", "r4j_root", "r4p_root"] if name in checked]
    missing = [name for name in required if not checked[name]["exists"]]
    return {
        "status": "pass" if not missing else "fail",
        "checked": checked,
        "missing_required_paths": missing,
    }


def build_algorithm_routing_matrix(bundle: MatrixBundle) -> list[dict[str, str]]:
    router = ApplicabilityRouter(bundle.applicability)
    rows: list[dict[str, str]] = []
    for source in bundle.applicability:
        routed = router.route(source["case_id"], source["algorithm_group"])
        rows.append(
            {
                **routed,
                "family_code": source["family_code"],
                "dryrun_only": "true",
                "not_executed": "true",
            }
        )
    return rows


def build_pilot_dryrun_matrix(bundle: MatrixBundle) -> list[dict[str, str]]:
    seed_case_ids = {row["case_id"] for row in bundle.seed_plan}
    rows: list[dict[str, str]] = []
    for row in bundle.pilot:
        random_required = row["random_value_manifest_need"] == "true"
        rows.append(
            {
                **row,
                "generator_available": "interface_only",
                "source_inputs_available": "metadata_checked",
                "randomness_required": "true" if random_required else "false",
                "seed_row_exists": "true" if row["case_id"] in seed_case_ids else "false",
                "future_random_value_output_file_planned": "true" if random_required else "false",
                "evaluator_compatible": "planned_not_executed",
                "expected_output_root": f"<N9B_RUNTIME_ROOT>/{row['case_id']}",
                "blocker": "N9B0B dry-run only; N9B1 execution requires human approval",
                "dryrun_only": "true",
                "not_executed": "true",
                "no_solver_run": "true",
                "ready_for_execution": "false",
            }
        )
    return rows


def build_blocked_runner_items(bundle: MatrixBundle) -> list[dict[str, str]]:
    blocked: list[dict[str, str]] = []
    for row in bundle.full:
        blocked.append(
            {
                "case_id": row["case_id"],
                "family": row["family"],
                "blocked_reason": "N9B0B is dryrun-only; N9B1/N9B2 execution is outside scope",
                "execution_status": "blocked_not_executed",
            }
        )
    return blocked


def validate_runtime_tree(runtime_root: Path) -> dict[str, Any]:
    forbidden_files: list[str] = []
    random_arrays: list[str] = []
    figures: list[str] = []
    if runtime_root.exists():
        for path in runtime_root.rglob("*"):
            if not path.is_file():
                continue
            name = path.name
            if any(name.startswith(prefix) for prefix in FORBIDDEN_EXECUTION_OUTPUT_NAMES):
                forbidden_files.append(_display_path(path))
            if path.suffix.lower() in {".npy", ".npz"}:
                random_arrays.append(_display_path(path))
            if path.suffix.lower() in {".png", ".pdf", ".svg", ".jpg", ".jpeg"}:
                figures.append(_display_path(path))
    issues = forbidden_files + random_arrays + figures
    return {
        "status": "pass" if not issues else "fail",
        "forbidden_execution_files": forbidden_files,
        "random_array_files": random_arrays,
        "figure_files": figures,
    }


def evaluate_safety_gate(
    bundle: MatrixBundle,
    runtime_paths: dict[str, str],
    runtime_tree: dict[str, Any] | None = None,
    generate_random_arrays: bool = False,
    generate_figures: bool = False,
    execute_full_matrix: bool = False,
) -> dict[str, Any]:
    issues: list[str] = []
    if runtime_tree and runtime_tree["status"] != "pass":
        issues.extend(runtime_tree.get("forbidden_execution_files", []))
        issues.extend(runtime_tree.get("random_array_files", []))
        issues.extend(runtime_tree.get("figure_files", []))
    text_rows = bundle.full + bundle.family + bundle.pilot + bundle.applicability
    for row in text_rows:
        joined = " ".join(row.values()).lower()
        if "historical_nominal_none" in joined:
            issues.append(f"historical_nominal_none detected in {row.get('case_id', '<unknown>')}")
    if generate_random_arrays:
        issues.append("random array generation requested")
    if generate_figures:
        issues.append("figure generation requested")
    if execute_full_matrix:
        issues.append("full matrix execution requested")
    for row in bundle.applicability:
        status = row["applicability"]
        algorithm = row["algorithm_group"]
        if algorithm == "final_v23_dual_antenna_EKF" and status != "reference_only":
            issues.append(f"final_v23 is not reference_only for {row['case_id']}")
        if algorithm == "single_antenna_gnss1_status_KF_GINS" and row["family_code"] not in {"A", "B", "C", "D", "E", "M"} and status != "not_applicable":
            issues.append(f"single_antenna forbidden case is {status}: {row['case_id']}")
        if algorithm == "pure_INS_reference_initialized" and status not in {"not_applicable", "fixed_reference"}:
            issues.append(f"pure_INS meaningless case is {status}: {row['case_id']}")
    for row in bundle.full:
        expected_outputs = set(_split_semicolon(row["expected_outputs"]))
        forbidden_solver_inputs = {"trace_solver_input", "final_v23_solver_input", "trace_as_solver_input", "final_v23_as_solver_input"}
        if expected_outputs & forbidden_solver_inputs:
            issues.append(f"forbidden solver input output marker for {row['case_id']}: {sorted(expected_outputs & forbidden_solver_inputs)}")
        if "final_v23" in row["applicable_algorithms"]:
            issues.append(f"final_v23 appears executable in applicable algorithms for {row['case_id']}")
    return {
        "status": "pass" if not issues else "fail",
        "dryrun_only": True,
        "not_executed": True,
        "no_solver_run": True,
        "no_random_arrays": not generate_random_arrays,
        "no_figures": not generate_figures,
        "ready_for_N9B_execution": False,
        "future_runtime_paths_planned_only": runtime_paths,
        "runtime_tree": runtime_tree or {"status": "not_checked"},
        "forbidden_execution_output_names": sorted(FORBIDDEN_EXECUTION_OUTPUT_NAMES),
        "issues": issues,
    }


def run_dryrun_precheck(
    matrix_root: Path | None = None,
    runtime_root: Path | None = None,
    write_outputs: bool = False,
    context_paths: dict[str, Path | None] | None = None,
) -> dict[str, Any]:
    bundle = load_matrix_bundle(matrix_root)
    validation = validate_matrix_bundle(bundle)
    case_registry = build_case_registry(bundle)
    generator_matrix = build_generator_capability_matrix()
    routing_matrix = build_algorithm_routing_matrix(bundle)
    pilot_matrix = build_pilot_dryrun_matrix(bundle)
    blocked_items = build_blocked_runner_items(bundle)
    planner = RuntimePathPlanner(runtime_root or Path("N9B0B_DEGRADATION_RUNNER_IMPLEMENTATION_AND_DRYRUN_PRECHECK"))
    if write_outputs:
        planner.create_report_dirs()
    runtime_paths = planner.planned_paths()
    source_path_validation = validate_context_paths(context_paths)
    safety_gate = evaluate_safety_gate(bundle, runtime_paths, validate_runtime_tree(planner.runtime_root))
    implementation_report = {
        "stage": "N9B0B_DEGRADATION_RUNNER_IMPLEMENTATION_AND_DRYRUN_PRECHECK",
        "runner_only": True,
        "interface_only": True,
        "matrix_loader": "cleaned_csv_json",
        "case_registry_count": len(case_registry),
        "generator_capability_count": len(generator_matrix),
        "degraded_inputs_created": False,
        "random_arrays_created": False,
        "solver_run": False,
        "figure_generation": False,
        "source_path_validation": source_path_validation,
        "ready_for_N9B_execution": False,
    }
    dryrun_report = {
        "stage": implementation_report["stage"],
        "dryrun_only": True,
        "not_executed": True,
        "no_solver_run": True,
        "source_matrix_validation": validation,
        "case_registry_rows": len(case_registry),
        "algorithm_routing_rows": len(routing_matrix),
        "pilot_dryrun_rows": len(pilot_matrix),
        "blocked_runner_items": len(blocked_items),
        "source_path_validation": source_path_validation,
        "ready_for_N9B_execution": False,
    }
    pilot_readiness = {
        "stage": implementation_report["stage"],
        "pilot_case_count": len(bundle.pilot),
        "ready_for_N9B_planning": validation["status"] == "pass" and safety_gate["status"] == "pass",
        "ready_for_N9B1_pilot": validation["status"] == "pass" and safety_gate["status"] == "pass",
        "ready_for_N9B_execution": False,
        "reason": "N9B0B validates dry-run mappings only; N9B1 execution remains blocked pending human approval",
        "pilot_cases": [row["case_id"] for row in bundle.pilot],
    }
    passed = validation["status"] == "pass" and safety_gate["status"] == "pass" and source_path_validation["status"] == "pass"
    decision = {
        "stage": implementation_report["stage"],
        "status": "N9B0B_degradation_runner_implementation_ready_for_N9B1_pilot" if passed else "N9B0B_safety_gate_failed",
        "ready_for_N9B_planning": passed,
        "ready_for_N9B1_pilot": passed,
        "ready_for_N9B_execution": False,
        "recommended_next_stage": (
            "human_review_N9B0B_then_N9B1_pilot_execution"
            if passed
            else "repair_safety_violation"
        ),
        "forbidden_actions_confirmed": [
            "no_solver_run",
            "no_official_evaluator_on_degradation_outputs",
            "no_random_array_generation",
            "no_degraded_input_generation",
            "no_figures",
            "no_NAV_STD_EVAL_RUN_MANIFEST_generation",
        ],
    }
    result = {
        "bundle": bundle,
        "validation": validation,
        "case_registry": [asdict(row) for row in case_registry],
        "generator_capability_matrix": [asdict(row) for row in generator_matrix],
        "algorithm_routing_matrix": routing_matrix,
        "pilot_dryrun_matrix": pilot_matrix,
        "blocked_runner_items": blocked_items,
        "implementation_report": implementation_report,
        "dryrun_precheck_report": dryrun_report,
        "pilot_readiness_report": pilot_readiness,
        "safety_gate_report": safety_gate,
        "decision_report": decision,
    }
    if write_outputs:
        write_precheck_outputs(runtime_root=planner.runtime_root, result=result)
    return result


def write_precheck_outputs(runtime_root: Path, result: dict[str, Any]) -> None:
    RuntimePathPlanner(runtime_root).create_report_dirs()
    report_dir = runtime_root / "reports"
    matrix_dir = runtime_root / "matrix"
    summary_dir = runtime_root / "summary"
    reports = {
        "N9B0B_RUNNER_IMPLEMENTATION_REPORT.json": result["implementation_report"],
        "N9B0B_DRYRUN_PRECHECK_REPORT.json": result["dryrun_precheck_report"],
        "N9B0B_N9B1_PILOT_READINESS_REPORT.json": result["pilot_readiness_report"],
        "N9B0B_SAFETY_GATE_REPORT.json": result["safety_gate_report"],
        "N9B0B_DECISION_REPORT.json": result["decision_report"],
    }
    matrices = {
        "N9B0B_CASE_REGISTRY": result["case_registry"],
        "N9B0B_GENERATOR_CAPABILITY_MATRIX": result["generator_capability_matrix"],
        "N9B0B_ALGORITHM_ROUTING_MATRIX": result["algorithm_routing_matrix"],
        "N9B0B_N9B1_PILOT_DRYRUN_MATRIX": result["pilot_dryrun_matrix"],
        "N9B0B_BLOCKED_RUNNER_ITEMS": result["blocked_runner_items"],
    }
    for name, payload in reports.items():
        _write_json(report_dir / name, payload)
    for stem, rows in matrices.items():
        _write_json(matrix_dir / f"{stem}.json", rows)
        _write_csv(matrix_dir / f"{stem}.csv", rows)
    summaries = {
        "n9b0b_runner_architecture.md": _architecture_summary(result),
        "n9b0b_dryrun_precheck.md": _dryrun_summary(result),
        "n9b0b_n9b1_pilot_readiness.md": _pilot_summary(result),
        "n9b0b_next_stage_recommendation.md": _recommendation_summary(result),
    }
    for name, text in summaries.items():
        (summary_dir / name).write_text(text, encoding="utf-8")


def _validate_randomness_rows(seed_rows: list[dict[str, str]], full_rows: list[dict[str, str]]) -> list[str]:
    issues: list[str] = []
    random_cases = {row["case_id"] for row in full_rows if row["deterministic_or_random"] == "random"}
    deterministic_cases = {row["case_id"] for row in full_rows if row["deterministic_or_random"] == "deterministic"}
    by_case: dict[str, list[dict[str, str]]] = {}
    for row in seed_rows:
        by_case.setdefault(row["case_id"], []).append(row)
        if row["array_created"] != "false":
            issues.append(f"random array already created for {row['case_id']} seed {row['seed']}")
    for case_id in deterministic_cases:
        for row in by_case.get(case_id, []):
            if row["seed"] != "none" or row["random_values_required"] != "false":
                issues.append(f"deterministic randomness rule violation for {case_id}")
    for case_id in random_cases:
        seeds = sorted(row["seed"] for row in by_case.get(case_id, []))
        if seeds != [str(i) for i in range(10)]:
            issues.append(f"random seed reservation is not 0..9 for {case_id}: {seeds}")
        for row in by_case.get(case_id, []):
            if row["random_values_required"] != "true":
                issues.append(f"random case missing random_values_required=true for {case_id}")
    return issues


def _validate_applicability_rows(rows: list[dict[str, str]]) -> list[str]:
    issues: list[str] = []
    for row in rows:
        status = row["applicability"]
        if status not in ALLOWED_ROUTING_STATUSES:
            issues.append(f"unsupported applicability {status} for {row['case_id']} {row['algorithm_group']}")
    return issues


def _expected_perturbation(row: dict[str, str]) -> str:
    return f"family={row['family']}; parameters={row['parameters']}; generator_interface_only=true"


def _split_semicolon(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def _bool(value: str) -> bool:
    return value.strip().lower() == "true"


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _display_path(path: Path) -> str:
    raw = str(path)
    cwd = Path.cwd()
    try:
        return str(path.resolve().relative_to(cwd.resolve()))
    except ValueError:
        pass
    drive = cwd.drive[:1].lower()
    wsl_audit_root = ""
    if drive:
        wsl_audit_root = "/mnt/" + drive + str(cwd)[2:].replace("\\", "/")
    alias_prefixes = [
        (str(cwd), "<WINDOWS_AUDIT_ROOT>"),
        (wsl_audit_root, "<WSL_AUDIT_ROOT>"),
    ]
    normalized = raw.replace("/", "\\")
    repo_marker = "\\KF-GINS"
    if normalized.lower().startswith(("\\" + "\\" + "wsl").lower()):
        marker_index = normalized.lower().find(repo_marker.lower())
        if marker_index >= 0:
            suffix = normalized[marker_index + len(repo_marker) :].replace("\\", "/")
            return "<WSL_ALGO_REPO>" + suffix
    if raw.startswith("/" + "home" + "/"):
        posix_marker = "/" + "KF-GINS"
        marker_index = raw.find(posix_marker)
        if marker_index >= 0:
            suffix = raw[marker_index + len(posix_marker) :].replace("\\", "/")
            return "<WSL_ALGO_REPO>" + suffix
    for prefix, alias in alias_prefixes:
        normalized_prefix = prefix.replace("/", "\\")
        if normalized.lower().startswith(normalized_prefix.lower()):
            suffix = raw[len(prefix) :].replace("\\", "/")
            return alias + suffix
    return raw


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _architecture_summary(result: dict[str, Any]) -> str:
    return (
        "# N9B0B runner architecture\n\n"
        "- Scope: runner-only dry-run precheck.\n"
        "- Matrix loader: cleaned N9B0A2 CSV/JSON pairs.\n"
        f"- Case registry rows: {len(result['case_registry'])}.\n"
        f"- Generator capability rows: {len(result['generator_capability_matrix'])}.\n"
        "- Degradation generators are interface-only and create no arrays or inputs.\n"
        "- Runtime path planner lists future subdirs only; no case output roots are created.\n"
        "- ready_for_N9B_execution=false.\n"
    )


def _dryrun_summary(result: dict[str, Any]) -> str:
    validation = result["validation"]
    return (
        "# N9B0B dry-run precheck\n\n"
        f"- Validation status: {validation['status']}.\n"
        f"- Counts: {validation['actual_counts']}.\n"
        "- dryrun_only=true; not_executed=true; no_solver_run=true.\n"
        "- No NAV/STD/EVAL_NAV/RUN_MANIFEST/random arrays/figures are generated.\n"
        "- ready_for_N9B_execution=false.\n"
    )


def _pilot_summary(result: dict[str, Any]) -> str:
    report = result["pilot_readiness_report"]
    return (
        "# N9B1 pilot readiness\n\n"
        f"- Pilot dry-run rows: {report['pilot_case_count']}.\n"
        "- Pilot execution remains blocked in N9B0B.\n"
        f"- Reason: {report['reason']}.\n"
        "- ready_for_N9B_execution=false.\n"
    )


def _recommendation_summary(result: dict[str, Any]) -> str:
    decision = result["decision_report"]
    return (
        "# N9B0B next stage recommendation\n\n"
        f"- Decision status: {decision['status']}.\n"
        f"- Recommended next stage: {decision['recommended_next_stage']}.\n"
        "- Human approval is required before N9B1 pilot execution.\n"
        "- ready_for_N9B_execution=false.\n"
    )
