# N4H2E Visual Review Checklist

Manual visual review is required before merging the current evidence branch or moving to N4H3.

Check:

1. Local trajectory reference and replay estimate overlap without obvious branch swaps.
2. Start and end segments do not show jumps or reset artifacts.
3. Height curves do not show unexpected drift or discontinuity.
4. North, east, and up errors remain stable over the nominal window.
5. Horizontal error does not contain unexplained spikes.
6. Yaw error does not contain wrap spikes or sawtooth discontinuities.
7. Roll and pitch errors are concentrated within the relaxed range, while strict status remains reported separately.
8. 3-sigma consistency figures do not show obvious missing-field or scale problems.
9. Observation yaw and reported standard deviations do not have strange jumps.
10. Summary panel values match the JSON metrics snapshot.
11. Opening bumps are marked as startup/convergence transients, not cropped away.
12. Yaw STD figures are interpreted as observation/state uncertainty, not automatic proof of injected yaw noise.
13. Process-data provenance report identifies whether actual input is closer to no-noise or noisy variants.
14. final mainline degradation/stress batch evidence is not reused as clean nominal evidence.

This checklist is visual evidence only. It does not modify solver output, does not relax gates, and does not make a formal performance claim.
