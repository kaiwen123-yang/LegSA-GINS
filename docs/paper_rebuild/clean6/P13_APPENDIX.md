# P13 appendix

## 2026-09-14 human adjudication

All five draft conflicts B01-B05 are resolved in SENSOR_MODEL_V21_CONTRACT.yaml. The old binary, v1/v2 outputs, original decision rules and Outcome remain preserved. The new native binary changes only the F02 fixed-yaw-standard-deviation guard to also accept 2.933193 degrees. This value is below the unchanged scheme-C soft threshold of 3.0 degrees.

The identity bridge uses unchanged CAL C00 inputs and std=1.5 with both binaries across all eleven profiles, comparing the four NAV/STD files byte-for-byte. It precedes all v2.1 use of the new binary.

## Validation definitions fixed before providers

- HV residual reproduction uses the inverse-scaled new provider, retaining exact P-11b samples and statistics; final scaled residuals are reported separately.
- GNSS source hashes remain fixed. New nominal and case tables preserve non-yaw_std tokens against their corresponding unchanged/injected reference. Every nominal yaw_std token is 2.933193. Frozen fault handlers are then applied in their original order: a registered yaw_std multiplier (including D28) multiplies this new nominal value in the actual injected yaw_std column. The gate compares against the same frozen handler applied to the nominal v2.1 table, rather than erasing the registered fault to enforce a constant injected column.
- Existing frozen_parameter_hash is unchanged. SENSOR_MODEL_V21 is separately hashed as three correction groups; runtime/provider diffs remain explicit.
- Case-specific injected A1 determines HV rotation/support. Fully absent A1 makes all HV invalid; missing source Go2 validity is never promoted.
- F01 sampling is C00 plus 49 non-C00 core cases ordered by SHA256 of P13_F01|case_id; the contract contains all fifty identities. Its seven scientific output files are compared to the original full-file seals, never to downsampled substitutes.
- H7 uses the existing evaluator yaw_abs_error_over_std_median. H7-H11 are reported by applicable profile/sequence/seed and evaluator; no post-hoc pooling changes a failed or missing component. Definitions are recorded in the contract.
- BY2 clean sequence and core C00 are the same ten rerun identities: 5890 requested entries, 5880 unique main-chain reruns, 50 F01 audit runs and 22 bridge runs; downstream diagnostics are recorded separately.

## Stop policy

Only non-preregistered native solver failure, evaluator failure/nonfinite results, F01/bridge/HV-RP reproduction failure, or batch archive failure above one percent stops this task. Validation mechanism, bookkeeping and wording conflicts are resolved by preserving science and recording the exact disposition here. No completed solver/evaluator run is silently repeated.

## Execution records

Contract preparation only at this entry: provider, solver, evaluator and plotting calls are zero. Subsequent entries record exact commands, identities, gates, bookkeeping adjustments and terminal states.

## Binary build implementation

The implementation stores BINARY_FREEZE.json beside the bridge evidence at 01_BINARY_BRIDGE/BINARY_FREEZE.json; the controller resolves this path instead of the initial 00_PREREGISTRATION label. This changes bookkeeping only. Independent read-only review passed the sole native source change and bridge implementation before launch.

## Binary bridge and provider implementation freeze

At code commit ca73cb1fb48a020fd2a450d79e520562c34eeb24, the bridge completed 22 native calls and passed all 44 full NAV/STD comparisons across C00 and eleven profiles. The old executable SHA256 is 9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f; the new executable SHA256 is 96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c. Provider and evaluator calls in the bridge are zero.

The provider implementation passed independent read-only review and 17 focused tests before real provider generation. Eight downstream adapter tests also passed without provider, native or evaluator execution. These implementation checks do not replace the pending real three-sequence residual gates.

## Three-sequence real provider gate
Provider commit: d01f2be8fb0ef1633d4871ec57b0e6d4e9de44a7. Raw PRE checkpoint: 22/22 PASS. Provider access audit: zero forbidden opens, zero raw writes, zero writes outside the owned output root.
| Sequence | HV matched n | Inverse-k sigma (m/s) | Final scaled sigma (m/s) | Corrected static pitch mean (deg) | Statistics compared | Maximum absolute difference |
|---|---:|---:|---:|---:|---:|---:|
| BY2 | 16968 | 0.13283767493317 | 0.131450299108858 | -0.444112110441446 | 183 | 8.3266726846886741e-17 |
| BY2H | 17558 | 0.210120538793595 | 0.211255196456088 | -0.420844093009067 | 183 | 2.7755575615628914e-17 |
| BY2O | 23022 | 0.106398459795671 | 0.103633801029819 | -0.412028739877216 | 233 | 1.1102230246251565e-16 |

All three residual gates pass 1e-6. Nominal 15/18-column GNSS non-yaw_std token equality and all-2.933193 yaw_std gates pass for 1510/1483/2231 rows. All three IMU and RD hashes match their frozen V2s pins. Scaled residuals are reported separately from the inverse-k reproduction gate.
