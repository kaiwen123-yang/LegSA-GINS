import hashlib
import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.canonical541.full_method_registry import FULL_METHODS
from legsa_gins.paper_rebuild.canonical541.preparation import (
    ExpectedBinding,
    PreparationError,
    PreparationStatusWriter,
    ProviderRegistryRow,
    ProviderTableCache,
    UniqueFileHashCache,
    _tail_recovery_allowed,
    _finalize_method_manifest_rendered_hash,
    _validate_method_manifest,
    _validate_shared_gnss_store,
    scientific_method_runtime_hash,
)
from legsa_gins.paper_rebuild.canonical541.provider_generator import ProviderBundle


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_unique_file_hash_and_json_cache_read_once(tmp_path):
    path = tmp_path / "a.json"
    path.write_text('{"x":1}\n', encoding="utf-8")
    calls = []

    def hasher(candidate):
        calls.append(candidate)
        return _sha(candidate)

    cache = UniqueFileHashCache(hasher=hasher)
    assert cache.read_json(path) == {"x": 1}
    # read_json already populated the SHA cache; sha256 must not reopen/hash it.
    assert cache.sha256(path) == _sha(path)
    assert calls == []
    assert cache.physical_reads == 1


def test_hash_cache_rejects_external_mutation_and_fresh_boundary_accepts_finalized_bytes(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text('{"value":"before"}\n', encoding="utf-8")
    cache = UniqueFileHashCache()
    cache.sha256(path)
    path.write_text('{"value":"external"}\n', encoding="utf-8")
    with pytest.raises(PreparationError, match="mutated during hash cache lifetime"):
        cache.sha256(path)

    # A new boundary is permitted only after the caller has explicitly
    # completed its owned atomic finalization; it hashes the finalized bytes.
    finalized = UniqueFileHashCache()
    assert finalized.sha256(path) == _sha(path)


def test_owned_manifest_finalization_is_guarded_and_written_once(tmp_path):
    path = tmp_path / "METHOD_BOUND_INPUT_MANIFEST.json"
    payload = {"case_id": "C00_clean_normal"}
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    cache = UniqueFileHashCache()
    cache.read_json(path)
    _finalize_method_manifest_rendered_hash(
        path=path, payload=payload, rendered_hash="a" * 64, hash_cache=cache,
    )
    assert json.loads(path.read_text(encoding="utf-8"))["actual_rendered_runtime_config_sha256"] == "a" * 64
    assert payload["actual_rendered_runtime_config_sha256"] == "a" * 64

    fresh = UniqueFileHashCache()
    fresh.sha256(path)
    _finalize_method_manifest_rendered_hash(
        path=path, payload=payload, rendered_hash="a" * 64, hash_cache=fresh,
    )
    with pytest.raises(PreparationError, match="rendered runtime config hash drift"):
        _finalize_method_manifest_rendered_hash(
            path=path, payload=payload, rendered_hash="b" * 64, hash_cache=fresh,
        )


def test_provider_table_cache_parses_same_physical_file_once(tmp_path):
    path = tmp_path / "provider.csv"
    path.write_text("time,value\n1,2\n", encoding="utf-8")
    semantic = _sha(path)
    cache = ProviderTableCache()
    left = cache.get(path, expected_semantic_sha256=semantic)
    right = cache.get(path, expected_semantic_sha256=semantic)
    assert left is right
    assert cache.physical_parses == 1


def test_shared_gnss_store_validates_content_address_once(tmp_path):
    root = tmp_path / "shared"; root.mkdir()
    content = b"1 2 3\n"
    digest = hashlib.sha256(content).hexdigest()
    (root / f"{digest}.gnss").write_bytes(content)
    cache = UniqueFileHashCache()
    assert _validate_shared_gnss_store(root, cache) == 1
    assert _validate_shared_gnss_store(root, cache) == 1
    assert cache.physical_reads == 1


def test_only_one_last_invalid_artifact_can_recover():
    assert _tail_recovery_allowed(invalid_ordinals=[9], artifact_ordinals=list(range(10))) == 9
    with pytest.raises(PreparationError):
        _tail_recovery_allowed(invalid_ordinals=[8], artifact_ordinals=list(range(10)))
    with pytest.raises(PreparationError):
        _tail_recovery_allowed(invalid_ordinals=[8, 9], artifact_ordinals=list(range(10)))


def test_existing_manifest_is_parsed_once_and_validly_skipped(tmp_path):
    case_id = "C00_clean_normal"; profile = FULL_METHODS[0]
    inputs = tmp_path / "inputs"; inputs.mkdir()
    imu = inputs / "fresh.imu"; imu.write_text("imu\n", encoding="utf-8")
    gnss = inputs / "fresh.gnss"; gnss.write_text("gnss\n", encoding="utf-8")
    aux = {}
    for name in ("raw_doppler", "go2_rp", "go2_hv"):
        path = inputs / f"{name}.csv"; path.write_text("time,value\n1,2\n", encoding="utf-8")
        aux[name] = path
    sources = (
        "gnss_position", "receiver_velocity", "dual_yaw", "raw_doppler",
        "go2_rp", "go2_hv", "source_quality_metadata",
    )
    semantic = {source: hashlib.sha256(source.encode()).hexdigest() for source in sources}
    registry = {
        (case_id, source): ProviderRegistryRow(
            case_id, source, semantic[source], 1, semantic[source], "materialized", inputs / f"{source}.csv",
        ) for source in sources
    }
    base = ProviderBundle(
        imu_path=imu, tables={}, raw_input_hashes={},
        base_provider_hashes={
            "imu": _sha(imu), "gnss": _sha(gnss),
            "raw_doppler": _sha(aux["raw_doppler"]),
            "go2_rp": _sha(aux["go2_rp"]), "go2_hv": _sha(aux["go2_hv"]),
        },
        dual_yaw_audit_rows=[],
        original_provider_paths={"combined_gnss": gnss, **aux},
    )
    destination = tmp_path / "METHOD_BOUND" / case_id / profile.effective_profile
    destination.mkdir(parents=True)
    actual_hashes = {"imu": _sha(imu), "gnss": _sha(gnss)}
    payload = {
        "method_id": profile.method_id, "method_name": profile.name,
        "effective_profile": profile.effective_profile,
        "effective_flags": dict(profile.flags),
        "actual_solver_inputs": {"imu": str(imu), "gnss": str(gnss)},
        "actual_solver_input_hashes": actual_hashes,
        "full_case_bundle_hashes": semantic,
        "method_bound_source_hashes": semantic,
        "source_quality_metadata_active_loader": False,
        "tracked_method_contract_sha256": "c" * 64,
        "scientific_runtime_contract_sha256": scientific_method_runtime_hash(
            profile, case_id, "c" * 64,
        ),
        "method_bound_bundle_sha256": hashlib.sha256(
            json.dumps(actual_hashes, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    manifest = destination / "METHOD_BOUND_INPUT_MANIFEST.json"
    manifest.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    cache = UniqueFileHashCache()
    task = ExpectedBinding(0, case_id, profile, destination)
    first = _validate_method_manifest(
        path=manifest, task=task, registry=registry, base=base,
        shared_gnss_root=tmp_path / "shared", hash_cache=cache,
    )
    reads = cache.physical_reads
    second = _validate_method_manifest(
        path=manifest, task=task, registry=registry, base=base,
        shared_gnss_root=tmp_path / "shared", hash_cache=cache,
    )
    assert first == second
    assert cache.physical_reads == reads


def test_status_is_lightweight_and_rate_limited(tmp_path):
    ticks = iter([0.0, 30.0, 60.0])
    writer = PreparationStatusWriter(tmp_path / "PREPARATION_STATUS.json", clock=lambda: next(ticks))
    assert writer.write(phase="STARTING", method_bound_completed=0, cases_completed=0, force=True)
    assert not writer.write(phase="WORKING", method_bound_completed=1, cases_completed=0)
    assert writer.write(phase="WORKING", method_bound_completed=2, cases_completed=0)
    payload = json.loads(writer.path.read_text(encoding="utf-8"))
    assert payload["method_bound_total"] == 5951
    assert payload["cases_total"] == 541
    assert payload["solver_runs"] == payload["evaluator_runs"] == payload["trace_reads"] == 0
    assert payload["execution_authorized"] is True
