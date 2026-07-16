from legsa_gins.paper_rebuild.clean2_run_registry import build_run_registry_rows
from legsa_gins.paper_rebuild.clean2_runner import build_clean2_runtime_config


BASE = """clean1_formal_mode: true
starttime: 66.0
endtime: 340.0
initpos: [39.98482973, 116.34312609, 41.80208107]
initvel: [0, 0, 0]
initatt: [0, 0, 0.688505]
antlever: [0.03, 0.03, -0.30]
basic_dual_yaw_fixed_std_deg: 1.5
trace_used_online: false
per_case_tuning: false
output_only_correction: false
epoch_deleted_for_metric: false
"""


def test_basic_uses_fixed_15deg_for_std_inflation_cases(repo_root, ablation_catalog, classic_catalog, clean2_base_files, tmp_path, monkeypatch):
    monkeypatch.setattr("legsa_gins.paper_rebuild.clean2_runner._validate_frozen_base_template", lambda *args, **kwargs: {})
    shared = {}
    for role in ("imu", "raw_doppler", "go2_roll_pitch", "go2_horizontal_velocity"):
        path = tmp_path / role
        path.write_text(role, encoding="utf-8")
        shared[role] = path
    hashes = {case.case_id: f"{index + 1:064x}" for index, case in enumerate(classic_catalog.cases)}
    rows = build_run_registry_rows(ablation_catalog, classic_catalog, provider_bundle_hashes=hashes, executable_hash="f" * 64)
    basic = [row for row in rows if row["structural_method"] == "basic_dual_yaw_EKF" and row["case_id"].startswith(("C10_", "C14_"))]
    configs = [build_clean2_runtime_config(BASE, row, gnss_path=clean2_base_files["gnss"], shared_provider_paths=shared, output_dir=tmp_path / row["run_id"], methods_config=repo_root / "configs/paper_rebuild/methods.yaml", parity_contract_path=repo_root / "configs/paper_rebuild/final_v23_parity_contract.yaml", clean1_protocol_path=repo_root / "configs/paper_rebuild/clean1_by2_clean_protocol.yaml") for row in basic]
    assert len(configs) == 2
    assert all("basic_dual_yaw_fixed_std_deg: 1.5" in config for config in configs)
    assert all("enable_source_aware: false" in config for config in configs)
