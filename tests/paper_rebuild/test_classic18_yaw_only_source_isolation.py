def test_classic18_changes_only_yaw_value_std_or_validity(clean2_base_files, apply_case):
    for code in ("C01", "C04", "C07", "C10", "C11", "C15"):
        result = apply_case(code)
        for base, changed in zip(clean2_base_files["rows"], result.output_fields):
            assert base[:13] == changed[:13]
            assert base[15:17] == changed[15:17]
