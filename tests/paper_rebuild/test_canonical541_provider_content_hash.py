from legsa_gins.paper_rebuild.canonical541.provider_generator import canonical_provider_bundle_sha256


def test_provider_bundle_hash_is_content_only():
    hashes = {"gnss_position": "a" * 64, "raw_doppler": "b" * 64}
    first = canonical_provider_bundle_sha256(imu_sha256="c" * 64, source_hashes=hashes)
    second = canonical_provider_bundle_sha256(
        imu_sha256="c" * 64,
        source_hashes={"raw_doppler": "b" * 64, "gnss_position": "a" * 64},
    )
    assert first == second
    assert first != canonical_provider_bundle_sha256(
        imu_sha256="c" * 64,
        source_hashes={"gnss_position": "a" * 64, "raw_doppler": "d" * 64},
    )
