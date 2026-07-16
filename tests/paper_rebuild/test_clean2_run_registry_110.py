from legsa_gins.paper_rebuild.clean2_run_registry import build_run_registry_rows, validate_run_registry_rows


def test_clean2_run_registry_has_110_unique_processes(ablation_catalog, classic_catalog):
    hashes = {case.case_id: f"{index + 1:064x}" for index, case in enumerate(classic_catalog.cases)}
    rows = build_run_registry_rows(ablation_catalog, classic_catalog, provider_bundle_hashes=hashes, executable_hash="f" * 64)
    audit = validate_run_registry_rows(rows)
    assert audit["unique_run_count"] == 110
    assert audit["duplicate_effective_config_count"] == 0
    assert [row["ablation_id"] for row in rows[:4]] == ["", "", "AB0000", "AB1111"]
