# BY2 Measurement Floor Sanity

Stage N4H0 evaluates the receiver-native measurement floor before implementing a full KF-GINS-style EKF reconstruction.

The stage directly converts BY2 `gnss1` and `gnss2` receiver-native GNSS status into EVAL_NAV-like rows and compares them with the trace reference in evaluation-only mode. It does not run the LegSA-GINS proposed solver and it does not generate proposed solver outputs.

## Purpose

- Measure direct receiver-native position error against trace.
- Measure direct receiver-native rel_pos heading candidates against trace yaw.
- Separate input/evaluator issues from filter update or mechanization issues.
- Decide whether N4H full EKF reconstruction is a reasonable next diagnostic stage.

## Boundaries

- trace is evaluation-only.
- `trace_solver_input: false`.
- no final_v23 output is used as proposed input.
- no raw Doppler, Go2 prior, source-aware weighting, LSIM/OIM, or FGO is implemented.
- no tuning to final_v23.
- no deletion of bad epochs.
- no output-only correction.
- no formal performance claim.

## Measurement Floor Logic

For each receiver source, N4H0 uses event-normalized `algo_time_sec` and evaluates three heading candidates:

- `no_offset`;
- `plus90`;
- `minus90`.

Position metrics are computed from direct receiver latitude, longitude, and height. Heading metrics use the receiver baseline heading plus the diagnostic mounting offset candidate. The transverse dual-antenna mounting offset is not formally selected because antenna order still needs physical confirmation.

## Interpretation

If the measurement floor itself is poor, the next step should be an input-source, evaluator, or final_v23 input parity audit rather than immediate filter tuning.

If the measurement floor is good but the N4G filter diagnostic result is poor, then filter update or mechanization is a likely issue and N4H full KF-GINS-style EKF reconstruction becomes the recommended next stage.

N4H0 is not final_v23 parity evidence and must not be described as proposed solver performance.
