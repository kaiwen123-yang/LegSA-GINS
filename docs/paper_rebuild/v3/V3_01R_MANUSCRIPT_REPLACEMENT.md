# Protocol v3 manuscript replacement text

Status: all ten figure groups passed machine and actual visual review; numerical tables remain the reviewed version. DONE was recorded at 2026-09-22T08:22:35.752561+00:00. The user explicitly omitted the handoff archive; the G: stage evidence and recorded hashes are authoritative.

This replacement is limited to the user-authorized protocol-v3 heading-input
experiment. The archived protocol-v2.1 results and figures remain unchanged.
Scientific freeze: `7d43b9af26120ed5dde21f53e515386361072ba6`.
The source identities and configuration were fixed before evaluation; the
retained outputs are bit-reproducible under the same software version and configuration.
Aggregation-only repair: `76153ae374a100ee70f5b8b6bb2a9d03f7f7bc72`.
Figure/validator repair: `6b8d7aa5ed145fe9f2eb68811dcbc5f4ee1fa92c`.
This file is the revised manuscript replacement; the earlier generated draft
under `07_AGGREGATE` is retained unchanged as part of the reviewed manifest.

## Methods: heading input and validity

Protocol v3 replaces the scalar dual-antenna heading input with scalar body-yaw
observations derived from the raw 5 Hz HPPOSECEF position streams of the two
GNSS receivers. Receiver observations
are paired by exactly equal integer iTOW values. The lateral baseline is
GNSS2 minus GNSS1, with GNSS1 on the robot's right and GNSS2 on its left. The
baseline is converted to body yaw using the frozen physical coordinate and
installation transforms; the scalar heading residual remains wrap-safe.
Baseline direction is not identified directly with body yaw.

The R5 validity rule, fixed before evaluation, requires an exactly matched raw heading and
NAV-PVT carrier-solution state 2 (RTK fixed) for both receivers at that epoch.
An absent raw pair or missing carrier-state record is invalid. Float solutions
are not admitted by this rule. No interpolation, neighbouring-epoch substitution
or time-offset correction is used to recover missing matches. Registered
heading outages and dropouts additionally disable their prescribed epochs.
In D57, the frozen perturbed time tokens have no eligible exact matches; its
absence of valid heading input is retained as an explicit failure category.

The nominal heading standard-deviation marker remains 2.933193 degrees. This
is the inherited protocol-v2.1 marker, not a new estimate of independent 5 Hz
measurement noise. The solver binary, evaluator, initialization, covariance,
process noise, weighting and gating parameters, cases, seeds and configuration
set remain frozen. Only the yaw and yaw-valid columns of each corresponding
GNSS table are replaced; all other input tokens and the IMU, Raw Doppler,
Go2 roll/pitch and horizontal-velocity provider bytes remain unchanged.

As a limitation of the heading-fault mapping, the original heading perturbations
and dropout realizations are transferred to the 5 Hz table by the original
one-second time cells; they are not independently redrawn at 5 Hz. Faults in
the heading standard deviation apply only to their original rows and are not propagated to
the intervening 5 Hz rows. The dual_yaw family is reported only as a protocol-v3
result with this mapping, without interpreting its difference from v2.1 as an
improvement. Horizontal-velocity priors
retain their status-heading rotation and original injected conditions; they
are not regenerated using the new raw heading. Consequently, this experiment
isolates the direct scalar heading input and does not establish a fully
synchronized raw-heading and velocity-prior model.

## Evaluation and reporting

The evaluation reference is the fused navigation output of the commercial receiver, which the estimator under test does not read.
The receiver is the Fixposition Vision-RTK 2; its output is used for offline
evaluation and does not establish independent ground truth.
The figure labels “Truth” and “Truth Trajectory” denote this evaluation role.
The frozen v3 evaluator is primary, with v2 reported in parallel; evaluation
windows and evaluation points are unchanged. All figures and segment summaries
consume retained, sealed evaluator outputs. The displayed reference trajectory
comes from the matched trajectory exported in the original evaluator child.

The study contains 541 registered core cases evaluated under eleven unique
configurations, 22 additional clean sequence/configuration combinations, and
495 A1/A2 combinations: 6,468 unique native terminal records in total. The BY2
clean sequence rows alias the core C00 outputs and are not additional runs.
The fault cases contain controlled faults injected into measured sequences;
they are not independently collected real sequences. Natural-sequence results and controlled-fault summaries are
reported separately. F03/A02 and F04/A01 are configuration aliases rather than
independent experiments.

All registered results are retained without a performance-based admission
threshold. Finite-only summaries, paired comparisons and failure counts have
explicit denominators. An unavailable or failed result is not assigned zero
error. Protocol v3 has 283 algorithm-failure terminals: 193 classified as
divergence and 90 as no valid heading input. The frozen protocol-v2.1 core
comparison has 177 failures, classified as all yaw measurements rejected.
The failure classification rules differ between the two chains: v2.1 has only
the all-yaw-rejected category, whereas v3 separates divergence from no valid
heading input. The totals 283 and 177 are therefore not directly comparable;
a comparison under a unified rule will be reported separately. The family ×
configuration inventory retains the original labels, with F02 shown separately.

两条链的失败分类规则不同——v2.1 仅有“航向全被拒”一类，v3 为发散与无有效航向两类——283 与 177 不可直接比较，统一规则下的对照另行给出。

Under the original, different classification rules, there are 278
completed-to-failed and 172 failed-to-completed label transitions,
with five shared failures and 5,496 shared completed core results. F02 has
43/541 failures in v3 (34 divergence and nine no-valid-heading outcomes),
compared with 0/541 in v2.1. Failure inventories also reflect the registered
classification/admission rules and must not be interpreted solely as changes
in trajectory accuracy. In particular, all twenty current F01 failures have
NAV hashes identical to the corresponding completed v2.1 records. Their
retained metadata show exit code zero, finite numerical rows, zero heading
attempts, and a first bound violation of speed greater than 50 m/s. These
twenty differences are classifications of identical outputs, not newly worsened
F01 trajectories. Both protocols' original terminal labels remain unchanged.

The 52-row main comparison retains all 37 external-method rows, including
LC01 and EXT05C, with their original CSV field tokens and availability classes.
The fifteen internal comparison rows use protocol-v3 outputs. The original
LC01 configuration/start choices and reported limitations remain attached to
their results. The ablation companion additionally reports every one of the
eleven configurations for each of the three sequences.

BY2O segment statistics use the unchanged closed primary interval
[3369.94, 3411.95] s and secondary interval [3495.94, 3508.94] s, their union,
the full [3186, 3563] s window, and the complementary outside region. Segment
statistics are derived from retained full-rate error series without re-evaluation
or metric-driven epoch deletion. Existing T5bc-R R5σ, R5W and B3 rows are
reported as separate sensitivity evidence with their original source identities;
these variants were not rerun or substituted for protocol v3. B3 outcomes with
no heading epochs remain not applicable, separate from algorithm failures.

## Replacement table sources

The following paths resolve under `<V3_ROOT> =
<CLEAN_ROOT>/stages/CLEAN8_PROTOCOL_V3`:

| Manuscript component | Authoritative replacement |
| --- | --- |
| Main three-sequence comparison, 52 rows | `07_AGGREGATE/MAIN_TABLE_V3.csv` |
| Five-profile comparison ladder | `07_AGGREGATE/ABLATION_TABLE_V3.csv` |
| Complete three-sequence ablation, 33 rows | `07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv` |
| Core 541-case summaries and distributions | `07_AGGREGATE/CORE_541_SUMMARY_V3.csv`, `CORE_541_DISTRIBUTION_V3.csv` |
| Failure family × configuration × classification | `07C_FAILURE_FAMILY_CONFIG/FAILURE_FAMILY_CONFIG.csv` |
| F01 classification comparability, 20 identical NAV hashes | `07D_CLASSIFICATION_PROVENANCE/F01_IDENTICAL_NAV_CLASSIFICATION.csv` |
| Correctly classified v2.1 paired comparisons | `07C_FAILURE_FAMILY_CONFIG/CORE_541_V21_COMPARISON_V3.csv`, `SUBSET61_V21_COMPARISON_V3.csv` |
| 61-case table and summary | `07_AGGREGATE/SUBSET61_TABLE_V3.csv`, `SUBSET61_SUMMARY_V3.csv` |
| BY2O segments, including outside | `07_AGGREGATE/BY2O_SEGMENT_TABLE.csv` |
| A1/A2 tables and summaries | `07_AGGREGATE/ADDENDUM_TABLE_V3.csv`, `ADDENDUM_SUMMARY_V3.csv` |
| Existing T5bc-R sensitivity | `07_AGGREGATE/T5BCR_REFERENCE_THREE_SEQUENCES_V3.csv`, `T5BCR_REFERENCE_SUBSET61_V3.csv`, `T5BCR_REFERENCE_SUBSET61_TAIL_SUMMARY.csv` |
| Ten replacement figure groups and captions | `08_FIGURES/FIGURE_INDEX.md`, `08_FIGURES/CAPTIONS.md` |

The matching `_V2` companions retain the parallel evaluator results. Where the
original frozen exporter placed `NONE` in a v2.1 failure-class field, the
`07C_FAILURE_FAMILY_CONFIG` comparison companion supplies the authoritative
`solver_terminal_status` class. Numerical fields, row identities and failure
memberships are unchanged; the original aggregate files remain preserved.

## Replacement main table

The following 52 rows show the primary v3 evaluator. Display rounding is six decimal places; the pinned CSV retains full precision and every original external-method token. Configuration/start identities and geometric-audit limitations remain visible.

Source SHA256: `cd734338cf89518679d78179f410a79ecad3060535d3b80e43a62545cee9b21c`.

| 序列 | 方法 | 配置 | 起点 | 水平 RMSE (m) | Up RMSE (m) | yaw RMSE (deg) | 评估状态 | 几何审计 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BY2 | F02 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.101922 | 0.048068 | 2.231952 | COMPLETED | NOT_APPLICABLE |
| BY2 | F03 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.099920 | 0.047874 | 1.915591 | COMPLETED | NOT_APPLICABLE |
| BY2 | F04 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.097906 | 0.048996 | 1.886272 | COMPLETED | NOT_APPLICABLE |
| BY2 | A04 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.096920 | 0.050019 | 1.886001 | COMPLETED | NOT_APPLICABLE |
| BY2H | A04 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.070046 | 0.045895 | 1.933907 | COMPLETED | NOT_APPLICABLE |
| BY2H | F02 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.071501 | 0.045410 | 2.283241 | COMPLETED | NOT_APPLICABLE |
| BY2H | F03 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.068667 | 0.044901 | 1.940801 | COMPLETED | NOT_APPLICABLE |
| BY2H | F04 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.068362 | 0.045352 | 1.933770 | COMPLETED | NOT_APPLICABLE |
| BY2O | A04 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.053942 | 0.044177 | 2.429173 | COMPLETED | NOT_APPLICABLE |
| BY2O | F02 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.054725 | 0.046174 | 2.309491 | COMPLETED | NOT_APPLICABLE |
| BY2O | F03 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.054709 | 0.043712 | 2.432184 | COMPLETED | NOT_APPLICABLE |
| BY2O | F04 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.054543 | 0.045859 | 2.433815 | COMPLETED | NOT_APPLICABLE |
| BY2 | F01 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.091771 | 0.047881 | 8.089647 | COMPLETED | NOT_APPLICABLE |
| BY2H | F01 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.062926 | 0.044904 | 7.137488 | COMPLETED | NOT_APPLICABLE |
| BY2O | F01 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.062842 | 0.043746 | 5.739038 | COMPLETED | NOT_APPLICABLE |
| BY2 | LC01 | LIT | FILE_START | 0.097548 | 0.050664 | 2.994827 | COMPLETED | FROZEN_PRIOR_AUDIT |
| BY2 | EXT05C | LIT | FILE_START | 0.087751 | 0.056470 | 12.048642 | COMPLETED | NOT_APPLICABLE_SINGLE_RECEIVER |
| BY2 | LC02_GINAV | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2 | EXT01 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2 | EXT02 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2 | EXT03 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2 | EXT04 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2 | Hartley | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2 | EXT05B | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2H | LC02_GINAV | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2H | EXT01 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2H | EXT02 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2H | EXT03 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2H | EXT04 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2H | Hartley | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2H | EXT05B | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2O | LC02_GINAV | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2O | EXT01 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2O | EXT02 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2O | EXT03 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2O | EXT04 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2O | Hartley | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2O | EXT05B | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2 | LC01-S | S | FILE_START | 0.103525 | 0.045250 | 1.539239 | COMPLETED | PASS |
| BY2 | EXT05C-S | S | FILE_START | 0.114228 | 0.046998 | 9.722098 | COMPLETED | NOT_APPLICABLE_SINGLE_RECEIVER |
| BY2H | LC01 | LIT | FILE_START | 0.097453 | 0.055628 | 2.173936 | AVAILABLE_GEOMETRIC_AUDIT_FAIL | FAIL |
| BY2H | LC01 | LIT | CONTRACT_START | 0.074606 | 0.044804 | 2.208612 | AVAILABLE_GEOMETRIC_AUDIT_FAIL | FAIL |
| BY2H | EXT05C | LIT | FILE_START | 0.197284 | 0.078735 | 55.609934 | COMPLETED | NOT_APPLICABLE_SINGLE_RECEIVER |
| BY2H | EXT05C | LIT | CONTRACT_START | 0.069190 | 0.050646 | 20.108223 | COMPLETED | NOT_APPLICABLE_SINGLE_RECEIVER |
| BY2H | LC01-S | S | FILE_START | 0.106709 | 0.040726 | 1.794054 | AVAILABLE_GEOMETRIC_AUDIT_FAIL | FAIL |
| BY2H | LC01-S | S | CONTRACT_START | 0.083733 | 0.040364 | 1.943003 | AVAILABLE_GEOMETRIC_AUDIT_FAIL | FAIL |
| BY2H | EXT05C-S | S | FILE_START | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_RUN_ALGORITHM_FAILURE | NOT_APPLICABLE_SINGLE_RECEIVER |
| BY2H | EXT05C-S | S | CONTRACT_START | 0.085419 | 0.043321 | 8.114756 | COMPLETED | NOT_APPLICABLE_SINGLE_RECEIVER |
| BY2O | LC01 | LIT | FILE_START | 0.054304 | 0.044752 | 2.453697 | COMPLETED | PASS |
| BY2O | EXT05C | LIT | FILE_START | 0.051954 | 0.048903 | 5.845502 | COMPLETED | NOT_APPLICABLE_SINGLE_RECEIVER |
| BY2O | LC01-S | S | FILE_START | 0.060462 | 0.039930 | 4.015602 | COMPLETED | PASS |
| BY2O | EXT05C-S | S | FILE_START | 0.075080 | 0.039767 | 8.266805 | COMPLETED | NOT_APPLICABLE_SINGLE_RECEIVER |

## Replacement complete ablation table

All eleven configurations are shown for each sequence. The primary v3 CSV SHA256 is `44aeaa0302afab54c8179bbb977c9fdac11ebf4f013ac9becdc731840342f4b1`. The F03/A02 and F04/A01 aliases do not represent extra runs.

| 序列 | 配置 | 水平 RMSE (m) | Up RMSE (m) | yaw RMSE (deg) | 评估状态 |
| --- | --- | --- | --- | --- | --- |
| BY2 | F01 | 0.091771 | 0.047881 | 8.089647 | COMPLETED |
| BY2 | F02 | 0.101922 | 0.048068 | 2.231952 | COMPLETED |
| BY2 | F03 | 0.099920 | 0.047874 | 1.915591 | COMPLETED |
| BY2 | A04 | 0.096920 | 0.050019 | 1.886001 | COMPLETED |
| BY2 | F04 | 0.097906 | 0.048996 | 1.886272 | COMPLETED |
| BY2 | A03 | 0.098050 | 0.048416 | 1.885676 | COMPLETED |
| BY2 | A05 | 0.098639 | 0.048478 | 1.913840 | COMPLETED |
| BY2 | A06 | 0.098997 | 0.048992 | 1.886870 | COMPLETED |
| BY2 | A07 | 0.099859 | 0.048474 | 1.914423 | COMPLETED |
| BY2 | A08 | 0.099760 | 0.049460 | 1.914867 | COMPLETED |
| BY2 | A09 | 0.099984 | 0.047858 | 1.913875 | COMPLETED |
| BY2H | F01 | 0.062926 | 0.044904 | 7.137488 | COMPLETED |
| BY2H | F02 | 0.071501 | 0.045410 | 2.283241 | COMPLETED |
| BY2H | F03 | 0.068667 | 0.044901 | 1.940801 | COMPLETED |
| BY2H | A04 | 0.070046 | 0.045895 | 1.933907 | COMPLETED |
| BY2H | F04 | 0.068362 | 0.045352 | 1.933770 | COMPLETED |
| BY2H | A03 | 0.068700 | 0.045364 | 1.932567 | COMPLETED |
| BY2H | A05 | 0.067847 | 0.044925 | 1.940927 | COMPLETED |
| BY2H | A06 | 0.068892 | 0.045355 | 1.934036 | COMPLETED |
| BY2H | A07 | 0.068334 | 0.044928 | 1.941106 | COMPLETED |
| BY2H | A08 | 0.068390 | 0.045419 | 1.941317 | COMPLETED |
| BY2H | A09 | 0.068666 | 0.044948 | 1.940210 | COMPLETED |
| BY2O | F01 | 0.062842 | 0.043746 | 5.739038 | COMPLETED |
| BY2O | F02 | 0.054725 | 0.046174 | 2.309491 | COMPLETED |
| BY2O | F03 | 0.054709 | 0.043712 | 2.432184 | COMPLETED |
| BY2O | A04 | 0.053942 | 0.044177 | 2.429173 | COMPLETED |
| BY2O | F04 | 0.054543 | 0.045859 | 2.433815 | COMPLETED |
| BY2O | A03 | 0.054465 | 0.045936 | 2.435462 | COMPLETED |
| BY2O | A05 | 0.054011 | 0.045365 | 2.434144 | COMPLETED |
| BY2O | A06 | 0.055421 | 0.045860 | 2.432539 | COMPLETED |
| BY2O | A07 | 0.054850 | 0.045369 | 2.433866 | COMPLETED |
| BY2O | A08 | 0.054777 | 0.043654 | 2.428660 | COMPLETED |
| BY2O | A09 | 0.054752 | 0.045437 | 2.435553 | COMPLETED |

## Replacement failure comparison

Cells are protocol v3 / protocol v2.1 failures under the original, different classification rules, except the dual_yaw column, which reports v3 only. The totals 283 and 177 are not directly comparable; a comparison under a unified rule will be reported separately. The dual_yaw family is reported under the one-second-cell mapping and original-row standard-deviation exposure described above, without an improvement claim. F02 is shown separately. The other five registered families contain zero failures in both protocols. The Total column preserves the complete original inventories from each chain; the partially displayed v2.1 columns are not intended to sum to that original total. The source CSV remains unchanged.

| Configuration | dual_yaw (v3 only) | multi_source_mixed | position_std_status | position_value | Total |
| --- | --- | --- | --- | --- | --- |
| F01 | 0 | 10/0 | 9/0 | 1/0 | 20/0 |
| F02 | 0 | 26/0 | 9/0 | 8/0 | 43/0 |
| F03 | 0 | 19/4 | 9/0 | 1/9 | 29/22 |
| F04 | 0 | 13/2 | 9/0 | 0/5 | 22/16 |
| A03 | 0 | 14/3 | 9/1 | 0/6 | 23/19 |
| A04 | 0 | 18/3 | 9/1 | 1/6 | 28/19 |
| A05 | 0 | 13/4 | 9/0 | 0/6 | 22/19 |
| A06 | 0 | 13/3 | 9/3 | 0/6 | 22/21 |
| A07 | 0 | 13/4 | 9/0 | 0/10 | 22/23 |
| A08 | 0 | 19/2 | 9/0 | 1/7 | 29/18 |
| A09 | 0 | 14/2 | 9/0 | 0/9 | 23/20 |
| Total | 0 | 172/27 | 99/5 | 12/64 | 283/177 |

The v3 failures comprise 193 divergence and 90 no-valid-heading terminals; the 177 v2.1 failures retain the all-yaw-rejected class. F02 has 34 divergence and nine no-valid-heading outcomes. All twenty F01 differences have identical NAV hashes across protocols and therefore must not be described as newly worsened trajectories.

Source: `<V3_ROOT>/07C_FAILURE_FAMILY_CONFIG/FAILURE_FAMILY_CONFIG.csv`, SHA256 `d374c4370952dc54c328bf868548848059d398801851e021fb664b349773cb50`.
