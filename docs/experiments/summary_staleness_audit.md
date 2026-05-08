# Summary Staleness Audit

N4H2D compares the old N4H2 summary with the fresh replay summary recomputed against the dual official reference.

Stale or wrong-reference evidence includes:

- old yaw around 93 deg while fresh yaw is around 1 to 3 deg
- old summary timestamp older than replay NAV or report evidence
- old report identifies a reference source other than the dual official reference
- old summary count or metadata no longer aligns with the current replay output

If stale or wrong-reference evidence is present, the old summary must not be used as formal evidence.

Boundary:

- trace remains evaluation-only
- no solver output is modified
- no output-only correction is performed
- no performance claim is made
