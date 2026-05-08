# N4H2D Replay Reference Mapping Audit Prompt

Goal: audit whether the old N4H2 replay summary yaw near 93 deg came from stale summary evidence or wrong reference mapping.

Use role aliases:

- `DUAL_FINAL_V23_ARTIFACT_ROOT`
- `N4H2_ARTIFACTS_ROOT`

Do:

- reconstruct official reference from dual NAV plus official error_series
- verify actual dual summary reproduction
- freshly evaluate N4H2 replay NAV against the reconstructed dual official reference
- compare old and fresh replay summaries
- audit stale summary and reference source evidence
- write diagnostic JSON and Markdown reports

Do not:

- modify solver output
- use trace as solver input
- perform output-only correction
- delete epochs
- tune yaw to chase final_v23
- relax yaw above 2 deg
- commit artifacts or raw data
- make a formal performance claim
