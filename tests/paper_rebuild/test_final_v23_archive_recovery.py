from __future__ import annotations

import zipfile

import pytest

from scripts.paper_rebuild.recover_final_v23_archive import (
    build_source_map,
    candidate_role,
    evidence_classification,
    lstat_confined_path,
    RecoveryError,
    safe_member_name,
    should_extract,
    should_recurse_nested_zip,
)


def _info(name: str, size: int = 10) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name)
    info.file_size = size
    return info


def test_member_path_guard_rejects_traversal_and_windows_forms() -> None:
    assert safe_member_name("KF-GINS/bin/process_data.py") == (True, "")
    assert safe_member_name("../escape.py")[0] is False
    assert safe_member_name("/absolute.py")[0] is False
    assert safe_member_name("C:/absolute.py")[0] is False
    assert safe_member_name("dir\\escape.py")[0] is False


def test_core_role_and_excluded_branch_classification() -> None:
    role, _ = candidate_role(_info("KF-GINS/bin/process_data.py"))
    assert role == "exact_process_data"
    assert evidence_classification(role)[0] == "MIGRATABLE_STATIC_SPECIFICATION"

    role, reason = candidate_role(_info("KF-GINS/bin/run_v24_quality_manager_tuned.py"))
    assert role == "excluded_branch"
    assert reason == "V2.4_QUALITY_MANAGER"
    assert evidence_classification(role)[0] == "DENIED_AS_ACTIVE_EVIDENCE"


def test_named_normal_archive_is_reference_only() -> None:
    role, _ = candidate_role(_info("KF-GINS/nominal_none.zip"))
    assert role == "named_reference_archive"
    assert evidence_classification(role)[0] == "PARITY_REFERENCE_ONLY"


def test_historical_summary_is_never_promoted_by_final_v23_parent() -> None:
    role, _ = candidate_role(_info("KF-GINS/final_v23_run/summary.json"))
    assert role == "historical_result"
    assert evidence_classification(role)[0] == "PARITY_REFERENCE_ONLY"
    assert not should_extract(
        {
            "candidate_role": role,
            "member_size": 1024,
            "archive_member": "KF-GINS/final_v23_run/summary.json",
            "safe_member": True,
            "symlink_member": False,
        }
    )

    assert not should_extract(
        {
            "candidate_role": role,
            "member_size": 1024,
            "archive_member": "KF-GINS/unlinked_run/summary.json",
            "safe_member": True,
            "symlink_member": False,
        }
    )


def test_parameter_sweep_is_denied_before_runtime_config_selection() -> None:
    role, reason = candidate_role(
        _info("KF-GINS/V2验证/attitude_feasibility_sweep/stage_b/kf-gins-lxm0.03.yaml")
    )
    assert role == "excluded_branch"
    assert reason == "NOISE_INJECTION_OR_DEGRADATION"
    assert evidence_classification(role)[0] == "DENIED_AS_ACTIVE_EVIDENCE"


def test_generated_final_v23_audit_is_reference_not_static_spec() -> None:
    name = "project/毕设数据/绘图/最新绘图/_final_v23_only_audit/final_v23_only_audit_summary.md"
    role, _ = candidate_role(_info(name))
    assert role == "historical_result"
    assert evidence_classification(role)[0] == "PARITY_REFERENCE_ONLY"
    assert not should_extract(
        {
            "candidate_role": role,
            "member_size": 2048,
            "archive_member": name,
            "safe_member": True,
            "symlink_member": False,
        }
    )


def test_canonical_final_v23_doc_remains_static_spec() -> None:
    role, _ = candidate_role(_info("KF-GINS/docs/final_v23_mainline.md"))
    assert role == "final_v23_note"
    assert evidence_classification(role)[0] == "MIGRATABLE_STATIC_SPECIFICATION"


def test_pos_spike_run_meta_is_denied_and_exact_runtime_yaml_is_static() -> None:
    role, _ = candidate_role(
        _info("毕设数据/generated_results/pos_spike_medium/dual_final_v23/run_meta.json")
    )
    assert role == "excluded_branch"
    assert evidence_classification(role)[0] == "DENIED_AS_ACTIVE_EVIDENCE"

    role, _ = candidate_role(
        _info("毕设数据/资料补齐_算法讲解/03_final_yaml/originals/final_v23_runtime.yaml")
    )
    assert role == "runtime_config"
    assert evidence_classification(role)[0] == "MIGRATABLE_STATIC_SPECIFICATION"

    role, _ = candidate_role(_info("KF-GINS/config/kf-gins.yaml"))
    assert role == "runtime_config"
    assert evidence_classification(role)[0] == "MIGRATABLE_STATIC_SPECIFICATION"


def test_solver_core_is_canonical_and_thirdparty_is_not_selected_as_core() -> None:
    role, _ = candidate_role(_info("KF-GINS/src/fileio/filesaver.cc"))
    assert role == "solver_source_core"

    role, _ = candidate_role(_info("KF-GINS/ThirdParty/abseil/absl/base/options.h"))
    assert role == "generic_static_source"
    assert evidence_classification(role)[0] == "MIGRATABLE_STATIC_SPECIFICATION"

    role, _ = candidate_role(_info("project/.venv/Lib/site-packages/pyarrow/options.h"))
    assert role == "environment_or_build_output"
    assert evidence_classification(role)[0] == "DENIED_AS_ACTIVE_EVIDENCE"


def test_historical_result_root_configs_are_not_static_contracts() -> None:
    role, _ = candidate_role(
        _info("project/generated_results/pos_spike/dual_final_v23/kf-gins.yaml")
    )
    assert role == "excluded_branch"
    assert evidence_classification(role)[0] == "DENIED_AS_ACTIVE_EVIDENCE"

    role, _ = candidate_role(_info("project/final_results/noisy_case/kf-gins-final-case.yaml"))
    assert role == "generated_performance_report"
    assert evidence_classification(role)[0] == "DENIED_AS_ACTIVE_EVIDENCE"


def test_real_v2_ablation_and_traceyaw_paths_are_denied() -> None:
    paths = (
        "毕设数据/V2验证/gi_yaw_param_ablation/scheme_C/15%野值+1.5度基值/kf-gins-scheme_C-case1.yaml",
        "毕设数据/V2验证/status_yawstd_ablation/fixed_1p5/15%野值+1.5度基值/kf-gins-fixed_1p5-case1.yaml",
        "毕设数据/V2验证/traceyaw/断联10s+15%野值+1.5度基值/kf-gins-traceyaw.yaml",
    )
    for path in paths:
        role, _ = candidate_role(_info(path))
        assert role == "excluded_branch"
        assert evidence_classification(role)[0] == "DENIED_AS_ACTIVE_EVIDENCE"


def test_only_source_linked_canonical_test1_pair_is_direct_parity_reference() -> None:
    canonical = "project/毕设数据/2026.3.6-测试数据/高层数据/test1.imu"
    role, _ = candidate_role(_info(canonical))
    assert role == "parity_reference"
    assert evidence_classification(role)[0] == "PARITY_REFERENCE_ONLY"

    noisy_variant = "project/毕设数据/数据处理后/双天线/15%野值/test1.imu"
    role, _ = candidate_role(_info(noisy_variant))
    assert role == "excluded_branch"
    assert evidence_classification(role)[0] == "DENIED_AS_ACTIVE_EVIDENCE"


def test_exact_source_linked_e001_exception_precedes_degradation_denylist() -> None:
    prefix = (
        "毕业设计-足式机器人双天线北斗RTK 惯导定位定姿算法研究/毕设数据/"
        "extended_degradation_results/final_v23/single/E001_single_nominal_none/"
    )
    static_expectations = {
        "kf-gins.yaml": "source_linked_runtime_config",
        "run_meta.json": "source_linked_runtime_manifest",
    }
    parity_names = (
        "input.gnss",
        "KF_GINS_Navresult.nav",
        "KF_GINS_STD.txt",
        "error_series.csv",
        "summary.json",
        "report.txt",
        "run.log",
    )
    for name, expected_role in static_expectations.items():
        role, _ = candidate_role(_info(prefix + name))
        assert role == expected_role
        assert evidence_classification(role)[0] == "MIGRATABLE_STATIC_SPECIFICATION"
    for name in parity_names:
        role, _ = candidate_role(_info(prefix + name))
        assert role == "source_linked_parity_reference"
        assert evidence_classification(role)[0] == "PARITY_REFERENCE_ONLY"

    sibling = prefix.replace("E001_single_nominal_none", "E002_single_other")
    role, _ = candidate_role(_info(sibling + "run_meta.json"))
    assert role == "excluded_branch"
    assert evidence_classification(role)[0] == "DENIED_AS_ACTIVE_EVIDENCE"


def test_nested_recursion_is_bounded_to_authorized_candidates() -> None:
    main_name = "authorized-full-project.zip"
    assert should_recurse_nested_zip(main_name, depth=0, main_archive_basename=main_name)
    assert not should_recurse_nested_zip("unrelated.zip", depth=0, main_archive_basename=main_name)
    assert should_recurse_nested_zip("archives/nominal_none.zip", depth=1, main_archive_basename=main_name)
    assert should_recurse_nested_zip("archives/final_v23_sources.zip", depth=2, main_archive_basename=main_name)
    assert not should_recurse_nested_zip("archives/unrelated.zip", depth=1, main_archive_basename=main_name)


def test_parent_symlink_is_rejected_before_output_creation(tmp_path) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    (allowed / "linked-parent").symlink_to(outside, target_is_directory=True)

    with pytest.raises(RecoveryError, match="symlink component"):
        lstat_confined_path(
            allowed / "linked-parent" / "output.json",
            allowed_root=allowed,
            role="test output",
            must_exist=False,
        )


def test_distinct_core_hashes_remain_unselected() -> None:
    rows = [
        {
            "candidate_role": "exact_process_data",
            "qualified_member": "MAIN!/1:KF-GINS/bin/process_data.py",
            "archive_member": "KF-GINS/bin/process_data.py",
            "sha256": "a" * 64,
            "mtime": "2026-04-03T00:00:00+00:00",
            "depth": 0,
        },
        {
            "candidate_role": "exact_process_data",
            "qualified_member": "MAIN!/nested.zip!/1:KF-GINS/bin/process_data.py",
            "archive_member": "KF-GINS/bin/process_data.py",
            "sha256": "b" * 64,
            "mtime": "2026-04-02T00:00:00+00:00",
            "depth": 1,
        },
    ]
    source_rows, _ = build_source_map(rows)
    process_rows = [row for row in source_rows if row["logical_role"] == "process_data"]
    assert len(process_rows) == 2
    assert all(row["selected"] is False for row in process_rows)
    assert all(row["conflict_resolution"] == "UNRESOLVED_DISTINCT_SHA256" for row in process_rows)
