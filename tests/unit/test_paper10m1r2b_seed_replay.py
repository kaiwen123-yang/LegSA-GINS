import json

from tests.paper10m1r2b_common import provider_root, read_csv


def test_seed_replay_dumps_use_locked_pcg64():
    rows = read_csv("05_PROVIDER_READY/PAPER10M1R2B_PROVIDER_READY_MANIFEST.csv")
    sample = next(row for row in rows if row["degradation_type_id"] != "CLEAN")
    dump = provider_root() / sample["case_id"] / "00_CASE_SPEC" / "seed_replay_dump.json"
    assert dump.exists()
    data = json.loads(dump.read_text(encoding="utf-8"))
    assert data["rng_algorithm"] == "numpy.random.PCG64"
    assert data["seed_value"] in {str(260306001 + i) for i in range(9)}
