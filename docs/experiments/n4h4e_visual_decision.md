# N4H4E Visual Decision

`visual_candidate_passed=true` requires:

- monotonic port, final_v23, and reference time axes;
- no NaN/Inf numeric values;
- enough aligned port-vs-final_v23 samples;
- required figures generated;
- port-vs-final_v23 parity remains small;
- final_v23 absolute summary is reproduced;
- port absolute metrics are close to final_v23 absolute metrics;
- no yaw wrap spike;
- no gross trajectory discontinuity.

`visual_candidate_passed` is an engineering candidate decision only. Manual
visual review is still required before starting N5.

If the visual candidate passes, the recommended next stage is
`N5_raw_doppler_factor_foundation`. If it fails, the recommended next stage is
`N4H4E_visual_anomaly_debug`.

N4H4E does not implement raw Doppler. It only decides whether the source-backed
backbone visual evidence is clean enough to make N5 a reasonable next stage.
