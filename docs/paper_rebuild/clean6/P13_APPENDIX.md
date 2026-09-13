# P13 appendix

## 2026-09-14 human adjudication

All five draft conflicts B01-B05 are resolved in SENSOR_MODEL_V21_CONTRACT.yaml. The old binary, v1/v2 outputs, original decision rules and Outcome remain preserved. The new native binary changes only the F02 fixed-yaw-standard-deviation guard to also accept 2.933193 degrees. This value is below the unchanged scheme-C soft threshold of 3.0 degrees.

The identity bridge uses unchanged CAL C00 inputs and std=1.5 with both binaries across all eleven profiles, comparing the four NAV/STD files byte-for-byte. It precedes all v2.1 use of the new binary.

## Validation definitions fixed before providers

- HV residual reproduction uses the inverse-scaled new provider, retaining exact P-11b samples and statistics; final scaled residuals are reported separately.
- GNSS source hashes remain fixed. New nominal and case tables preserve non-yaw_std tokens against their corresponding unchanged/injected reference. The yaw_std column is set to 2.933193 on every row. A frozen fault handler that changes yaw_std is logged explicitly and its scientific effect retained in a separately declared field only if needed; no conflict may be silently masked.
- Existing frozen_parameter_hash is unchanged. SENSOR_MODEL_V21 is separately hashed as three correction groups; runtime/provider diffs remain explicit.
- Case-specific injected A1 determines HV rotation/support. Fully absent A1 makes all HV invalid; missing source Go2 validity is never promoted.
- F01 sampling is C00 plus 49 non-C00 core cases ordered by SHA256 of P13_F01|case_id; the contract contains all fifty identities. Its seven scientific output files are compared to the original full-file seals, never to downsampled substitutes.
- H7 uses the existing evaluator yaw_abs_error_over_std_median. H7-H11 are reported by applicable profile/sequence/seed and evaluator; no post-hoc pooling changes a failed or missing component. Definitions are recorded in the contract.
- BY2 clean sequence and core C00 are the same ten rerun identities: 5890 requested entries, 5880 unique main-chain reruns, 50 F01 audit runs and 22 bridge runs; downstream diagnostics are recorded separately.

## Stop policy

Only non-preregistered native solver failure, evaluator failure/nonfinite results, F01/bridge/HV-RP reproduction failure, or batch archive failure above one percent stops this task. Validation mechanism, bookkeeping and wording conflicts are resolved by preserving science and recording the exact disposition here. No completed solver/evaluator run is silently repeated.

## Execution records

Contract preparation only at this entry: provider, solver, evaluator and plotting calls are zero. Subsequent entries record exact commands, identities, gates, bookkeeping adjustments and terminal states.
