# CLEAN1R1C execution status

## Decision

- Stage: `CLEAN1R1C_FROZEN_PROTOCOL_DIRECT_REIMPLEMENTATION_AND_BY2_FORMAL_EXECUTION`
- Protocol: `CLEAN1_BY2_CLEAN_NORMAL_V2_KICK_ALIGNED`
- Code-freeze commit: `0e94fb1047cbe72bb06c2b3072d51b54b5e1f179`
- Terminal status: `PASS_CLEAN1_BY2_KICK_ALIGNED_FOUR_METHOD_FRESH_EVIDENCE_READY_FOR_HUMAN_REVIEW`
- Claim ceiling: BY2 clean-normal descriptive results under the frozen same-source evaluation protocol; human review remains required.

## Frozen execution contract

- Raw lock: 22/22 before provider generation, 22/22 after provider generation, and 22/22 at final audit; mutation count zero.
- Provider bundle: `provider://CLEAN1_BY2_CLEAN_NORMAL_V2_KICK_ALIGNED`, SHA-256 `91607ea3da0eae1452d132aa0ff14565d78efc057afa3f6430a516bdd3f6e7c0`.
- Propagation IMU: `raw://BY2_GO2_BODY/by2.txt`; Fixposition receiver IMU files remained diagnostic-only.
- Measurement lever arm: `[+0.03, +0.03, -0.30] m` in solver FRD, shared by all methods.
- Kick event: absolute Unix time `1772784062.579067`; fixed event-alignment offset `0.0 s`.
- Common window: absolute Unix time `[1772784063.2034607, 1772784350.0910494]`.
- Dual yaw: A1 status mapping, GNSS2 minus GNSS1, GNSS1 right, GNSS2 left, lateral `+Y_left`, fixed `+90 deg` body transform, wrap-safe residual.
- A1 baseline: median `0.356170 m`, P05 `0.311727 m`, P95 `0.409101 m`; 302 provider rows.
- Raw Doppler: fresh pinned RTKLIB B34 `pntpos/estvel` lineage from GNSS1 RAWX/SFRBX, with 1,248 valid epochs; receiver NAV-PVT velocity was not substituted for Raw Doppler.
- Trace access: offline evaluator only, after all four solver outputs were sealed and hashed; no offset, sign, alignment, or metric-driven search.

## Formal runs

| Method | Terminal | Position | Receiver velocity | Dual yaw | Raw Doppler | Source-aware evaluations | Go2 roll/pitch | Go2 horizontal velocity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `single_antenna_EKF` | PASS | 286 | 286 | 0 | 0 | 0 | 0 | 0 |
| `basic_dual_yaw_EKF` | PASS | 286 | 0 | 286 | 0 | 0 | 0 | 0 |
| `strong_dual_yaw_EKF` | PASS | 286 | 286 | 280 | 0 | 0 | 0 | 0 |
| `LegSA_Paper_V1` | PASS | 286 | 286 | 280 | 235 | 1,659 | 286 | 286 |

FGO, QM, QA, and contact/FK counters were zero for every method. The four methods ran once, in the frozen order, in formal session `303b8051de3b40dca3c5114c4591cb67`.

## Current clean descriptive metrics

| Method | Horizontal RMSE (m) | 3D RMSE (m) | Up RMSE (m) | Yaw RMSE (deg) | Yaw MAE (deg) | Coverage |
|---|---:|---:|---:|---:|---:|---:|
| `single_antenna_EKF` | 0.347158 | 0.882634 | 0.811495 | 10.901991 | 9.878095 | 58,128 / 59,331 (97.9724%) |
| `basic_dual_yaw_EKF` | 0.349234 | 0.885124 | 0.813314 | 2.249157 | 1.810894 | 58,128 / 59,331 (97.9724%) |
| `strong_dual_yaw_EKF` | 0.346942 | 0.882562 | 0.811509 | 2.240041 | 1.876279 | 58,128 / 59,331 (97.9724%) |
| `LegSA_Paper_V1` | 0.349252 | 0.916200 | 0.847022 | 2.230108 | 1.871480 | 58,128 / 59,331 (97.9724%) |

The independent aggregate cross-check passed. These values do not establish universal superiority, robustness, generalization, independent ground-truth accuracy, or paper readiness.

## Evidence and boundary

- Final evidence alias: `evidence://CLEAN1R1C_KICK_ALIGNED_FOUR_METHOD_EXECUTION/FINALIZED`.
- Evidence-manifest SHA-256: `56be5ce178bb0d795fe883552707d92ab4015ed0fcdee9656158f37444dcfebf`.
- Reference role: `FIXPOSITION_SAME_SOURCE_EVALUATION_REFERENCE`; `independent_ground_truth=false`.
- Position interpretation: `SAME_SOURCE_DIRECT_COMPARE_WITH_MOUNTING_CAVEAT`; no evaluator point compensation and no primary absolute-position claim.
- Historical performance results, providers, runtimes, rows, aggregates, and figures were not reused.
- Formal results were freshly regenerated from the current hash-locked raw inputs.
- No paper figures were generated; the stage PR must remain unmerged pending human review.
