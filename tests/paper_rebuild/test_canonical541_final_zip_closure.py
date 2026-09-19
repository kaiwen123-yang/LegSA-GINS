from legsa_gins.paper_rebuild.canonical541.evidence import build_manifest,create_final_zip


def test_final_zip_manifest_closure(tmp_path):
    root=tmp_path/"FINALIZED";root.mkdir();(root/"a.txt").write_text("a\n")
    build_manifest(root, {"a.txt": ("terminal_audit", "current_clean_audit")})
    report=create_final_zip(
        finalized_root=root,
        zip_path=tmp_path/"LegSA_GINS_CANONICAL541_FINAL_20260719T000000P0800.zip",
    )
    assert report["zip_manifest_closure"] and report["zip_sidecar_check"]
    assert report["zip_exact_entry_set"] and report["outer_sha256_check"]
