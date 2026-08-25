from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.config_contract import (
    allan_psd_mapping,
    derive_by2_config,
    lever_frd_to_rfu,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.constants import (
    LEVER_FRD_M,
    LEVER_RFU_M,
    OFFICIAL_CONFIG_RELATIVE,
    OFFICIAL_POS_COLUMNS,
    POOR_APPLICABILITY_STATUS,
    STANDARD_NAV_COLUMNS,
    STAGE_NAME,
    SUCCESS_STATUS,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.outputs import (
    OfficialSolutionRow,
    OutputContractError,
    formal_admission,
    freeze_native_solution,
    standard_nav_row,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.publication import (
    FINAL_STATUS_RELATIVE,
    PARITY_RELATIVE,
    PublicationError,
    _guarded_atomic_rename,
    _replace_aliases,
    compact_artifact_paths,
    publish_compact_stage,
    validate_exact_destination,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.source import (
    AccessLedger,
    ForbiddenInputError,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.transaction import (
    TransactionError,
    _activation_terminal,
    _create_stage_layout,
    _finalize_terminal,
    _make_scratch_root,
    _write_cleanliness,
    _zero_native_output_terminal,
)


REPOSITORY = Path(__file__).resolve().parents[2]
TDCP_TERMINAL = "UNSUPPORTED_LC02_GINAV_BY2_TDCP_ALIGNMENT_CONDITION_NOT_MET"


def _official_root() -> Path:
    value = os.environ.get("LEGSAGINS_GINAV_ROOT")
    if not value:
        pytest.skip("LEGSAGINS_GINAV_ROOT is required for pinned-config tests")
    return Path(value).expanduser().resolve(strict=True)


def _provenance() -> dict[str, object]:
    return {
        "schema_version": "ginav2021.consolidated_provenance.v1",
        "data_mode": "real_by2_raw",
        "dataset_role": "REAL_BY2_NATIVE_INPUT_ADAPTER_AND_C00",
        "raw_source_hashes": {"raw": "a" * 64},
        "provider_hashes": {"provider": "b" * 64},
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
        "code_commit": "c" * 40,
        "config_hash": "d" * 64,
        "gate_execution_counts": {
            "G0_matlab_candidate_attempts": 1,
            "G1_official_sample_runs": 2,
            "G2_gnss_adapter_runs": 1,
            "G2_imu_adapter_runs": 1,
            "G3_tdcp_probe_runs": 1,
            "G4_BY2_C00_runs": 0,
        },
    }


def _clean_audit() -> dict[str, object]:
    return {
        "pass": True,
        "trace_open_count": 0,
        "reference_open_count": 0,
        "gnss2_open_count": 0,
        "other_method_open_count": 0,
        "forbidden_open_count": 0,
        "unauthorized_runtime_read_count": 0,
        "records": [],
    }


def _publication_roots(tmp_path: Path) -> dict[str, Path]:
    roots = {
        name: tmp_path / name
        for name in ("scratch", "clean", "raw", "code", "paper", "legacy")
    }
    for root in roots.values():
        root.mkdir()
    stage = _create_stage_layout(roots["scratch"])
    parent = (
        roots["clean"] / "stages"
        / "CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON"
    )
    parent.mkdir(parents=True)
    roots["stage"] = stage
    roots["destination"] = parent / STAGE_NAME
    return roots


def _write_minimum_publication_evidence(
    stage: Path, *, terminal: str = TDCP_TERMINAL
) -> dict[str, object]:
    status = {
        "terminal_status": terminal,
        "scientific_terminal_status": terminal,
        "artifact_publication": "PENDING",
        "transaction_complete": False,
        "scratch_stage_root": str(stage),
    }
    (stage / FINAL_STATUS_RELATIVE).write_text(
        json.dumps(status) + "\n", encoding="utf-8"
    )
    (stage / "11_REPORT/GINAV_FORBIDDEN_INPUT_AUDIT.json").write_text(
        json.dumps(_clean_audit()) + "\n", encoding="utf-8"
    )
    (stage / "11_REPORT/GINAV_CONSOLIDATED_PROVENANCE.json").write_text(
        json.dumps(_provenance()) + "\n", encoding="utf-8"
    )
    return status


def test_by2_config_allowlist_lever_and_allan_psd(tmp_path: Path) -> None:
    data = tmp_path / "runtime"
    data.mkdir()
    destination = tmp_path / "BY2.ini"
    contract = derive_by2_config(
        _official_root() / OFFICIAL_CONFIG_RELATIVE,
        destination,
        data_directory=data,
        site_name="by2_gnss1",
        start_time_gpst=dt.datetime(2022, 1, 1, 0, 0, 0),
        end_time_gpst=dt.datetime(2022, 1, 1, 0, 2, 0),
        navsys="G",
        nfreq=1,
        project_repository_root=REPOSITORY,
    )
    assert set(contract["actual_changed_fields"]).issubset(
        set(contract["allowed_change_fields"])
    )
    assert contract["gnss_mode"] == 1 and contract["ins_mode"] == 1
    assert contract["official_robust_path_unchanged"] is True
    assert contract["initial_state_uncertainties_unchanged"] is True
    assert contract["imu_data_format"] == 2
    assert lever_frd_to_rfu(LEVER_FRD_M) == LEVER_RFU_M
    assert contract["lever"]["quality"] == "ROUGH_ENGINEERING_LEVER"
    assert contract["lever"]["trace_tuned"] is False
    allan = allan_psd_mapping(REPOSITORY)
    assert allan["mapping_rule"] == "square_each_continuous_ASD_exactly_once"
    assert allan["sqrt_dt_preprocessing"] is False
    assert allan["user_thesis_opened_by_this_route"] is False
    assert len(allan["project_parameter_source_hashes_verified"]) == 2


def _finite_q5_row() -> OfficialSolutionRow:
    values = [0.0] * len(OFFICIAL_POS_COLUMNS)
    values[0] = 2200
    values[1] = 100.0
    values[2:5] = [4_000_000.0, 1_000_000.0, 4_800_000.0]
    values[5] = 5
    values[6] = 8
    values[7:13] = [1.0] * 6
    values[15:18] = [1.0, 2.0, 3.0]
    values[18:24] = [0.1] * 6
    values[24:27] = [1.0, 2.0, 3.0]
    values[27:33] = [0.2] * 6
    return OfficialSolutionRow(tuple(values))


def test_standard_output_schema_is_source_and_frame_derived() -> None:
    row = standard_nav_row(_finite_q5_row())
    assert tuple(row) == STANDARD_NAV_COLUMNS
    assert row["status_name"] == "SPP"
    assert row["lc_update"] is True
    assert row["velocity_north_ned_mps"] == row["velocity_north_mps"]
    assert row["velocity_down_ned_mps"] == -row["velocity_up_mps"]


def test_formal_admission_routes_no_q5_all_nonfinite_and_finite_q5() -> None:
    no_q5 = formal_admission(
        {
            "row_count": 10,
            "internal_spp_fed_lc_update_count": 0,
            "finite_state_rate": 1.0,
            "finite_covariance_rate": 1.0,
            "finite_lc_update_count": 0,
        },
        process_returncode=0,
    )
    assert no_q5["terminal_status"] == (
        "UNSUPPORTED_LC02_GINAV_BY2_INSUFFICIENT_INTERNAL_SPP"
    )

    all_nonfinite = formal_admission(
        {
            "row_count": 10,
            "internal_spp_fed_lc_update_count": 2,
            "finite_state_rate": 0.0,
            "finite_covariance_rate": 0.0,
            "finite_lc_update_count": 0,
        },
        process_returncode=0,
    )
    assert all_nonfinite["terminal_status"] == POOR_APPLICABILITY_STATUS
    assert all_nonfinite["formal_lc02_admission"] is False
    assert all_nonfinite["BY2_C00_complete"] is True

    admitted = formal_admission(
        {
            "row_count": 10,
            "internal_spp_fed_lc_update_count": 2,
            "finite_state_rate": 1.0,
            "finite_covariance_rate": 1.0,
            "finite_lc_update_count": 1,
        },
        process_returncode=0,
    )
    assert admitted["terminal_status"] == SUCCESS_STATUS
    assert admitted["formal_lc02_admission"] is True

    partial = formal_admission(
        {
            "row_count": 10,
            "internal_spp_fed_lc_update_count": 2,
            "finite_state_rate": 0.9,
            "finite_covariance_rate": 1.0,
            "finite_lc_update_count": 1,
        },
        process_returncode=0,
    )
    assert partial["terminal_status"] == POOR_APPLICABILITY_STATUS
    assert partial["formal_lc02_admission"] is True


def test_formal_admission_rejects_nonzero_process_returncode() -> None:
    with pytest.raises(OutputContractError, match="zero MATLAB process"):
        formal_admission(
            {
                "row_count": 1,
                "internal_spp_fed_lc_update_count": 1,
                "finite_state_rate": 1.0,
                "finite_covariance_rate": 1.0,
                "finite_lc_update_count": 1,
            },
            process_returncode=1,
        )


def test_native_summary_and_freeze_carry_required_provenance(tmp_path: Path) -> None:
    native = tmp_path / "source.pos"
    native.write_text(
        " ".join(format(value, ".12g") for value in _finite_q5_row().values) + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "native"
    normalized = tmp_path / "normalized"
    summary = freeze_native_solution(
        native,
        output,
        matlab_result={
            "returncode": 0,
            "runtime_seconds": 1.0,
            "stdout": "",
            "stderr": "",
        },
        input_counts={"input_gnss_epoch_count": 1},
        provenance=_provenance(),
        normalization_root=normalized,
    )
    freeze = json.loads(
        (output / "GINAV_BY2_C00_NATIVE_FREEZE.json").read_text(encoding="utf-8")
    )
    for payload in (summary, freeze):
        assert payload["data_mode"] == "real_by2_raw"
        assert payload["synthetic_data_used"] is False
        assert payload["trace_used_online"] is False
        assert payload["old_runtime_input_count"] == 0
        assert payload["code_commit"] == "c" * 40
        assert payload["config_hash"] == "d" * 64


def test_zero_native_output_after_g3_is_fail_closed() -> None:
    assert _zero_native_output_terminal() == (
        "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE"
    )


def test_activation_terminal_routing_is_source_literal_and_fail_closed() -> None:
    base = {
        "internal_spp_valid_epoch_count": 2,
        "spp_pair_available_epoch_count": 1,
        "official_tdcp_flag_count": 1,
        "threshold_pass_count": 1,
        "alignment_activated": True,
    }
    assert _activation_terminal(base) is None
    assert _activation_terminal(
        {**base, "spp_pair_available_epoch_count": 0}
    )[0] == "UNSUPPORTED_LC02_GINAV_BY2_INSUFFICIENT_INTERNAL_SPP"
    assert _activation_terminal(
        {**base, "threshold_pass_count": 0}
    )[0] == "UNSUPPORTED_LC02_GINAV_BY2_TDCP_ALIGNMENT_CONDITION_NOT_MET"
    assert _activation_terminal(
        {**base, "alignment_activated": False}
    )[0] == "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE"


def test_forbidden_path_audit_rejects_other_methods_and_reference(tmp_path: Path) -> None:
    ledger = AccessLedger()
    for name in ("GNSS2.csv", "trace.csv", "Canonical-541.csv", "LC01.pos"):
        with pytest.raises(ForbiddenInputError):
            ledger.record(tmp_path / name, role="candidate_input")
    assert not ledger.records


def test_compact_publication_is_exact_self_contained_and_path_aliased(
    tmp_path: Path,
) -> None:
    roots = _publication_roots(tmp_path)
    stage = roots["stage"]
    status = _write_minimum_publication_evidence(stage)
    runtime = stage / "01_OFFICIAL_SAMPLE_REGRESSION/pristine_run_1/sample_data"
    runtime.mkdir(parents=True)
    (runtime / "sample.19o").write_text("runtime", encoding="ascii")

    selected = compact_artifact_paths(stage, terminal_status=TDCP_TERMINAL)
    assert {path.relative_to(stage) for path in selected} == {
        FINAL_STATUS_RELATIVE,
        Path("11_REPORT/GINAV_FORBIDDEN_INPUT_AUDIT.json"),
        Path("11_REPORT/GINAV_CONSOLIDATED_PROVENANCE.json"),
    }
    report = publish_compact_stage(
        stage,
        roots["destination"],
        terminal_status=TDCP_TERMINAL,
        final_status_payload=status,
        expected_destination_stage_root=roots["destination"],
        clean_root=roots["clean"],
        protected_roots=(
            roots["code"], roots["clean"], roots["raw"], roots["paper"],
            roots["legacy"],
        ),
        path_aliases={tmp_path: "<TEST_ROOT>"},
    )
    assert report["pass"] is True
    destination = roots["destination"]
    assert not (destination / "01_OFFICIAL_SAMPLE_REGRESSION/pristine_run_1").exists()
    published_status = json.loads(
        (destination / FINAL_STATUS_RELATIVE).read_text(encoding="utf-8")
    )
    assert published_status["artifact_publication"] == "COMPLETE"
    assert published_status["transaction_complete"] is True
    published_provenance = json.loads(
        (destination / "11_REPORT/GINAV_CONSOLIDATED_PROVENANCE.json")
        .read_text(encoding="utf-8")
    )
    assert published_provenance["artifact_publication"] == "COMPLETE"
    assert published_provenance["transaction_complete"] is True
    parity = json.loads((destination / PARITY_RELATIVE).read_text(encoding="utf-8"))
    paths = {row["relative_path"] for row in parity["files"]}
    assert FINAL_STATUS_RELATIVE.as_posix() in paths
    assert PARITY_RELATIVE.as_posix() not in paths
    for row in parity["files"]:
        content = (destination / row["relative_path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == row["prepared_destination_sha256"]
    published_text = "".join(
        path.read_text(encoding="utf-8")
        for path in destination.rglob("*") if path.is_file()
    )
    assert str(tmp_path) not in published_text


def test_publication_rejects_unallowlisted_evidence_and_source_symlinks(
    tmp_path: Path,
) -> None:
    roots = _publication_roots(tmp_path)
    stage = roots["stage"]
    _write_minimum_publication_evidence(stage)
    unknown = stage / "11_REPORT/REPORT.json"
    unknown.write_text("{}\n", encoding="utf-8")
    with pytest.raises(PublicationError, match="not allowlisted"):
        compact_artifact_paths(stage, terminal_status=TDCP_TERMINAL)
    unknown.unlink()

    target = tmp_path / "outside.json"
    target.write_text("{}\n", encoding="utf-8")
    link = stage / "00_SOURCE_AND_ENVIRONMENT/GINAV_SOURCE_LOCK.json"
    link.symlink_to(target)
    with pytest.raises(PublicationError, match="symlink"):
        compact_artifact_paths(stage, terminal_status=TDCP_TERMINAL)


@pytest.mark.parametrize("leaf", (STAGE_NAME, STAGE_NAME + ".partial"))
def test_publication_rejects_dangling_destination_symlink(
    tmp_path: Path, leaf: str
) -> None:
    roots = _publication_roots(tmp_path)
    stage = roots["stage"]
    status = _write_minimum_publication_evidence(stage)
    protected_leaf = roots["destination"].with_name(leaf)
    protected_leaf.symlink_to(tmp_path / "missing-target")
    with pytest.raises(PublicationError, match="destination|symlink|partial"):
        publish_compact_stage(
            stage,
            roots["destination"],
            terminal_status=TDCP_TERMINAL,
            final_status_payload=status,
            expected_destination_stage_root=roots["destination"],
            clean_root=roots["clean"],
            protected_roots=(
                roots["code"], roots["clean"], roots["raw"], roots["paper"],
                roots["legacy"],
            ),
            path_aliases={tmp_path: "<TEST_ROOT>"},
        )


def test_destination_identity_and_protected_source_are_fail_closed(
    tmp_path: Path,
) -> None:
    roots = _publication_roots(tmp_path)
    wrong = roots["destination"].with_name("wrong")
    with pytest.raises(PublicationError, match="exact authorized stage"):
        validate_exact_destination(
            wrong,
            expected_destination=roots["destination"],
            clean_root=roots["clean"],
            other_protected_roots=(
                roots["code"], roots["raw"], roots["paper"], roots["legacy"]
            ),
        )

    protected_stage = _create_stage_layout(roots["code"])
    status = _write_minimum_publication_evidence(protected_stage)
    with pytest.raises(PublicationError, match="inside protected root"):
        publish_compact_stage(
            protected_stage,
            roots["destination"],
            terminal_status=TDCP_TERMINAL,
            final_status_payload=status,
            expected_destination_stage_root=roots["destination"],
            clean_root=roots["clean"],
            protected_roots=(
                roots["code"], roots["clean"], roots["raw"], roots["paper"],
                roots["legacy"],
            ),
            path_aliases={tmp_path: "<TEST_ROOT>"},
        )

    raw_stage = _create_stage_layout(roots["raw"])
    raw_status = _write_minimum_publication_evidence(raw_stage)
    with pytest.raises(PublicationError, match="inside protected root"):
        publish_compact_stage(
            raw_stage,
            roots["destination"],
            terminal_status=TDCP_TERMINAL,
            final_status_payload=raw_status,
            expected_destination_stage_root=roots["destination"],
            clean_root=roots["clean"],
            protected_roots=(
                roots["code"], roots["clean"], roots["raw"], roots["paper"],
                roots["legacy"],
            ),
            path_aliases={tmp_path: "<TEST_ROOT>"},
        )


def test_scratch_rejects_protected_root_and_symlinked_ancestor(
    tmp_path: Path,
) -> None:
    protected = tmp_path / "code"
    protected.mkdir()
    with pytest.raises(TransactionError, match="inside protected root"):
        _make_scratch_root(
            protected / "runtime", protected_roots=(protected,)
        )

    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    with pytest.raises(TransactionError, match="inside protected root"):
        _make_scratch_root(
            raw_root / "runtime", protected_roots=(protected, raw_root)
        )

    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(TransactionError, match="symlinked path component"):
        _make_scratch_root(
            linked_parent / "runtime", protected_roots=(protected,)
        )


def test_destination_rejects_symlinked_ancestor(tmp_path: Path) -> None:
    clean = tmp_path / "real-clean"
    clean.mkdir()
    linked_clean = tmp_path / "linked-clean"
    linked_clean.symlink_to(clean, target_is_directory=True)
    destination = (
        linked_clean / "stages"
        / "CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON" / STAGE_NAME
    )
    with pytest.raises(PublicationError, match="symlinked path component"):
        validate_exact_destination(
            destination,
            expected_destination=destination,
            clean_root=linked_clean,
            other_protected_roots=(),
        )


def test_guarded_atomic_fallback_never_overwrites_existing_destination(
    tmp_path: Path,
) -> None:
    source = tmp_path / "prepared"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    (source / "new").write_text("new", encoding="ascii")
    (destination / "old").write_text("old", encoding="ascii")
    with pytest.raises(PublicationError, match="existing destination"):
        _guarded_atomic_rename(source, destination)
    assert (source / "new").read_text(encoding="ascii") == "new"
    assert (destination / "old").read_text(encoding="ascii") == "old"
    assert not (tmp_path / ".destination.publish.lock").exists()


def test_publication_aliases_drive_and_wsl_path_forms(tmp_path: Path) -> None:
    mounted = Path("/") / "mnt" / "q" / "evidence"
    assert _replace_aliases(
        "Q:\\evidence\\status.json", {mounted: "<STAGE_ROOT>"}
    ) == "<STAGE_ROOT>\\status.json"
    linux_path = tmp_path / "evidence"
    windows_unc = (
        "\\\\wsl.localhost\\TestDistribution"
        + str(linux_path).replace("/", "\\")
        + "\\status.json"
    )
    assert _replace_aliases(
        windows_unc, {linux_path: "<SCRATCH_ROOT>"}
    ) == "<SCRATCH_ROOT>\\status.json"


def test_cleanliness_aggregate_recovers_failed_candidate_proof(
    tmp_path: Path,
) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    stage = _create_stage_layout(scratch)
    candidate = stage / "00_SOURCE_AND_ENVIRONMENT/matlab_probe_runtime_candidate_1"
    candidate.mkdir()
    proof = {
        "schema_version": "ginav2021.core_cleanliness_before_after.v1",
        "run_id": "G0_MATLAB_ENVIRONMENT_candidate_1",
        "pass": True,
    }
    (candidate / "GINAV_CORE_CLEANLINESS_BEFORE_AFTER.json").write_text(
        json.dumps(proof) + "\n", encoding="utf-8"
    )
    runs: list[dict[str, object]] = []
    aggregate_path = _write_cleanliness(stage, runs)
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    assert runs == [proof]
    assert aggregate["run_count"] == 1
    assert aggregate["runs"][0]["run_id"].endswith("candidate_1")


def test_publication_failure_preserves_allowed_terminal_and_is_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _publication_roots(tmp_path)

    def fail_rename(source: Path, destination: Path) -> None:
        raise PublicationError("injected guarded publication failure")

    monkeypatch.setattr(
        "legsa_gins.paper_rebuild.horizontal_literature.ginav2021.publication."
        "_atomic_rename_noreplace",
        fail_rename,
    )
    payload = _finalize_terminal(
        SUCCESS_STATUS,
        stage=roots["stage"],
        access_audit=_clean_audit(),
        provenance=_provenance(),
        cleanliness_runs=(),
        publish=True,
        destination=roots["destination"],
        clean_root=roots["clean"],
        protected_roots=(
            roots["code"], roots["clean"], roots["raw"], roots["paper"],
            roots["legacy"],
        ),
        path_aliases={tmp_path: "<TEST_ROOT>"},
        detail="bounded test terminal",
        extra={"formal_lc02_admission": True},
    )
    assert payload["terminal_status"] == SUCCESS_STATUS
    assert payload["scientific_terminal_status"] == SUCCESS_STATUS
    assert payload["artifact_publication"] == "FAILED"
    assert payload["transaction_complete"] is False
    assert payload["scientific_formal_lc02_admission"] is True
    assert payload["formal_lc02_admission"] is False
    assert payload["formal_lc02_slot"] == "VACANT"
    assert not roots["destination"].exists()
    for key in (
        "data_mode", "raw_source_hashes", "provider_hashes",
        "synthetic_data_used", "semisynthetic_data_used", "trace_used_online",
        "receiver_imu_as_body_imu", "final_v23_output_solver_input",
        "LegSA_output_solver_input", "per_case_tuning",
        "output_only_correction", "epoch_deleted_for_metric",
        "old_runtime_input_count", "code_commit", "config_hash",
    ):
        assert key in payload
