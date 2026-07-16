from legsa_gins.paper_rebuild.clean2_run_registry import build_run_registry_rows


def test_six_sentinels_have_four_extra_loo(ablation_catalog, classic_catalog):
    hashes = {case.case_id: f"{index + 1:064x}" for index, case in enumerate(classic_catalog.cases)}
    rows = build_run_registry_rows(ablation_catalog, classic_catalog, provider_bundle_hashes=hashes, executable_hash="f" * 64)
    loo = [row for row in rows if "sentinel_LOO" in row["alias_roles"]]
    assert len(loo) == 24
    assert {row["ablation_id"] for row in loo} == {"AB0111", "AB1011", "AB1101", "AB1110"}
