from legsa_gins.paper_rebuild.clean2_evidence import assert_method_case_output_invariance


def test_single_method_output_invariance_audit(tmp_path):
    outputs = {}
    for code in ("C00", "C01", "C17"):
        nav, std = tmp_path / f"{code}.nav", tmp_path / f"{code}.std"
        nav.write_bytes(b"same-nav\n")
        std.write_bytes(b"same-std\n")
        outputs[code] = [nav, std]
    audit = assert_method_case_output_invariance(outputs, failure_status="FAIL_CLEAN2_DUAL_YAW_CASE_LEAKED_INTO_SINGLE_BASELINE")
    assert audit["bit_identical"] is True
