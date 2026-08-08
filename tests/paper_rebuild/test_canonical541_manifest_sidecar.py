from legsa_gins.paper_rebuild.canonical541.evidence import build_manifest,validate_stage_closure


def test_manifest_sidecar_created_together(tmp_path):
    (tmp_path/"report.txt").write_text("ok\n")
    build_manifest(tmp_path, {"report.txt": ("terminal_audit", "current_clean_audit")})
    report=validate_stage_closure(tmp_path)
    assert report["sidecar_check"] and report["payload_count"]==1
    assert report["exact_entry_set"] and report["unlisted_extra_count"] == 0
