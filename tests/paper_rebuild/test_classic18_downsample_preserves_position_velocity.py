def test_downsample_retains_first_and_never_deletes_rows(clean2_base_files, apply_case):
    result_2hz = apply_case("C02")
    result_1hz = apply_case("C03")
    assert len(result_2hz.output_fields) == len(result_1hz.output_fields) == 40
    assert all(row[17] == "1" for row in result_2hz.output_fields)
    kept = [float(row[0]) for row in result_1hz.output_fields if row[17] == "1"]
    assert kept[0] == 0.0
    assert all(right - left >= 0.95 for left, right in zip(kept, kept[1:]))
    assert all(base[:17] == changed[:17] for base, changed in zip(clean2_base_files["rows"], result_1hz.output_fields))
