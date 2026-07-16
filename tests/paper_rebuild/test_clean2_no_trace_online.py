from legsa_gins.paper_rebuild.clean2_run_registry import build_run_registry_rows
from legsa_gins.paper_rebuild.clean2_runner import build_clean2_runtime_config
from test_basic_fixed_std_semantics import BASE


def test_clean2_runtime_explicitly_disables_trace(repo_root, ablation_catalog, classic_catalog, clean2_base_files, tmp_path, monkeypatch):
    monkeypatch.setattr("legsa_gins.paper_rebuild.clean2_runner._validate_frozen_base_template", lambda *args, **kwargs: {})
    shared = {}
    for role in ("imu", "raw_doppler", "go2_roll_pitch", "go2_horizontal_velocity"):
        path = tmp_path / role
        path.write_text(role, encoding="utf-8")
        shared[role] = path
    hashes = {case.case_id: f"{index + 1:064x}" for index, case in enumerate(classic_catalog.cases)}
    row = build_run_registry_rows(ablation_catalog, classic_catalog, provider_bundle_hashes=hashes, executable_hash="f" * 64)[3]
    text = build_clean2_runtime_config(BASE, row, gnss_path=clean2_base_files["gnss"], shared_provider_paths=shared, output_dir=tmp_path / "run", methods_config=repo_root / "configs/paper_rebuild/methods.yaml", parity_contract_path=repo_root / "configs/paper_rebuild/final_v23_parity_contract.yaml", clean1_protocol_path=repo_root / "configs/paper_rebuild/clean1_by2_clean_protocol.yaml")
    assert "clean2_formal_mode: true" in text
    assert "trace_used_online: false" in text
    assert "clean1_formal_mode: false" in text
    assert str(shared["imu"].resolve()) in text
    assert str(shared["raw_doppler"].resolve()) in text
