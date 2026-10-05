# Sensitivity to measured support and IMU interruptions

The existing H and O records contain one and six internal IMU interruptions. The supplementary segmented diagnostic is compared with the original implementation on all 22 method–sequence members. Analysis domains are fixed by the recorded interruption times: the 5 s preceding each gap, its open physical interval, the first observed record after it, (0,5] s and (5,30] s after it, and the remaining recording. Overlapping near-gap intervals are combined once for the sequence summary. The original and diagnostic errors are compared at exact common microsecond keys.

## Output support

| Sequence | Methods | Internal gaps | Original recorded epochs | Diagnostic matched epochs per method | Waiting records | Restart seeds | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|
| BY2H | 11 | 1 | 58,580 | 58,556 | 23 | 1 | 99.9590% |
| BY2O | 11 | 6 | 76,548 | 72,810 | 3,732 | 6 | 95.1168% |

The physical gaps contain no recorded output epoch and therefore do not generate interpolated samples or nominal-rate denominator entries. The longest input-qualified restart wait was 20.142953 s in BY2O: the next segment started at 3392.657047 s, a position-and-heading initialization became available at 3412.799999952 s, the seed was at 3412.805279 s, and output resumed at 3412.809049 s. This restart accounts for 3606 waiting records and one seed. The BY2H startup-boundary interruption is separate from the seven internal gaps.

## Proposed configuration: original and diagnostic errors

H, V and 3D are in metres, yaw is in degrees. The near-gap domain is the union of [last-pre-gap-time−5 s, first-post-gap-time+30 s]; its complement is the far domain. Own-support and common-support values are both displayed.

| Sequence | Domain | Quantity | Original own support | Original common support | Diagnostic common support | Common epochs / original domain |
|---|---|---|---:|---:|---:|---:|
| BY2H | FULL | H | 0.068362 | 0.068369 | 0.068056 | 58556/58580 |
| BY2H | FULL | V | 0.045352 | 0.045268 | 0.045332 | 58556/58580 |
| BY2H | FULL | 3D | 0.082038 | 0.081997 | 0.081772 | 58556/58580 |
| BY2H | FULL | yaw | 1.933770 | 1.933754 | 1.941476 | 58556/58580 |
| BY2H | NEAR_GAP_UNION | H | 0.042751 | 0.042718 | 0.042168 | 6888/6912 |
| BY2H | NEAR_GAP_UNION | V | 0.039296 | 0.038438 | 0.037759 | 6888/6912 |
| BY2H | NEAR_GAP_UNION | 3D | 0.058068 | 0.057466 | 0.056603 | 6888/6912 |
| BY2H | NEAR_GAP_UNION | yaw | 2.638213 | 2.640241 | 2.669097 | 6888/6912 |
| BY2H | FAR_FROM_GAP | H | 0.071092 | 0.071092 | 0.070796 | 51668/51668 |
| BY2H | FAR_FROM_GAP | V | 0.046102 | 0.046102 | 0.046248 | 51668/51668 |
| BY2H | FAR_FROM_GAP | 3D | 0.084732 | 0.084732 | 0.084563 | 51668/51668 |
| BY2H | FAR_FROM_GAP | yaw | 1.818959 | 1.818959 | 1.822662 | 51668/51668 |
| BY2O | FULL | H | 0.054543 | 0.055648 | 0.054444 | 72810/76548 |
| BY2O | FULL | V | 0.045859 | 0.044285 | 0.041537 | 72810/76548 |
| BY2O | FULL | 3D | 0.071260 | 0.071118 | 0.068479 | 72810/76548 |
| BY2O | FULL | yaw | 2.433815 | 2.492247 | 2.412522 | 72810/76548 |
| BY2O | NEAR_GAP_UNION | H | 0.066009 | 0.068961 | 0.067215 | 35201/38939 |
| BY2O | NEAR_GAP_UNION | V | 0.048810 | 0.046028 | 0.040042 | 35201/38939 |
| BY2O | NEAR_GAP_UNION | 3D | 0.082095 | 0.082911 | 0.078238 | 35201/38939 |
| BY2O | NEAR_GAP_UNION | yaw | 3.044360 | 3.196666 | 3.157752 | 35201/38939 |
| BY2O | FAR_FROM_GAP | H | 0.039292 | 0.039292 | 0.038858 | 37609/37609 |
| BY2O | FAR_FROM_GAP | V | 0.042588 | 0.042588 | 0.042888 | 37609/37609 |
| BY2O | FAR_FROM_GAP | 3D | 0.057945 | 0.057945 | 0.057874 | 37609/37609 |
| BY2O | FAR_FROM_GAP | yaw | 1.568599 | 1.568599 | 1.391013 | 37609/37609 |

## Manuscript-ready paragraph

**Sensitivity to recorded support.** The segmented sensitivity analysis retained 58,556 of 58,580 recorded epochs in BY2H and 72,810 of 76,548 in BY2O for each of the eleven configurations. For the Proposed configuration on exact common support, whole-recording horizontal RMSE changed from 0.068369 to 0.068056 m in BY2H and from 0.055648 to 0.054444 m in BY2O. In the BY2O near-gap domain, separate-support horizontal RMSEs were 0.066009 and 0.067215 m, while common-support values were 0.068961 and 0.067215 m. Away from the interruptions, the corresponding values were 0.039292 and 0.038858 m. These results show why output availability and same-time comparisons are reported alongside whole-recording errors.

The comparison is between the original V3 and the existing segmented compound diagnostic, which also uses explicit measured IMU durations, different heading prediction, covariance/Jacobian processing and input-qualified reinitialization. It is a version-and-support sensitivity analysis; the original V3 result tables remain the primary matrix. All eleven methods and all seven internal interruptions are retained, including domains with no common output.

## Saved tables and reproduction

- `GAP_SUPPORT_SUMMARY_2.csv`: sequence-level coverage and wait/seed decomposition.
- `GAP7_RESTART_SUPPORT_COMPACT.csv`: all seven interruption/restart records; the fields are identical across the eleven methods for each interruption.
- `GAP7_ALL22_RESTART_SUPPORT_77.csv`: every method-specific restart record.
- `GAP22_WHOLE_AND_COMMON_SUPPORT_88.csv`: all22×4 quantities on original own, original common and diagnostic common support.
- `GAP22_FIXED_DOMAINS_1804.csv`: all22 members, sequence domains and per-interruption domains, with every original denominator and missing count.
- `GAP22_DOMAIN_RANKINGS_792.csv` and `GAP22_RANK_SENSITIVITY_48.csv`: all11 rankings on full/near/far domains for H/V/3D/yaw; both support-only and compound-version changes are retained.
- `GAP_PROPOSED_COMMON_DOMAINS_24.csv`: the compact Proposed table above.
- `V07_DOMAIN_SPECIFICATION_BEFORE_REDUCTION.json`: fixed time domains written before error reduction.
- `summarize_saved_gap_versions.py` and `GAP22_REDUCTION.json`: read-only reducer and before/after input hashes. All44 saved error files were read; their complete RMSEs reproduce the original and diagnostic aggregates with maximum difference 4.44×10⁻¹⁶. No raw or reference stream was opened and no estimator/evaluator was invoked.

The physical-gap domain is empty because no measured record exists there. The first post-gap record and other unavailable common domains remain explicit rows with missing support and no finite diagnostic score. No earlier endpoint is substituted and no output is interpolated across gaps.
