import csv
import gzip
from collections import Counter

from legsa_gins.paper_rebuild.canonical541.provider_generator import (
    D57_TIMING_SOURCE_IDS, resolve_provider_index, write_case_provider,
)
from test_canonical541_helpers import case, make_bundle


def test_provider_package_tree_and_pointer(tmp_path):
    base=make_bundle(tmp_path); clean={**case("D01"), "case_id":"C00_clean_normal", "degradation_type_id":"CLEAN", "seed_index":"none", "seed_value":""}
    croot=tmp_path/"C00"; write_case_provider(base=base,case=clean,case_root=croot)
    droot=tmp_path/"D30"; write_case_provider(base=base,case=case("D30"),case_root=droot,clean_case_root=croot)
    resolved=resolve_provider_index(droot)
    assert len(resolved)==8 and (droot/"04_PROVIDER_READY/provider_ready.flag").is_file()


def test_d57_package_ledger_closes_only_six_timing_sources(tmp_path):
    base = make_bundle(tmp_path, n=120)
    assert "source_quality_metadata" in base.tables
    root = tmp_path / "D57"
    ready = write_case_provider(base=base, case=case("D57", 4), case_root=root)
    assert ready["provider_ready"] is True
    assert (root / "04_PROVIDER_READY/provider_ready.flag").read_text(encoding="utf-8") == "PASS\n"
    with gzip.open(root / "02_PROVIDERS/CASE_PERTURBATION_LEDGER.csv.gz",
                   "rt", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    counts = Counter(row["source"] for row in rows)
    assert set(counts) == set(D57_TIMING_SOURCE_IDS)
    assert "source_quality_metadata" not in counts
    assert counts == Counter({source: len(base.tables[source].rows)
                              for source in D57_TIMING_SOURCE_IDS})
    assert all("time" in row["changed_fields"].split(";") for row in rows)
