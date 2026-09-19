from legsa_gins.paper_rebuild.canonical541.effect_validation import validate_case_effect, validate_handler_closure
from legsa_gins.paper_rebuild.canonical541.provider_generator import apply_degradation, compose_solver_gnss18
from test_canonical541_helpers import case, make_bundle


def test_all_sixty_handlers_independently_validate(tmp_path):
    validate_handler_closure(); base = make_bundle(tmp_path)
    for index in range(1, 61):
        row = case(f"D{index:02d}", index % 9)
        generated, components, _ = apply_degradation(base, row)
        report = validate_case_effect(base=base, generated=generated, case=row, components=components)
        assert report["passed"], (row["case_id"], [item for item in report["detail_rows"] if not item["passed"]])
        replay = next(item for item in report["detail_rows"] if item["check"] == "seed_replay_exact")
        assert replay["passed"] is True


def test_d40_changes_audit_baseline_but_not_solver_runtime_input(tmp_path):
    base = make_bundle(tmp_path)
    generated, components, semantics = apply_degradation(base, case("D40", 4))
    assert generated.tables["dual_yaw"].sha256() != base.tables["dual_yaw"].sha256()
    assert compose_solver_gnss18(generated) == compose_solver_gnss18(base)
    assert semantics["no_active_path"] is True
    detail = next(row for row in components if row["component"] == "baseline_length_jitter_relacc")
    assert detail["details"]["rel_acc_no_active_path"] is True
    assert detail["details"]["solver_visible_mapping"] == "none_audit_only_baseline_metadata"


def test_d60_exact_seed_replay_passes_all_nine_at_one_hz(tmp_path):
    # 275 rows over the frozen 274 s window approximate the actual 1 Hz GNSS streams.
    base = make_bundle(tmp_path, n=275)
    for seed in range(9):
        row = case("D60", seed)
        generated, components, _ = apply_degradation(base, row)
        report = validate_case_effect(base=base, generated=generated, case=row, components=components)
        assert report["passed"], (seed, [item for item in report["detail_rows"] if not item["passed"]])


def test_velocity_and_go2_cross_axis_mutations_fail_exact_replay(tmp_path):
    base = make_bundle(tmp_path)
    for type_id, source, field in (("D43", "receiver_velocity", "ve"),
                                   ("D47", "raw_doppler", "vd"),
                                   ("D53", "go2_hv", "ve")):
        row = case(type_id, 2)
        generated, components, _ = apply_degradation(base, row)
        generated.tables[source].rows[0][field] = str(float(generated.tables[source].rows[0][field]) + .125)
        report = validate_case_effect(base=base, generated=generated, case=row, components=components)
        assert report["passed"] is False
        assert any("exact_seed_replay" in item["check"] and not item["passed"]
                   for item in report["detail_rows"])
