from tests.paper10m1r2a_v2_common import EXPECTED_SEEDS, read_csv


def test_seed_manifest_has_exact_fixed_seeds_and_rng():
    rows = read_csv("03_SEEDS/CANONICAL_BY2_RANDOM_SEED_MANIFEST.csv")
    assert [(row["seed_index"], row["seed_value"]) for row in rows] == EXPECTED_SEEDS
    assert {row["rng_algorithm"] for row in rows} == {"numpy.random.PCG64"}


def test_seed_manifest_declares_all_seed_uses():
    rows = read_csv("03_SEEDS/CANONICAL_BY2_RANDOM_SEED_MANIFEST.csv")
    for row in rows:
        assert row["used_for_noise"] == "true"
        assert row["used_for_dropout"] == "true"
        assert row["used_for_spike"] == "true"
        assert row["used_for_outage_start"] == "true"
        assert row["used_for_bias_direction"] == "true"
        assert row["used_for_mixed_components"] == "true"


def test_anchor_manifest_forbids_trace_and_outputs():
    rows = read_csv("03_SEEDS/CANONICAL_BY2_ANCHOR_SELECTION_MANIFEST.csv")
    assert len(rows) == 9
    for row in rows:
        assert row["trace_used_for_selection"] == "false"
        assert row["final_v23_output_used_for_selection"] == "false"
        assert row["legsa_output_used_for_selection"] == "false"
