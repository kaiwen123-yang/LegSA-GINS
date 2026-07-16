def test_clean2_ablation_matrix_left_to_right(ablation_catalog):
    assert len(ablation_catalog.variants) == 16
    assert [row.ablation_id for row in ablation_catalog.variants] == [f"AB{i:04b}" for i in range(16)]
    assert ablation_catalog.variant("AB1001").features == (True, False, False, True)
    assert ablation_catalog.variant("AB0110").features == (False, True, True, False)
