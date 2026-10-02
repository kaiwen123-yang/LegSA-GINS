# Final horizontal comparison report

## Result

The result identity is corrected. The primary table now uses each method's own valid formal/native C00 result with actual coverage; the 77-epoch GINav-defined grid is isolated as diagnostic-only. Final status: `PASS_CLEAN4_HORIZONTAL_RESULT_IDENTITY_CORRECTED_AND_FINAL_EVIDENCE_INTEGRATED`.

## Formal C00 table

| Method | Scope | Matched / coverage | H RMSE m | 3D RMSE m | Roll deg | Pitch deg | Yaw deg |
|---|---|---:|---:|---:|---:|---:|---:|
| GINAV | GINAV_COVERAGE_AWARE_FORMAL_WINDOW | 77 / 0.28 | 130.818725911 | 219.883710982 | 14.936207000 | 14.107014661 | 69.753332483 |
| LC01 | LC01_STANDALONE_FULL_C00 | 58014 / 1.0 | 0.169139117 | 0.379008961 | 1.209562753 | 1.567624407 | 2.994827460 |
| F02 | CURRENT_CANONICAL_FULL_C00 | 56642 / 1.0 | 0.355526080 | 0.893101601 | 1.031475286 | 1.524123850 | 2.338426625 |
| F03 | CURRENT_CANONICAL_FULL_C00 | 56642 / 1.0 | 0.352517110 | 0.890580910 | 1.024453023 | 1.523894981 | 1.962413317 |
| A04 | CURRENT_CANONICAL_FULL_C00 | 56642 / 1.0 | 0.352386387 | 0.890358461 | 1.017649820 | 1.522219347 | 1.934075656 |
| F04 | CURRENT_CANONICAL_FULL_C00 | 56642 / 1.0 | 0.354802541 | 0.926378228 | 1.019464351 | 1.521891729 | 1.954959025 |

This table is `NATIVE_OR_FORMAL_C00_RESULTS_WITH_COVERAGE`, not a strict-common-timestamp ranking. GINav has 77/275 row coverage (28.0%), temporal-span coverage 62.043%, alignment delay 113.002 s, 295 configured epochs, 116 eligible epochs, SPP valid/invalid 48/68, 80 native rows, 11 LC updates, 68 INS-only rows, 11 s maximum gap, and 38 formal-window segments. Its poor result contains both low availability and low accuracy.

## Diagnostic identity correction

The existing 77-epoch table has raw six-way literal intersection 0 and is registered only as `COMMON_SUPPORT_REFERENCE_INDEPENDENT_BRACKET_INTERPOLATION_DIAGNOSTIC_ONLY`. A04 2.231055 deg and F04 2.226267 deg are diagnostic values, not formal C00. Current Canonical full-C00 yaw RMSE is A04 1.934075656 deg and F04 1.954959025 deg. Historical final_v23 yaw RMSE 1.813898158 deg is `LEGACY_FINAL_V23_RESULT`, `not_current_canonical_C00=true`, and `not_used_for_current_ranking=true`.

## Method roles and cross-layer boundary

LC01 is a valid dual-receiver solution-level comparator. GINav is an exact official SPP/INS LC route with coverage-aware C00 reporting. EXT01-EXT04 are raw dual-antenna applicability evidence, not full-NAV filter comparators. Hartley proves only the three-dimensional global translation gauge plus gravity-axis yaw gauge, real-data gauge equivalence, and numerical observability; it has no absolute position/yaw RMSE.

Different information layers cannot be described as a fair ranking of filter formulas alone. A04 is the `core/main-method candidate`; F04 is the `quality-mismatch and tail-protection extension`; final paper method identity remains `PROVISIONAL_PENDING_GENERALIZATION`. The role uses full Canonical C00, frozen Canonical-541 pairwise/profile statistics, and frozen module/degradation evidence, never the 77-epoch diagnostic.

## Corrected Classic-18

Not currently required for identity correction or provisional role. It is conditionally required only if an external-degradation horizontal-comparison claim is retained, and then the unique method set is `LC01, F02, F03, A04, F04`. No Classic-18 or other algorithm was run.
