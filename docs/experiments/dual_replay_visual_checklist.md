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

This checklist is visual evidence only. It does not modify solver output, does not relax gates, and does not make a formal performance claim.

