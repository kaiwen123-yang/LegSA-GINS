from legsa_gins.paper_rebuild.canonical541.matrix_spec import load_type_registry


def test_type_registry_is_exact_60():
    rows = load_type_registry()
    assert [row.type_id for row in rows] == [f"D{i:02d}" for i in range(1, 61)]
    assert rows[18].parameters["period_s"] > 180
    assert rows[39].parameters["baseline_length_additive_jitter_sigma_m"] == .03
    assert rows[48].parameters["spike_component"] is False
