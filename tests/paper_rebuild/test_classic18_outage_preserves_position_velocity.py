def test_outage_only_withholds_yaw_valid(clean2_base_files, apply_case):
    result = apply_case("C01")
    assert sum(row[17] == "0" for row in result.output_fields) == 20
    assert all(base[:17] == changed[:17] for base, changed in zip(clean2_base_files["rows"], result.output_fields))
