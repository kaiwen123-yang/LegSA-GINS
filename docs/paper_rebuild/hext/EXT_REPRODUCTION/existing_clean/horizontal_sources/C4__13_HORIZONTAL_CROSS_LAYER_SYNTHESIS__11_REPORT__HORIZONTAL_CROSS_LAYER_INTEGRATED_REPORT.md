
# LegSA-GINS horizontal cross-layer integrated report

Terminal target: `PASS_CLEAN4_HORIZONTAL_CROSS_LAYER_DATA_ORGANIZED_AND_COMPLETENESS_AUDITED`.

This report is a read-only integration of frozen CSV/JSON/MD evidence. It did not rerun any method, solver, evaluator, MATLAB, Canonical runner, Classic-18, or plotting runner. Fixposition is a **same-source offline evaluation reference**, not independent ground truth; the pose-point and mounting boundary remains explicit.

## 1. Method registry and count

There are **11 registered entities** and **10 formal methods**:

- Layer A raw dual-antenna: 3 formal methods — RAW01/EXT01, RAW02/EXT02, RAW03/EXT03.
- Layer B solution-level LC: 2 — LC01 Pavlasek and LC02 GINav.
- Layer C proprioceptive observability: 1 — LSE01 Hartley.
- Internal LegSA: 4 — F02, F03, A04, F04.
- EXT04 is the eleventh entity but is supplementary and is not counted among the three primary raw methods or the ten formal methods.

## 2. Three raw dual-antenna methods

RAW01 is the constrained integer least-squares/C-LAMBDA family: 1,077/1,509 integer results were returned and globally certified, but no ambiguity-acceptance test is defined. Persistent fractional-DD phase bias remains unresolved, so its BY2 conclusion is `UNSUPPORTED_EXT01_ON_BY2_WITHOUT_PHASE_BIAS_CALIBRATION`.

RAW02 is the faithful C-WLS reproduction: 1,057/1,509 accepted wrapped outputs and 452 invalid rows. “Accepted wrapped” is not “correct ambiguity,” and physical heading applicability is poor.

RAW03 is the faithful Yang 2024 recursive DD-KF + M-LAMBDA reproduction with a declared stochastic instantiation. The frozen primary applicability mode has 609/1,509 valid rows, 105 paper-ratio-fixed rows, and 900 invalid rows; 101/105 ratio-fixed rows are proxy-inconsistent. All ten modes remain in the tables; no mode was chosen by reference error.

EXT04 is only `SUPPLEMENTARY_DIAGNOSTIC_MODULE`, `PAPER_DERIVED_POLICY_BASELINE`, and `NOT_COUNTED_IN_THE_THREE_PRIMARY_RAW_METHODS`. Its 27 declared policy/mode branches have zero accepted epochs because the exact PAR policy is under-specified and all branches fail the declared gates.

## 3. LC01 / GINav solution-level LC

LC01 Pavlasek is a valid dual-receiver, solution-level comparator. It uses P1 absolute position plus the P2-P1 rigid relative vector and correlated measurement covariance. Its standalone formal C00 covers 58,014/58,014 rows (100%). RMSE: horizontal 0.1691391165921043 m, 3D 0.3790089605253968 m, roll/pitch/yaw 1.2095627529559005/1.5676244070222305/2.9948274600591076°.

GINav is an exact official software reproduction of a standard 15-state SPP/INS loosely coupled baseline, not a novel filter method. Formal row coverage is **77/275 = 28.0%** and temporal-span coverage **62.043%**; alignment delay is 113.002 s, with 295 configured epochs, 116 official eligible epochs, SPP valid/invalid 48/68, 80 native rows, 11 LC updates, 68 INS-only rows, maximum gap 11 s, and 38 formal segments. Formal RMSE is horizontal 130.8187259110151 m, 3D 219.88371098234956 m, roll/pitch/yaw 14.936207000465183/14.107014661009151/69.75333248293973°. The correct applicability conclusion is `EXACT_OFFICIAL_ROUTE_WITH_POOR_BY2_ACCURACY_AND_AVAILABILITY`.

## 4. Hartley yaw unobservability

The Hartley route is scientifically complete as `PASS_LSE01_COMPLETE_WITH_REFERENCE_EXTRINSIC_LIMITATION`: 63,277 real native state rows, full-precision yaw-gauge equivalence, and stable numerical observability. The structural nullity is four—three global translations and one gravity-axis yaw—for 2-contact and 4-contact windows, including the bias-augmented model. Twenty-four topology-conditioned NIS groups are retained.

This proves global translation/yaw gauge, real-data gauge equivalence, and numerical observability. It does not prove “poor yaw accuracy” and cannot supply absolute position or yaw RMSE. H7/H7C remains a reference-extrinsic limitation archive, not an active algorithm blocker.

## 5. Internal F02/F03/A04/F04

Current full-window C00 RMSE values are:

| Method | H m | 3D m | Roll ° | Pitch ° | Yaw ° |
|---|---:|---:|---:|---:|---:|
| F02 | 0.35552607969271205 | 0.893101601000678 | 1.031475285698871 | 1.524123850435799 | 2.3384266253352437 |
| F03 | 0.352517110036549 | 0.8905809096536953 | 1.0244530231621092 | 1.523894981413622 | 1.9624133174349125 |
| A04 | 0.35238638733674005 | 0.8903584609765574 | 1.01764982040405 | 1.5222193469113123 | 1.9340756561653565 |
| F04 | 0.3548025409632719 | 0.9263782283427902 | 1.0194643508248697 | 1.5218917293925804 | 1.9549590248265367 |

A04 is the `core/main-method candidate`; F04 is the `quality-mismatch and tail-protection extension`. Final paper identity remains `PROVISIONAL_PENDING_GENERALIZATION`.

## 6. Cross-layer information structure and fairness

Direct numerical comparison is admissible for F02/F03/A04/F04 under the same Canonical C00/541 contracts. LC01, GINav, and internal methods can be reported with coverage-aware full-navigation metrics, but they use different online information and formal support. RAW methods can be compared only at native availability/baseline-heading mechanism level. EXT04 is mechanism-only. Hartley is structural-only.

Thus raw-carrier heading backends, solution-level full navigation, proprioceptive gauge observability, and internal LegSA full navigation do not form a flat fair ranking of filter formulas.

## 7. Normal C00 primary results

The legal full-navigation C00 table is `SOLUTION_LEVEL_LC_C00_FORMAL_SUMMARY.csv` plus `INTERNAL_FORMAL_C00_SUMMARY.csv`; each method retains its own formal support and coverage. GINav’s low coverage is never hidden by deleting the missing prefix.

The 77-epoch values A04=**2.2310550147062354°** and F04=**2.226266687869817°** are `COMMON_SUPPORT_REFERENCE_INDEPENDENT_BRACKET_INTERPOLATION_DIAGNOSTIC_ONLY`, not formal C00. The raw six-way literal timestamp intersection is zero. Historical **1.813898158169119°** is `LEGACY_FINAL_V23_RESULT`, not current Canonical C00 and not used for ranking.

## 8. Availability and failure mechanisms

Availability is a first-class result: RAW native states preserve distinct meanings; EXT04 has zero acceptance; LC01 is full-support; GINav combines late alignment, low SPP/LC availability, and severe errors; Hartley has legal native/gauge evidence but no absolute metric; internal methods have full C00 coverage. Missing or inapplicable metrics remain NA rather than zero.

## 9. Canonical-541 internal robustness

The completed Canonical aggregate reports 541-case means separately from C00:

| Method | H mean m | 3D mean m | Roll mean ° | Pitch mean ° | Yaw mean ° |
|---|---:|---:|---:|---:|---:|
| F02 | 1.0660951649957948 | 1.6611295645112392 | 1.4212262784354055 | 1.7944610428695729 | 5.702271937739465 |
| F03 | 0.9398033611839849 | 1.5577604811605639 | 1.3701762359851484 | 1.781465863091135 | 6.436739822920733 |
| A04 | 0.9352351185618887 | 1.5541718196752616 | 1.3580804208359414 | 1.7721513026098918 | 6.498097772981546 |
| F04 | 0.9428380211794175 | 1.5865019284246893 | 1.2732615078105713 | 1.674898645747707 | 5.329333015842954 |

For F04 minus A04: H mean delta 0.0076029026175286965 m with 86/541 wins; 3D mean delta 0.032330108749427634 m with 43/541 wins; yaw-RMSE mean delta -1.1687647571385906° but median delta 0.020883368661180235° with 71/541 wins; yaw-P95 mean delta -1.833176556584313° with 407/541 wins. This mixed evidence motivates the core/extension split, not universal superiority.

Only a global runtime row is available in the allowed aggregate (`count=5951`, mean wall-time field 4046.777897469001 s, total CPU time 26165.463577 s). Per-method runtime aggregate is `NOT_AVAILABLE_IN_ALLOWED_AGGREGATE`; none is inferred.

## 10. Horizontal comparison completeness

The route set covers constrained integer least squares/C-LAMBDA, wrapped least squares, recursive DD filtering + M-LAMBDA, dual-receiver invariant filtering, official single-receiver standard LC, proprioceptive contact-aided gauge observability, and internal Basic/Strong/Core/Full. It is comprehensive for the current cross-layer claims. No additional external algorithm is required by an uncovered claim-critical route.

## 11. Corrected Classic-18 decision

Decision: `CONDITIONALLY_REQUIRED_ONLY_IF_MAIN_TEXT_CLAIMS_EXTERNAL_DEGRADATION_SUPERIORITY`.

Current cross-layer claims do not require it. If that external-degradation superiority claim is retained, the only method set is LC01, F02, F03, A04, F04. GINav, EXT01–EXT04, and Hartley are excluded for the documented availability/applicability/structural reasons. Classic-18 was not started.

## 12. Remaining evidence gaps

The material gaps are independent ground truth, additional real platform/sequence generalization, a real one-side antenna-occlusion sequence, cross-platform generalization, and publication-quality plotting. “Add more horizontal algorithms” is not the default gap.

## 13. Pending plot linkage

`PLOT_LINKAGE_PENDING.csv` links claims to the raw-availability, raw-heading, EXT04 rejection, solution-LC formal, GINav mechanism, Hartley gauge/observability/NIS, internal C00, A04/F04 Canonical-541, module-action, cross-layer comparability, and coverage-gap tables. Every row is `PENDING_PARALLEL_CANONICAL_PLOTTING_COMPLETION`, with future path NA. Plotting access and execution counts are zero in this task.
