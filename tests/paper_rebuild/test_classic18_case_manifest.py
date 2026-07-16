import json

from legsa_gins.paper_rebuild.clean2_case_provider import materialize_case_bundle
from legsa_gins.paper_rebuild.clean2_classic_cases import apply_classic_case


def test_c00_case_manifest_is_clean_and_byte_parity(classic_catalog, clean2_base_files, tmp_path):
    application = apply_classic_case(clean2_base_files["epochs"], classic_catalog.case("C00"))
    evidence = {
        "provider_hashes": {"imu": "1" * 64, "gnss": "2" * 64, "raw_doppler": "3" * 64, "go2_roll_pitch": "4" * 64, "go2_horizontal_velocity": "5" * 64},
        "shared_provider_paths": {"imu": "/fresh/imu", "raw_doppler": "/fresh/rd", "go2_roll_pitch": "/fresh/rp", "go2_horizontal_velocity": "/fresh/hv"},
        "raw_source_hashes": {f"raw/{i}": "6" * 64 for i in range(22)},
        "raw_pre_checkpoint_sha256": "7" * 64, "raw_post_checkpoint_sha256": "8" * 64,
        "raw_hash_lock_sha256": "9" * 64, "code_freeze_commit": "a" * 40,
        "clean_input_manifest_sha256": "b" * 64, "auxiliary_bundle_manifest_sha256": "c" * 64,
    }
    result = materialize_case_bundle(
        application,
        base_gnss_path=clean2_base_files["gnss"],
        base_dual_yaw_provider_path=clean2_base_files["dual"],
        base_rows=clean2_base_files["rows"],
        base_payload=clean2_base_files["payload"],
        base_extension_audit={"first15_token_parity": True, "first15_numerical_parity": True},
        destination=tmp_path / "C00",
        mapping_catalog=classic_catalog,
        base_provider_evidence=evidence,
    )
    manifest = json.loads(open(result["manifest_path"], encoding="utf-8").read())
    assert manifest["data_mode"] == "real_by2_raw"
    assert manifest["semisynthetic_data_used"] is False
    assert manifest["c00_extended_payload_exact"] is True
    assert manifest["c00_first15_token_parity"] is True
    assert manifest["trace_read_count"] == 0
    assert manifest["shared_provider_paths"] == {
        "go2_horizontal_velocity": "provider://fresh/go2_horizontal_velocity",
        "go2_roll_pitch": "provider://fresh/go2_roll_pitch",
        "imu": "provider://fresh/imu",
        "raw_doppler": "provider://fresh/raw_doppler",
    }
    assert '"/fresh/' not in json.dumps(manifest)
    policy = json.loads((tmp_path / "C00/CASE_POLICY_REPORT.json").read_text(encoding="utf-8"))
    assert policy["shared_provider_paths"] == manifest["shared_provider_paths"]
