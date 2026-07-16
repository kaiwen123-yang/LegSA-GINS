import math
import json

from legsa_gins.paper_rebuild.clean2_case_provider import materialize_case_bundle
from legsa_gins.paper_rebuild.clean2_classic_cases import apply_classic_case


def test_yaw_std_scales_only_provider_yaw_std(apply_case, clean2_base_files):
    c10 = apply_case("C10")
    c14 = apply_case("C14")
    assert all(math.isclose(float(row[14]), 6.0) for row in c10.output_fields)
    assert all(math.isclose(float(row[14]), 3.0) for row in c14.output_fields)
    assert all(math.isclose(float(row["modified_yaw"]), float(row["original_yaw"])) for row in c10.ledger_rows)
    for base, changed in zip(clean2_base_files["rows"], c10.output_fields):
        assert base[:14] == changed[:14]
        assert base[15:] == changed[15:]
    for base, changed in zip(clean2_base_files["rows"], c14.output_fields):
        assert base[:14] == changed[:14]
        assert base[15:] == changed[15:]


def test_std_scale_metadata_is_frozen_in_policy_and_manifest(
    classic_catalog, clean2_base_files, tmp_path
):
    application = apply_classic_case(
        clean2_base_files["epochs"], classic_catalog.case("C10")
    )
    evidence = {
        "provider_hashes": {
            "imu": "1" * 64,
            "gnss": "2" * 64,
            "raw_doppler": "3" * 64,
            "go2_roll_pitch": "4" * 64,
            "go2_horizontal_velocity": "5" * 64,
        },
        "shared_provider_paths": {
            "imu": "/fresh/imu",
            "raw_doppler": "/fresh/rd",
            "go2_roll_pitch": "/fresh/rp",
            "go2_horizontal_velocity": "/fresh/hv",
        },
        "raw_source_hashes": {f"raw/{i}": "6" * 64 for i in range(22)},
        "raw_pre_checkpoint_sha256": "7" * 64,
        "raw_post_checkpoint_sha256": "8" * 64,
        "raw_hash_lock_sha256": "9" * 64,
        "code_freeze_commit": "a" * 40,
        "clean_input_manifest_sha256": "b" * 64,
        "auxiliary_bundle_manifest_sha256": "c" * 64,
    }
    result = materialize_case_bundle(
        application,
        base_gnss_path=clean2_base_files["gnss"],
        base_dual_yaw_provider_path=clean2_base_files["dual"],
        base_rows=clean2_base_files["rows"],
        base_payload=clean2_base_files["payload"],
        base_extension_audit={"first15_token_parity": True, "first15_numerical_parity": True},
        destination=tmp_path / application.case.case_id,
        mapping_catalog=classic_catalog,
        base_provider_evidence=evidence,
    )
    manifest = json.loads(open(result["manifest_path"], encoding="utf-8").read())
    policy = json.loads(
        (tmp_path / application.case.case_id / "CASE_POLICY_REPORT.json").read_text(encoding="utf-8")
    )
    assert manifest["provider_std_scale"] == policy["provider_std_scale"] == 4.0
    assert manifest["operations"] == policy["operations"]
