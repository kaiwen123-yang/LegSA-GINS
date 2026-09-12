from legsa_gins.paper_rebuild.canonical541.seed_anchor import SEEDS, seed_manifest


def test_seed_manifest_exact():
    assert SEEDS == tuple(range(260306001, 260306010))
    assert len(seed_manifest()) == 9
