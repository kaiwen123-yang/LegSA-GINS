# N7C3 Confidence Policy

N7C3 confidence combines solver-visible and Go2-visible evidence:

- N7B4 probabilistic contact confidence
- N7B5 horizontal frame equivalence
- Go2 velocity consistency with receiver-native and raw Doppler velocity
- mode/gait and motion-state plausibility
- time-alignment confidence

The combination is conservative: a weighted harmonic mean is guarded by the
minimum component. This prevents one high component from hiding weak contact,
weak frame equivalence, weak cross-source consistency, or poor alignment.

Outputs:

- `GO2_HORIZONTAL_VELOCITY_CONFIDENCE_REPORT.json`
- `GO2_HORIZONTAL_VELOCITY_CONFIDENCE_TIMESERIES.csv`

Boundary:

- Confidence is not a truth label.
- Go2 velocity is not truth.
- No trace/final_v23 tuning.
- No paper performance claim.
