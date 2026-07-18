import csv
import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.clean2r2a_runner import (
    METHOD_ORDER,
    Clean2R2ARunError,
    run_directory,
    validate_output_seal,
)
from legsa_gins.paper_rebuild.manifest import sha256_file


def _sealed_stage(tmp_path: Path) -> tuple[Path, Path, Path]:
    stage = tmp_path / "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD"
    runtime = stage / "06_FORMAL_RUNS"
    seal = stage / "07_OUTPUT_SEAL"
    seal.mkdir(parents=True)
    rows = []
    counts = {}
    for method in METHOD_ORDER:
        output = runtime / run_directory(method)
        output.mkdir(parents=True)
        payload = output / "output.txt"
        payload.write_text(method + "\n", encoding="utf-8")
        rows.append({
            "algorithm_id": method,
            "relative_path": payload.relative_to(runtime).as_posix(),
            "size_bytes": payload.stat().st_size,
            "sha256": sha256_file(payload),
            "sealed_before_trace": True,
        })
        counts[method] = 1
    manifest = seal / "OUTPUT_HASH_MANIFEST.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    journal_path = seal / "OUTPUT_SEAL_JOURNAL.json"
    journal = {
        "schema_version": "paper_rebuild.clean2r2a_output_seal.v1",
        "unique_formal_runs": 18, "sealed_file_count": 18,
        "method_ids": list(METHOD_ORDER), "sealed_file_count_by_method": counts,
        "trace_open_count_before_seal": 0, "all_outputs_sealed_before_trace": True,
        "output_hash_manifest_sha256": sha256_file(manifest),
        "output_hash_manifest_size_bytes": manifest.stat().st_size,
        "passed": True,
    }
    journal_path.write_text(json.dumps(journal), encoding="utf-8")
    return stage, manifest, journal_path


def test_output_seal_is_exact_current_file_closure(tmp_path: Path) -> None:
    stage, manifest, journal_path = _sealed_stage(tmp_path)
    assert len(validate_output_seal(stage)) == 18
    rows = list(csv.DictReader(manifest.open("r", encoding="utf-8", newline="")))
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows[:-1])
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    journal["sealed_file_count"] = 17
    journal["sealed_file_count_by_method"][METHOD_ORDER[-1]] = 0
    journal["output_hash_manifest_sha256"] = sha256_file(manifest)
    journal["output_hash_manifest_size_bytes"] = manifest.stat().st_size
    journal_path.write_text(json.dumps(journal), encoding="utf-8")
    with pytest.raises(Clean2R2ARunError, match="exact current-file closure"):
        validate_output_seal(stage)
