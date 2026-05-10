# N5C Ablation Decision

N5C produces diagnostic engineering evidence and a next-stage recommendation.

Decision rules:

- `raw_doppler_update_count == 0`: activation failed; return to activation or alignment repair.
- Time alignment failure: move to raw Doppler time-alignment repair.
- Source-copy suspicion: move to source-integrity repair.
- Neutral or improved `baseline_plus_raw_doppler_r1`: move to visual validation and stress protocol.
- Significant diagnostic degradation: move to noise-model or gating follow-up.
- Improvement in `position_yaw_plus_raw_doppler_r1` over `position_yaw_only` is evidence that raw Doppler can act as an independent velocity constraint, but it is diagnostic-only.

RTKLIB position solution must not be used as LegSA solver input.

paper performance claim: false.
No outperform final_v23 claim is made.
