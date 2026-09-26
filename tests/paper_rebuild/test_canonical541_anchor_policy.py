import numpy as np
from legsa_gins.paper_rebuild.canonical541.seed_anchor import AnchorContext, place_interval, place_repeated_d07, realize_all_anchors


def test_anchor_and_half_open_placement():
    t = np.linspace(66, 340, 2000)
    context = AnchorContext(t, np.ones_like(t), np.sin(t), np.ones_like(t, dtype=bool), np.ones_like(t, dtype=bool), np.linspace(1, 0, len(t)), np.full_like(t, .35), np.linspace(0, 1, len(t)), np.ones_like(t, dtype=bool), np.ones_like(t))
    rows = realize_all_anchors(context)
    assert len(rows) == 9 and rows[0]["anchor_time_s"] == 206.2
    assert place_interval(66, 20) == (66.0, 86.0)
    intervals = place_repeated_d07(206.2)
    assert [round((a+b)/2-206.2, 8) for a,b in intervals] == [-6, 0, 6]
