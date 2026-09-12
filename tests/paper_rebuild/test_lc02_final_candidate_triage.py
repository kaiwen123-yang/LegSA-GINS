from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
SUFFIX = Path("paper_rebuild/horizontal_literature/lc02_final_candidate_triage/stage_payload")
CONFIG = ROOT / "configs" / SUFFIX
DOCS = ROOT / "docs" / SUFFIX
EXPECTED_START_HEAD = "27c5647abe5ab253d8a4db2b602d8682a8a63b8f"
TERMINAL = "PASS_LC02_FINAL_CANDIDATE_SELECTED_GINAV2021_OFFICIAL_LC"
GINAV = "LC02C_GINAV2021_OFFICIAL_SPP_INS_LC"
RUBRIC_SHA256 = "462e4477049df39ca3fa52cd661adadc2a3c2f7e3cd959919a7d7c2c01e1fb00"
INPUT_BOUNDARY_SHA256 = "d31543109f97b19cef3bed06c463225edf4db01f39cd064a9d30c57b072726fa"
INITIAL_EXTERNAL_STAGE_MANIFEST_SHA256 = (
    "f19010a45607a58c8b8540d610dff37c979504b22b2924f9d607111449e6d6a4"
)
# Full normalized 33-file payload manifest, including the status artifact.
# It is asserted here rather than embedded self-referentially in that payload.
FINAL_EXTERNAL_STAGE_MANIFEST_SHA256 = (
    "59ed95a57bb6065dedf7cfd19db5874905c4495b4de2543f3ee3bd07e2956afd"
)
GITATTRIBUTES_BYTES = (
    b"01_COMMON_RUBRIC/LC02_FINAL_CANDIDATE_ADMISSION_RUBRIC.yaml "
    b"whitespace=-blank-at-eof\n"
    b"01_COMMON_RUBRIC/LC02_ONLINE_INPUT_BOUNDARY.yaml "
    b"whitespace=-blank-at-eof\n"
)
CANONICAL_HASHES = {
    "scripts/paper_rebuild/run_canonical541_offline_eval_aggregate.py": (
        "00a54aac97ec54715c47dda9350635aa3ea3e969e5deb152e52e33614a6a6480"
    ),
    "src/legsa_gins/paper_rebuild/canonical541/offline_eval_aggregate.py": (
        "d021a503bc91dbd6a194182478770a1457cf0ca615c7d3adb2f7a6f68eadea16"
    ),
}
PREDECESSOR_OIDS = {
    "configs/paper_rebuild/horizontal_literature/lc02_yin2023": (
        "654ce7f3819bb6a17b606ad6a3d57f4d79d41d4e"
    ),
    "docs/paper_rebuild/horizontal_literature/lc02_yin2023": (
        "ecc6735a1cb03cd3ca8879ea72152c30e25de101"
    ),
    "configs/paper_rebuild/horizontal_literature/lc02_chang2021": (
        "3ae77bcd875951617316f02236d963660d6bacc3"
    ),
    "docs/paper_rebuild/horizontal_literature/lc02_chang2021": (
        "8337d49d0314b58be7fc1cd54367bb54cc7ea820"
    ),
}
EXPECTED_ARTIFACTS = {
    ".gitattributes",
    "00_REGISTRY/LC02_FINAL_CANDIDATE_HISTORY.md",
    "00_REGISTRY/LC02_FINAL_CANDIDATE_REGISTRY.csv",
    "00_REGISTRY/PREDECESSOR_AND_START_FREEZE.json",
    "01_COMMON_RUBRIC/LC02_FINAL_CANDIDATE_ADMISSION_RUBRIC.yaml",
    "01_COMMON_RUBRIC/LC02_FINAL_CANDIDATE_TRIAGE_PROTOCOL.md",
    "01_COMMON_RUBRIC/LC02_ONLINE_INPUT_BOUNDARY.yaml",
    "02_JIANG2021/JIANG2021_DECISION.json",
    "02_JIANG2021/JIANG2021_GATE_AUDIT.yaml",
    "02_JIANG2021/JIANG2021_SOURCE_CLOSURE_AND_DECISION.md",
    "02_JIANG2021/JIANG2021_SOURCE_REGISTRY.csv",
    "03_TAGHIZADEH2023/TAGHIZADEH2023_DECISION.json",
    "03_TAGHIZADEH2023/TAGHIZADEH2023_GATE_AUDIT.yaml",
    "03_TAGHIZADEH2023/TAGHIZADEH2023_SOURCE_CLOSURE_AND_DECISION.md",
    "03_TAGHIZADEH2023/TAGHIZADEH2023_SOURCE_REGISTRY.csv",
    "04_GINAV2021/GINAV2021_DECISION.json",
    "04_GINAV2021/GINAV2021_GATE_AUDIT.yaml",
    "04_GINAV2021/GINAV2021_HISTORICAL_ATTEMPT_CLASSIFICATION.csv",
    "04_GINAV2021/GINAV2021_OFFICIAL_ROUTE_CONTRACT.yaml",
    "04_GINAV2021/GINAV2021_SOURCE_AND_OFFICIAL_ROUTE.md",
    "04_GINAV2021/GINAV2021_SOURCE_HASH_REGISTRY.csv",
    "04_GINAV2021/GINAV2021_SOURCE_IDENTITY.json",
    "05_CROSS_CANDIDATE_DECISION/LC01_VS_FINAL_CANDIDATES_INFORMATION_STRUCTURE.csv",
    "05_CROSS_CANDIDATE_DECISION/LC02_CANDIDATE_NON_DUPLICATION_DECISIONS.csv",
    "05_CROSS_CANDIDATE_DECISION/LC02_FINAL_CANDIDATE_GATE_MATRIX.csv",
    "05_CROSS_CANDIDATE_DECISION/LC02_FINAL_CANDIDATE_RANKING_WITHOUT_PERFORMANCE.csv",
    "05_CROSS_CANDIDATE_DECISION/LC02_FINAL_SELECTION_DECISION.json",
    "05_CROSS_CANDIDATE_DECISION/LC02_FINAL_SELECTION_REPORT.md",
    "05_CROSS_CANDIDATE_DECISION/LC02_SELECTED_CANDIDATE_FUTURE_EXECUTION_GATE.yaml",
    "11_REPORT/LC02_FINAL_CANDIDATE_FORMAL_DECISION.md",
    "11_REPORT/LC02_FINAL_CANDIDATE_TRIAGE_FULL_REPORT.md",
    "11_REPORT/LC02_FINAL_CANDIDATE_TRIAGE_STATUS.json",
    "11_REPORT/ZERO_EXECUTION_AUDIT.json",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(relative: str) -> dict:
    return json.loads((CONFIG / relative).read_text(encoding="utf-8"))


def _yaml(relative: str) -> dict:
    return yaml.safe_load((CONFIG / relative).read_text(encoding="utf-8"))


def _csv(relative: str) -> list[dict[str, str]]:
    with (CONFIG / relative).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _collect_payload() -> dict[str, bytes]:
    payload: dict[str, bytes] = {}
    for root in (CONFIG, DOCS):
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            assert relative not in payload, f"duplicate stage-relative artifact: {relative}"
            payload[relative] = path.read_bytes()
    return payload


def _normalized_tree_manifest(root: Path) -> tuple[int, str]:
    records: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"symlink forbidden: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"special entry forbidden: {path}")
        records.append(f"{_sha256(path)}  {path.relative_to(root).as_posix()}\n")
    return len(records), hashlib.sha256("".join(records).encode()).hexdigest()


def _git_object(path: str) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", f"HEAD:{path}"], cwd=ROOT, text=True
    ).strip()


def test_exact_payload_scope_and_all_structured_files_parse() -> None:
    payload = _collect_payload()
    assert set(payload) == EXPECTED_ARTIFACTS
    assert len(payload) == 33
    structured_count = 0
    for relative, raw in payload.items():
        suffix = Path(relative).suffix.lower()
        if suffix == ".json":
            json.loads(raw)
            structured_count += 1
        elif suffix in {".yaml", ".yml"}:
            yaml.safe_load(raw)
            structured_count += 1
        elif suffix == ".csv":
            list(csv.DictReader(raw.decode("utf-8").splitlines()))
            structured_count += 1
        elif relative == ".gitattributes":
            assert raw == GITATTRIBUTES_BYTES
        assert suffix in {".json", ".yaml", ".csv", ".md"} or (
            relative == ".gitattributes"
        )
        assert b"/home/" not in raw and b"/mnt/" not in raw
    assert structured_count == 24
    assert not any(
        relative.lower().endswith((".pdf", ".zip", ".7z", ".mat", ".m"))
        for relative in payload
    )


def test_start_predecessors_registry_and_canonical_files_are_preserved() -> None:
    freeze = _json("00_REGISTRY/PREDECESSOR_AND_START_FREEZE.json")
    assert freeze["task_start_head"] == EXPECTED_START_HEAD
    assert freeze["tracked_worktree_clean_at_preflight"] is True
    assert freeze["index_clean_at_preflight"] is True
    assert freeze["external_stage10_absent_at_preflight"] is True
    assert freeze["tracked_predecessor_tree_oids"] == {
        "configs_lc02_yin2023": PREDECESSOR_OIDS[
            "configs/paper_rebuild/horizontal_literature/lc02_yin2023"
        ],
        "docs_lc02_yin2023": PREDECESSOR_OIDS[
            "docs/paper_rebuild/horizontal_literature/lc02_yin2023"
        ],
        "configs_lc02_chang2021": PREDECESSOR_OIDS[
            "configs/paper_rebuild/horizontal_literature/lc02_chang2021"
        ],
        "docs_lc02_chang2021": PREDECESSOR_OIDS[
            "docs/paper_rebuild/horizontal_literature/lc02_chang2021"
        ],
    }
    for path, expected in PREDECESSOR_OIDS.items():
        assert _git_object(path) == expected
    assert freeze["preserved_registry_states"] == {
        "08_LC02_YIN2023_RAEKF": "NO_GO_FORMAL_PRIMARY",
        "09_LC02_CHANG2021_FSTCKF": "NO_GO_FORMAL_PRIMARY",
        "LC01_PAVLASEK2021_TWO_RECEIVER_IEKF": "COMPLETED_ACTIVE_METHOD",
        "formal_lc02_slot": "VACANT",
    }
    rows = {row["registry_key"]: row for row in _csv("00_REGISTRY/LC02_FINAL_CANDIDATE_REGISTRY.csv")}
    assert rows["LC01"]["status"] == "COMPLETED_ACTIVE_METHOD"
    assert rows["STAGE08"]["status"] == rows["STAGE09"]["status"] == "NO_GO_FORMAL_PRIMARY"
    assert rows["FORMAL_LC02_SLOT"]["status"] == "VACANT"
    for relative, expected in CANONICAL_HASHES.items():
        path = ROOT / relative
        if path.exists():
            assert _sha256(path) == expected


def test_rubric_was_frozen_with_exact_mandatory_gates_and_tie_break() -> None:
    rubric_path = CONFIG / "01_COMMON_RUBRIC/LC02_FINAL_CANDIDATE_ADMISSION_RUBRIC.yaml"
    rubric = yaml.safe_load(rubric_path.read_text(encoding="utf-8"))
    assert rubric["frozen_before_candidate_artifacts"] is True
    assert rubric["all_gates_mandatory"] is True
    assert [row["gate"] for row in rubric["gates"]] == [f"G{i}" for i in range(1, 13)]
    assert [row["name"] for row in rubric["gates"]] == [
        "PUBLISHED_FAMILY",
        "SOLUTION_LEVEL_LC_GNSS_INS",
        "DISTINCT_FROM_LC01",
        "COMPLETE_NOMINAL_AND_MECHANIZATION",
        "PROCESS_NOISE_AND_DISCRETIZATION",
        "MEASUREMENT_AND_PHYSICAL_POINT",
        "PREDICTION_UPDATE_AND_COVARIANCE",
        "UNIQUE_ADAPTIVE_ROBUST_FADING_OR_HINF_SEMANTICS",
        "EXECUTABLE_INITIALIZATION_FEEDBACK_AND_RESET",
        "BY2_REQUIRED_FIELDS",
        "NO_REFERENCE_OR_ERROR_COMPLETION",
        "FORMAL_REPRODUCTION_LEVEL",
    ]
    assert rubric["tie_break_order"] == [
        "OFFICIAL_IMPLEMENTATION",
        "FEWER_ADAPTERS",
        "CLEARER_POINT_AND_FRAME",
        "LOWER_SOURCE_AMBIGUITY",
        "LOWER_RUNTIME_AND_DEPENDENCY_RISK",
    ]
    assert rubric["prohibited_selection_factors"] == [
        "ACCURACY",
        "PRESTIGE",
        "NOVELTY",
        "HISTORICAL_RMSE",
    ]
    status = _json("11_REPORT/LC02_FINAL_CANDIDATE_TRIAGE_STATUS.json")
    assert _sha256(rubric_path) == RUBRIC_SHA256
    assert status["initial_pre_candidate_rubric_sha256"] == RUBRIC_SHA256
    assert status["rubric_sha256"] == RUBRIC_SHA256
    boundary_path = CONFIG / "01_COMMON_RUBRIC/LC02_ONLINE_INPUT_BOUNDARY.yaml"
    assert _sha256(boundary_path) == INPUT_BOUNDARY_SHA256
    assert status["initial_pre_candidate_input_boundary_sha256"] == INPUT_BOUNDARY_SHA256
    assert status["input_boundary_sha256"] == INPUT_BOUNDARY_SHA256
    assert status["post_freeze_change"] == "NONE"
    assert status["byte_freeze_whitespace_exception"] == [
        "01_COMMON_RUBRIC/LC02_FINAL_CANDIDATE_ADMISSION_RUBRIC.yaml",
        "01_COMMON_RUBRIC/LC02_ONLINE_INPUT_BOUNDARY.yaml",
    ]


def test_byte_freeze_whitespace_exception_is_exactly_scoped() -> None:
    attributes = CONFIG / ".gitattributes"
    assert attributes.read_bytes() == GITATTRIBUTES_BYTES
    payload_paths = sorted(
        path.relative_to(ROOT).as_posix()
        for root in (CONFIG, DOCS)
        for path in root.rglob("*")
        if path.is_file()
    )
    output = subprocess.check_output(
        ["git", "check-attr", "whitespace", "--", *payload_paths],
        cwd=ROOT,
        text=True,
    )
    values: dict[str, str] = {}
    for line in output.splitlines():
        path, attribute, value = line.split(": ", 2)
        assert attribute == "whitespace"
        values[path] = value
    targets = {
        (
            CONFIG / "01_COMMON_RUBRIC/LC02_FINAL_CANDIDATE_ADMISSION_RUBRIC.yaml"
        ).relative_to(ROOT).as_posix(),
        (
            CONFIG / "01_COMMON_RUBRIC/LC02_ONLINE_INPUT_BOUNDARY.yaml"
        ).relative_to(ROOT).as_posix(),
    }
    assert {path for path, value in values.items() if value == "-blank-at-eof"} == (
        targets
    )


def test_input_boundary_allows_only_declared_sources_and_forbids_substitution() -> None:
    boundary = _yaml("01_COMMON_RUBRIC/LC02_ONLINE_INPUT_BOUNDARY.yaml")
    assert boundary["allowed_candidate_inputs"]["common"] == [
        "GO2_BODY_GYROSCOPE",
        "GO2_BODY_ACCELEROMETER",
    ]
    forbidden = set(boundary["forbidden_online_or_selection_inputs"])
    assert {
        "GO2_QUATERNION",
        "GO2_RPY",
        "GO2_ONBOARD_PVT",
        "GO2_YAW",
        "GNSS2",
        "P2_MINUS_P1",
        "DUAL_ANTENNA_YAW",
        "EXT_CARRIERS",
        "LC01_OUTPUTS",
        "HARTLEY_OUTPUTS",
        "LEGSA_OUTPUTS",
        "TRACE",
        "REFERENCE",
        "ERROR_SERIES",
    } <= forbidden
    constraints = boundary["ginav_route_constraints"]
    assert constraints["official_core_unmodified"] is True
    assert constraints["source_explicit_adapters_only"] is True
    assert constraints["official_internal_spp_ins_lc_required"] is True
    assert constraints["invented_external_pvt_forbidden"] is True


def test_candidate_gate_audits_and_cross_matrix_are_consistent() -> None:
    candidates = {
        "LC02A_JIANG2021_ADAPTIVE_FADING_CKF": "02_JIANG2021/JIANG2021_GATE_AUDIT.yaml",
        "LC02B_TAGHIZADEH2023_AHINF_CKF": "03_TAGHIZADEH2023/TAGHIZADEH2023_GATE_AUDIT.yaml",
        GINAV: "04_GINAV2021/GINAV2021_GATE_AUDIT.yaml",
    }
    allowed = {"PASS", "FAIL", "NOT_EVALUATED_SOURCE_UNAVAILABLE"}
    results: dict[str, dict[str, str]] = {}
    for candidate, relative in candidates.items():
        audit = _yaml(relative)
        assert audit["candidate_id"] == candidate
        assert [row["gate"] for row in audit["gates"]] == [f"G{i}" for i in range(1, 13)]
        result = {row["gate"]: row["result"] for row in audit["gates"]}
        assert set(result.values()) <= allowed
        summary = audit["summary"]
        assert summary["pass_count"] == sum(value == "PASS" for value in result.values())
        assert summary["fail_count"] == sum(value == "FAIL" for value in result.values())
        assert summary["not_evaluated_source_unavailable_count"] == sum(
            value == "NOT_EVALUATED_SOURCE_UNAVAILABLE" for value in result.values()
        )
        results[candidate] = result
    matrix = {row["gate"]: row for row in _csv("05_CROSS_CANDIDATE_DECISION/LC02_FINAL_CANDIDATE_GATE_MATRIX.csv")}
    assert list(matrix) == [f"G{i}" for i in range(1, 13)]
    for candidate, result in results.items():
        assert {gate: row[candidate] for gate, row in matrix.items()} == result
    assert all(value == "PASS" for value in results[GINAV].values())
    assert not all(value == "PASS" for value in results["LC02A_JIANG2021_ADAPTIVE_FADING_CKF"].values())
    assert not all(value == "PASS" for value in results["LC02B_TAGHIZADEH2023_AHINF_CKF"].values())


def test_source_identities_and_official_code_attribution_are_exact() -> None:
    identity = _json("04_GINAV2021/GINAV2021_SOURCE_IDENTITY.json")
    assert identity["official_repository"] == "https://github.com/kaichen686/GINav"
    assert identity["head_commit"] == "bc6b3ab6c40db996a4fd8e8ca5b748fe21a23666"
    assert identity["tree_oid"] == "94940c5b72c6003f696f6ed3684ee5b10875e792"
    assert identity["source_lock_policy"] == {
        "controlling_identity": "WHOLE_TREE_OID",
        "controlling_tree_oid": "94940c5b72c6003f696f6ed3684ee5b10875e792",
        "per_file_hash_registry_role": "NAMED_GATE_EVIDENCE_SUBSET",
    }
    assert identity["tag_count"] == 0
    assert identity["license"] == {
        "spdx": "BSD-2-Clause",
        "path": "LICENSE",
        "bytes": 1323,
        "sha256": "97bf25caf038104d0d74d963a2f3b4b8dffb3a8a55bef39547852204333b7504",
    }
    assert identity["manual"]["sha256"] == (
        "9a2c287f892c50b7260c5112999750c4b34e2b938506cb2736085454363c6a65"
    )
    assert identity["official_spp_ins_lc_config"]["sha256"] == (
        "6250830f6785d62e323b51b6852fc15d982ee1768f5a90f9dd031760c98c2196"
    )
    assert identity["official_sample"]["sha256"] == (
        "4758adb3f44e33cacea4b124eab3b591e723a3c722369f5fd303b3b3338bf209"
    )
    assert identity["official_sample"]["regression_executed"] is False
    hashes = {row["repository_path"]: row["sha256"] for row in _csv("04_GINAV2021/GINAV2021_SOURCE_HASH_REGISTRY.csv")}
    assert hashes["src/main_func/gi_Loose.m"] == (
        "60a3e3c6c872609e280ee9f29c555acaa49dc722d8bf093846e325ff5c0fbf1f"
    )
    assert hashes["src/gnss_ins_lc/gnss_ins_lc.m"] == (
        "2a9eec76511f8635ef71b45d84375bb200f1b58e3fb0b68ea806860ae2917b30"
    )
    assert hashes["src/gnss_ins_lc/lc_filter.m"] == (
        "9685b2d09de537d2c8f2d68a9484b8dbb8950e07e55ac9442d4b69f56ce6d7e4"
    )
    assert hashes["src/ins/ins_time_updata.m"] == (
        "ffe25393e7e1b674bb39a5b2e2ee409f4fc17e0655e7f540724a8c7f4ee39db3"
    )
    assert hashes["src/ins/update_trans_mat.m"] == (
        "1a9da235e000c59b2ac20de243ab854a6828e8a3986323893fd2dec2ea8242de"
    )
    assert hashes["src/main_func/gi_processor.m"] == (
        "3f41351876266614cd13c5cbd6726f4031a304606408e2cf2e831f01a2c8b95c"
    )
    assert hashes["src/main_func/gnss_solver.m"] == (
        "2b865a9cbda0c4a77135218fd8e0675f63cf4f3063d6d4f64b607aa0f86d1ff7"
    )
    route = _yaml("04_GINAV2021/GINAV2021_OFFICIAL_ROUTE_CONTRACT.yaml")
    assert route["core_policy"]["official_core_unmodified"] is True
    assert route["core_policy"]["external_solution_import_interface_exists"] is False
    assert route["core_policy"]["invented_external_pvt_interface_forbidden"] is True
    assert route["system_input_route"]["chain"] == ["gnss_solver", "gnss_ins_lc"]
    assert route["filter_contract"]["state_dimension"] == 15
    assert route["initialization_and_epoch_behavior"]["tdcp_motion_condition_literal"] == "dot(vn,vn)>3"
    assert route["initialization_and_epoch_behavior"]["initial_attitude_source_semantics"] == "CLOSED"
    assert route["initialization_and_epoch_behavior"]["time_and_noninteger_epoch_source_semantics"] == "CLOSED"
    assert route["initialization_and_epoch_behavior"]["runtime_activation"] == (
        "NOT_EXECUTED_FUTURE_VALIDATION"
    )


def test_selection_is_exactly_one_or_none_rule_with_exactly_one_here() -> None:
    rubric = _yaml("01_COMMON_RUBRIC/LC02_FINAL_CANDIDATE_ADMISSION_RUBRIC.yaml")
    assert rubric["allowed_terminal_outcomes"] == [
        "PASS_LC02_FINAL_CANDIDATE_SELECTED_JIANG2021",
        "PASS_LC02_FINAL_CANDIDATE_SELECTED_TAGHIZADEH2023",
        TERMINAL,
        "NO_GO_LC02_NO_REMAINING_REFERENCE_PACK_CANDIDATE_MEETS_FORMAL_REPRODUCTION",
    ]
    selection = _json("05_CROSS_CANDIDATE_DECISION/LC02_FINAL_SELECTION_DECISION.json")
    assert selection["terminal_outcome"] == TERMINAL
    assert selection["selected_candidate_id"] == GINAV
    assert selection["all_pass_candidates"] == [GINAV]
    assert selection["selection_cardinality"] == 1
    assert selection["exactly_one_selected"] is True
    assert selection["tie_break_applied"] is False
    assert selection["formal_lc02_slot"] == "VACANT"
    assert selection["formal_lc02_admission"] is False
    assert selection["candidate_selection_tier"]["selected"] is True
    assert selection["formal_primary_tier"]["formal_lc02_slot"] == "VACANT"
    decisions = [
        _json("02_JIANG2021/JIANG2021_DECISION.json"),
        _json("03_TAGHIZADEH2023/TAGHIZADEH2023_DECISION.json"),
        _json("04_GINAV2021/GINAV2021_DECISION.json"),
    ]
    assert sum(item["selected"] for item in decisions) == 1
    assert next(item for item in decisions if item["selected"])["candidate_id"] == GINAV


def test_no_performance_factor_selected_the_candidate() -> None:
    ranking = _csv(
        "05_CROSS_CANDIDATE_DECISION/"
        "LC02_FINAL_CANDIDATE_RANKING_WITHOUT_PERFORMANCE.csv"
    )
    rows = {row["candidate_id"]: row for row in ranking}
    assert rows[GINAV]["ranking_without_performance"] == "1"
    assert rows[GINAV]["all_twelve_gates_pass"] == "true"
    for candidate in (
        "LC02A_JIANG2021_ADAPTIVE_FADING_CKF",
        "LC02B_TAGHIZADEH2023_AHINF_CKF",
    ):
        assert rows[candidate]["ranking_without_performance"] == (
            "NOT_RANKED_MANDATORY_GATES_FAIL"
        )
        assert rows[candidate]["relative_performance_order"] == "NONE"
    performance_fields = {
        "tie_break_applied",
        "candidate_ranked_by_performance",
        "accuracy_used",
        "prestige_used",
        "novelty_used",
        "historical_rmse_used",
        "paper_reported_accuracy_used",
        "historical_metrics_used",
        "trace_or_reference_used",
        "performance_value_transcription",
        "performance_value_import",
        "performance_value_use",
    }
    assert all(
        row[field] == "false" for row in ranking for field in performance_fields
    )
    for relative in (
        "02_JIANG2021/JIANG2021_DECISION.json",
        "03_TAGHIZADEH2023/TAGHIZADEH2023_DECISION.json",
        "04_GINAV2021/GINAV2021_DECISION.json",
    ):
        assert _json(relative)["performance_used"] is False


def test_no_implementation_or_execution_and_future_gates_are_false() -> None:
    future = _yaml(
        "05_CROSS_CANDIDATE_DECISION/"
        "LC02_SELECTED_CANDIDATE_FUTURE_EXECUTION_GATE.yaml"
    )
    for key in (
        "formal_lc02_admission",
        "implementation_authorized",
        "synthetic_validation_authorized",
        "BY2_C00_authorized",
        "representative_cases_authorized",
        "comparison_authorized",
        "official_sample_regression_authorized",
        "matlab_execution_authorized",
        "adapter_generation_authorized",
    ):
        assert future[key] is False
    zero = _json("11_REPORT/ZERO_EXECUTION_AUDIT.json")
    assert zero["zero_execution_proved"] is True
    access = zero["source_access_counters"]
    assert (
        access[
            "historical_performance_content_incidentally_opened_during_authorized_classification"
        ]
        is True
    )
    assert access["historical_performance_file_content_open_count"] is None
    assert access["historical_performance_file_content_open_count_status"] == (
        "NOT_EXACTLY_RECONSTRUCTED"
    )
    assert access["historical_performance_used_for_selection"] is False
    assert access["historical_performance_value_transcription_count"] == 0
    assert access["historical_performance_value_import_count"] == 0
    assert access["historical_performance_value_use_count"] == 0
    assert all(value == 0 for value in zero["execution_counters"].values())
    assert all(value == 0 for value in zero["mutation_counters"].values())
    assert zero["mutation_counter_scope"] == {
        "applies_to": "BOUNDED_WORKER_ACTIONS_ONLY",
        "cutoff": "BEFORE_SUPERVISOR_FINAL_GIT_ADMINISTRATION",
        "supervisor_staging_attempt_outside_counter_scope": True,
        "future_authorized_supervisor_commit_outside_counter_scope": True,
        "worker_zero_counts_do_not_deny_supervisor_git_administration": True,
    }
    status = _json("11_REPORT/LC02_FINAL_CANDIDATE_TRIAGE_STATUS.json")
    assert status["terminal_status"] == TERMINAL
    assert status["external_stage_publication"] == (
        "GUARDED_PRECOMMIT_UNSEALED_DRAFT_CORRECTION_THEN_FINAL_PARITY"
    )
    assert status["external_stage_initial_create_once_manifest_sha256"] == (
        INITIAL_EXTERNAL_STAGE_MANIFEST_SHA256
    )
    assert status["external_stage_review_correction_occurred"] is True
    assert status["external_stage_review_correction_authorization"] == (
        "SUPERVISOR_AUTHORIZED_AFTER_READ_ONLY_REVIEW"
    )
    assert status["external_stage_payload_file_count"] == 33
    assert status["external_stage_final_parity"] is True
    assert "external_stage_sealed" not in status
    assert FINAL_EXTERNAL_STAGE_MANIFEST_SHA256 not in json.dumps(status)
    assert status["navigation_filter_run"] is False
    assert status["trace_used"] is False and status["reference_used"] is False
    assert status["ready_for_implementation"] is False
    assert status["ready_for_BY2_C00"] is False
    assert status["ready_for_comparison"] is False
    assert status["ready_for_paper_claims"] is False


def test_structural_non_duplication_files_use_no_performance() -> None:
    rows = _csv("05_CROSS_CANDIDATE_DECISION/LC02_CANDIDATE_NON_DUPLICATION_DECISIONS.csv")
    assert {row["candidate_id"] for row in rows} == {
        "LC02A_JIANG2021_ADAPTIVE_FADING_CKF",
        "LC02B_TAGHIZADEH2023_AHINF_CKF",
        GINAV,
    }
    assert all(row["structurally_distinct"] == "true" for row in rows)
    assert all(row["performance_used"] == "false" for row in rows)
    information = _csv("05_CROSS_CANDIDATE_DECISION/LC01_VS_FINAL_CANDIDATES_INFORMATION_STRUCTURE.csv")
    dimensions = {row["dimension"]: row for row in information}
    required_dimensions = {
        "number_GNSS_receivers",
        "GNSS_information_entering_fusion",
        "direct_P2_MINUS_P1_geometry",
        "state_error_representation",
        "filter_family",
        "direct_heading_information",
        "robust_adaptive_mechanism",
        "native_output",
        "failure_modes",
    }
    assert required_dimensions <= set(dimensions)
    for dimension in required_dimensions:
        assert dimensions[dimension]["LC02A_JIANG2021_ADAPTIVE_FADING_CKF"] == (
            "NOT_EVALUATED_SOURCE_UNAVAILABLE"
        )
        assert dimensions[dimension]["LC02B_TAGHIZADEH2023_AHINF_CKF"] == (
            "NOT_EVALUATED_SOURCE_UNAVAILABLE"
        )
    performance = next(row for row in information if row["dimension"] == "performance_used_for_identity")
    assert set(performance.values()) >= {"NO", "PROHIBITED"}


def test_ginav_historical_classes_and_current_static_closures_are_explicit() -> None:
    rows = _csv("04_GINAV2021/GINAV2021_HISTORICAL_ATTEMPT_CLASSIFICATION.csv")
    historical = [row for row in rows if row["record_scope"] == "HISTORICAL_ATTEMPT"]
    assert {row["class_or_topic"] for row in historical} == {
        "OLD_OFFICIAL_SOURCE_LOCK",
        "OLD_ADAPTER",
        "OLD_SAMPLE_RESULT",
        "OLD_BY2_NORMAL_RESULT",
        "OLD_120_CASE_STATUS",
        "OLD_BLOCKER",
    }
    assert len(historical) == 6
    assert all(row["commit_identity"] for row in historical)
    assert all(row["path_identity"] for row in historical)
    assert all(row["active_evidence_allowed"] == "false" for row in historical)
    assert all(
        row["performance_values_recorded_in_this_triage"] == "false"
        for row in historical
    )
    current = [row for row in rows if row["record_scope"] == "CURRENT_STATIC_CLOSURE"]
    assert {row["class_or_topic"] for row in current} == {
        "GO2_BODY_FRAME",
        "INITIAL_ATTITUDE",
        "LEVER_ARM",
        "TIME_AND_NONINTEGER_POLICY",
        "OFFICIAL_GNSS_SOLUTION_ROUTE",
        "OFFICIAL_LC_CONFIG",
    }
    assert len(current) == 6
    assert all(row["source_semantics"] == "CLOSED" for row in current)
    assert all(
        row["runtime_activation"] == "NOT_EXECUTED_FUTURE_VALIDATION"
        for row in current
    )


def test_external_static_stage_and_predecessors_when_explicitly_configured() -> None:
    explicit = os.environ.get("LEGSA_GINS_LC02_EXTERNAL_STAGE_PARENT")
    if not explicit:
        pytest.skip("LEGSA_GINS_LC02_EXTERNAL_STAGE_PARENT is unset")
    parent = Path(explicit)
    stage08 = parent / "08_LC02_YIN2023_RAEKF"
    stage09 = parent / "09_LC02_CHANG2021_FSTCKF"
    stage10 = parent / "10_LC02_FINAL_CANDIDATE_TRIAGE"
    assert _normalized_tree_manifest(stage08) == (
        79,
        "17a55c6b1f2c02fa5f06b7ccb5c0d74cb01538a03cc2aa484f76f32b37d74729",
    )
    assert _normalized_tree_manifest(stage09) == (
        37,
        "8b1dfa8bb667e2392c65b5afe4688cd02d7a4348fd1b33265af074c74ea375e2",
    )
    payload = _collect_payload()
    external = {
        path.relative_to(stage10).as_posix(): path.read_bytes()
        for path in stage10.rglob("*")
        if path.is_file()
    }
    assert external == payload
    assert _normalized_tree_manifest(stage10) == (
        33,
        FINAL_EXTERNAL_STAGE_MANIFEST_SHA256,
    )
