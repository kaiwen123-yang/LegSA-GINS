# AGENTS.md — LegSA-GINS Active Project Rules

Last updated: 2026-09-05
Canonical-541 numerical evidence completed: 2026-08-09 22:18 UTC+8
Horizontal literature comparison, cross-layer synthesis, and exploratory plotting completed: 2026-09-04

## 0. Authority and reading order

Every agent must read this file before inspecting, changing, executing, plotting, or interpreting the project.

Then read, as applicable:

1. `docs/paper_rebuild/ACTIVE_CONTEXT.md`;
2. `docs/paper_rebuild/DATA_ROLES.md`;
3. `docs/paper_rebuild/METHOD_SCOPE.md`;
4. `docs/paper_rebuild/EXPERIMENT_PROTOCOL.md`;
5. `docs/paper_rebuild/LEGACY_DENYLIST.md`;
6. `docs/paper_rebuild/CLAIM_BOUNDARY.md`;
7. `docs/paper_rebuild/NEXT_ACTIONS.md`.

This file supersedes stale CLEAN0/CLEAN1/CLEAN2 text that still describes Canonical-541 or the horizontal comparison as unauthorized, unexecuted, or future work.

Do not silently reconcile a historical conflict that changes scientific meaning. Stale stage wording, log paths, timestamps, or archival metadata must not block current work when the completed terminal artifacts below are present.

---

## 1. Current program state

Completed program chain:

```text
CLEAN0
→ CLEAN1R2R1
→ CLEAN2R2A1
→ CLEAN3 mathematical/runtime repair
→ Canonical-541 full execution
→ Canonical-541 offline evaluation and aggregate completion
→ real-literature horizontal comparison
→ horizontal result-identity correction
→ horizontal cross-layer synthesis
→ horizontal exploratory full plotting
→ Canonical-541 paper-focused plotting
```

Authoritative completed terminal states:

```text
PASS_CANONICAL541_OFFLINE_EVALUATION_AND_AGGREGATE_READY_FOR_SEPARATE_PLOTTING
PASS_CLEAN4_HORIZONTAL_RESULT_IDENTITY_CORRECTED_AND_FINAL_EVIDENCE_INTEGRATED
PASS_CLEAN4_HORIZONTAL_CROSS_LAYER_DATA_ORGANIZED_AND_COMPLETENESS_AUDITED
PASS_CLEAN4_HORIZONTAL_FULL_PLOTTING_COMPLETE
PASS_PAPER_FOCUSED_PLOTTING_COMPLETE
```

Canonical-541 counts:

```text
cases:                         541 / 541
unique solver runs:           5951 / 5951
unique offline evaluations:   5951 / 5951
logical evaluation rows:      7033 / 7033
evaluation failures:             0
aggregate outputs:              15 / 15
paper-focused figures:         483 / 483
paper-focused PNG / PDF:       483 / 18
```

Horizontal exploratory plotting counts:

```text
families:                       66 / 66
PNG / PDF / SVG:          213 / 198 / 198
minimum PNG long edge:          >= 4096 px
```

The numerical stages are closed. Do not restart them for publication-figure construction, manuscript organization, generalization planning, storage inspection, or ordinary reporting.

The 66-family horizontal atlas and 483-figure Canonical gallery are exploratory evidence libraries. File-generation PASS does not make every image a publication figure.

---

## 2. Repository, branch, and local paths

```text
GitHub:
kaiwen123-yang/LegSA-GINS

Active local worktree:
/home/kaiwen/research/LegSA-GINS-WORKTREES/clean3-math-repair

Active local branch:
stage/clean3-math-repair

Ignored local path configuration:
/home/kaiwen/research/LegSA-GINS-WORKTREES/clean3-math-repair/
configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml
```

The local branch may be ahead of GitHub. Never reset the local worktree to `main` or a stale remote branch because recent commits are not visible remotely.

Machine-local absolute paths belong in the ignored local YAML. Do not hard-code them into shared Python or C++ source.

If the local active branch contains unpushed commits and the remote branch is stale, do not add an unrelated documentation commit directly to that stale remote branch. Use a separate documentation branch or let the human push the complete local history.

---

## 3. Authoritative Canonical-541 roots and solver identity

```text
<CANONICAL541_ATTEMPT> =
/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/
CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX/
.attempt_20260808T200855P0800
```

Formal solver identity:

```text
scientific solver freeze:
64c81965b17ef1bf8ae2ce3e4dd7b1ae35110b00

executable:
/home/kaiwen/research/LegSA-GINS-WORKTREES/clean3-math-repair/
build/canonical541_cpp/legsa_v23_port_core_demo

executable SHA-256:
9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f
```

Authoritative result roots:

```text
<CANONICAL541_ATTEMPT>/08_FULL_ALGORITHM_RUNS/
<CANONICAL541_ATTEMPT>/10_INTERNAL_ABLATION_RUNS/
<CANONICAL541_ATTEMPT>/12_OFFLINE_EVALUATION/
<CANONICAL541_ATTEMPT>/13_AGGREGATE/
<CANONICAL541_ATTEMPT>/14_PAPER_FOCUSED_PLOTTING/
<CLEAN6_ROOT> = <CLEAN_ROOT>/stages/CLEAN6_PUBLICATION_FIGURES
<CLEAN6_ROOT>/01_CANONICAL541/00_DERIVED_TABLES   (AGENTS §12b derived tables; identity gate + frozen validation PASS)
<CLEAN6_ROOT>/01_CANONICAL541/01_FIGURES_BY2_DRAFT (MFIG00-MFIG06, SFIG01, STAB01; BY2-only; superseded when BY2H/BY2O land)
```

Default numerical sources:

```text
12_OFFLINE_EVALUATION/UNIQUE_EVALUATION_RESULTS.csv
12_OFFLINE_EVALUATION/LOGICAL_EVALUATION_RESULTS.csv
13_AGGREGATE/PAIRWISE_CASE_LEVEL.csv
13_AGGREGATE/PAIRWISE_SUMMARY.csv
13_AGGREGATE/FAMILY_SUMMARY.csv
13_AGGREGATE/DEGRADATION_TYPE_SUMMARY.csv
13_AGGREGATE/SEED_SUMMARY.csv
13_AGGREGATE/CASE_SUMMARY.csv
13_AGGREGATE/MODULE_ACTION_SUMMARY.csv
13_AGGREGATE/UNCERTAINTY_CALIBRATION_SUMMARY.csv
13_AGGREGATE/RECOVERY_SUMMARY.csv
13_AGGREGATE/RUNTIME_SUMMARY.csv
13_AGGREGATE/METRIC_COVERAGE_REPORT.csv
```

CLEAN5 evaluated sequence roots:

```text
<CLEAN5_BY2H_ROOT> = <CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE
<CLEAN5_BY2O_ROOT> = <CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE
<CLEAN5_DECISION_ROOT> = <CLEAN_ROOT>/stages/CLEAN5_DECISION
```

Default CLEAN5 numerical sources (under each sequence root):

```text
08_AGGREGATE/UNIQUE_EVALUATION_RESULTS.csv
08_AGGREGATE/LOGICAL_EVALUATION_RESULTS.csv
08_AGGREGATE/UNIQUE_METHOD_SUMMARY.csv
08_AGGREGATE/LOGICAL_METHOD_SUMMARY.csv
08_AGGREGATE/PAIRWISE_CASE_LEVEL.csv
08_AGGREGATE/PAIRWISE_SUMMARY.csv
08_AGGREGATE/MODULE_ACTION_SUMMARY.csv
08_AGGREGATE/RUNTIME_SUMMARY.csv
08_AGGREGATE/METRIC_COVERAGE_REPORT.csv
08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv
08_AGGREGATE/FINAL_EVALUATION_SUMMARY.json
08_AGGREGATE/FIELD_DEFINITIONS.json
<CLEAN5_DECISION_ROOT>/A04_F04_DECISION_INPUTS.json
```

P-09ab storage inventory (2026-09-11): C1/C2/C3 PASS, C4 FAIL (`renameat2(RENAME_NOREPLACE)` returned EINVAL), C5/D NOT_EXECUTED. Planned 57,233 files / 439,508,000,426 logical bytes; moved/purged/released by purge 0/0/0. The empty quarantine tree is retained. No root was bulk purged. Planned ledger records at `docs/paper_rebuild/purge/DELETION_LEDGER_20260911T040000Z.json.gz`; terminal and inventory record: `docs/paper_rebuild/purge/STORAGE_PURGE_20260911T040000Z.md`. Main-chain roots and Outcome remain unchanged.

P-09ab DrvFs continuation (2026-09-11, audit `20260911T062436Z`): `STOPPED_PREFLIGHT_IO_PROBE_FAIL_NO_CANDIDATE_MOVE_OR_PURGE`. The audit-only zero-byte ordinary rename completed, then the implementation-added full-metadata equality assertion failed; source-absent/destination-present/size-zero postconditions hold, and the differing metadata field is UNAVAILABLE. Dispatch stopped before C1/C2/C3, candidate quarantine, C5 or D; candidate moved/purged files and bytes are 0. No root was bulk purged and no retry was made. Planned ledger records at `docs/paper_rebuild/purge/DELETION_LEDGER_20260911T062436Z.json.gz`; terminal, C5 NOT_EXECUTED rows and UNKNOWN top 20 at `docs/paper_rebuild/purge/STORAGE_PURGE_20260911T062436Z.md`. The prior failed audit and empty quarantine are retained.

Do not reconstruct current metrics from screenshots, legacy tables, or old summaries.

---

## 4. Clean source and evidence boundary

Active tracked material may come from:

```text
docs/paper_rebuild/
configs/paper_rebuild/
scripts/paper_rebuild/
tests/paper_rebuild/
src/legsa_gins/paper_rebuild/
cpp/legsa_v23_port_core/
current horizontal-literature code under the clean namespace
```

Active external material may include immutable raw data under `<RAW_ROOT>`, the ignored local path configuration, the authoritative Canonical attempt, and current horizontal/generalization stage roots.

Legacy runtime, providers, row-level results, figures, aggregates, and performance numbers are not active evidence. Historical files may be read only for formula/source recovery, provenance, implementation lessons, or claim-boundary history.

Synthetic and semi-synthetic results must never be inserted into real-data result tables. Every method/run registry must state its data mode.

---

## 5. Canonical-541 scientific contract

```text
60 degradation types × 9 fixed seeds = 540 degraded cases
+ 1 clean case = 541 cases
```

The exact D01–D60 parameters are authoritative only in the tracked degradation specification and attempt case manifest. Do not redesign them from memory.

Logical aliases:

```text
F03 = A02 = AB0000
F04 = A01 = AB1111
```

Unique effective configurations:

```text
single_antenna_EKF
basic_dual_yaw_EKF
AB0000
AB1111
AB0111
AB1011
AB1101
AB1110
AB1100
AB1000
AB0100
```

Therefore:

```text
541 × 11 = 5951 unique solver/evaluation identities
7033 logical rows after alias expansion
```

Never double-count logical aliases as independent runs.

---

## 6. Fixed data, frame, and evaluation contracts

Core BY2 physical contract:

```text
GNSS1 = right
GNSS2 = left
baseline = GNSS2 - GNSS1
baseline direction = body +Y_left
nominal separation = 0.350 m
body/IMU preprocessing = FLU → FRD
imu_install = [-1, 0, 0] deg
lever arm = [+0.03, +0.03, -0.30] m in FRD
base_time = 1772784000.0
evaluation window = 66.0 .. 340.0 s
```

Trace is evaluation-only. Never use it for solver input, provider selection, frame/sign/time search, tuning, feedback, or correction.

Use wrap-safe yaw residuals. Never choose antenna order, ±90 deg transform, yaw sign, frame, time offset, or constant bias from RMSE.

The reference is Fixposition-derived and not independent ground truth. This limitation belongs in manuscript prose and claim boundaries. For publication graphics, the human requires visible labels `Truth` or `Truth Trajectory`; do not place “same-source reference” wording inside the figure itself.

---

## 7. Internal method identities and current interpretation

```text
F01 = single-antenna EKF
F02 = basic dual-yaw EKF
F03 = strong dual-yaw EKF = AB0000
A04 = AB1011 = no Source-Aware; current core candidate
F04 = AB1111 = Full; current quality-mismatch/tail-protection extension
```

Current manuscript role:

```text
A04:
core and leading main-method candidate

F04:
quality-mismatch and tail-protection extension

final manuscript identity:
A04 (decided by pre-registered rule, 2026-09-08)
```

Do not claim Full universally dominates Strong or A04. Do not claim Source-Aware is nominal-silent/fault-active; clean touch rate is about 84.8%.

Current formal full-C00 anchors:

```text
F02: H / 3D / yaw = 0.355526 m / 0.893102 m / 2.338427 deg
F03: H / 3D / yaw = 0.352517 m / 0.890581 m / 1.962413 deg
A04: H / 3D / yaw = 0.352386 m / 0.890358 m / 1.934076 deg
F04: H / 3D / yaw = 0.354803 m / 0.926378 m / 1.954959 deg
```

Formal BY2H full-window anchors:

```text
F01: H / 3D / Up / yaw RMSE / yaw P95 = 0.350287 m / 0.938231 m / 0.870389 m / 3.901904 deg / 7.587503 deg
F02: H / 3D / Up / yaw RMSE / yaw P95 = 0.353305 m / 0.940934 m / 0.872085 m / 2.122373 deg / 4.498102 deg
F03: H / 3D / Up / yaw RMSE / yaw P95 = 0.349399 m / 0.937819 m / 0.870301 m / 2.007379 deg / 3.968948 deg
A04: H / 3D / Up / yaw RMSE / yaw P95 = 0.349360 m / 0.937628 m / 0.870112 m / 2.059813 deg / 4.106967 deg
F04: H / 3D / Up / yaw RMSE / yaw P95 = 0.351939 m / 0.982015 m / 0.916783 m / 2.068136 deg / 4.117244 deg
```

Formal BY2O full-window anchors:

```text
F01: H / 3D / Up / yaw RMSE / yaw P95 = 0.348856 m / 1.226955 m / 1.176316 m / 6.904339 deg / 11.147493 deg
F02: H / 3D / Up / yaw RMSE / yaw P95 = 0.351268 m / 1.230122 m / 1.178903 m / 2.799343 deg / 4.331735 deg
F03: H / 3D / Up / yaw RMSE / yaw P95 = 0.348291 m / 1.226749 m / 1.176268 m / 3.311780 deg / 5.416607 deg
A04: H / 3D / Up / yaw RMSE / yaw P95 = 0.348045 m / 1.226528 m / 1.176111 m / 3.314214 deg / 5.474313 deg
F04: H / 3D / Up / yaw RMSE / yaw P95 = 0.350912 m / 1.602733 m / 1.563846 m / 3.404182 deg / 5.610167 deg
```

Calibrated-sensor protocol anchors (V2s input + calibrated vrw/abstd, evaluator v3)

`NOT_THE_PREREGISTERED_COMPARISON_PROTOCOL`. One BY2-calibrated sensor model (including s) is transferred unchanged to BY2H/BY2O. The main-chain anchors and the pre-registered A04 Outcome above remain unchanged.

Source: `<CLEAN_ROOT>/stages/CLEAN5_CALIBRATED_SENSOR_MODEL/08_AGGREGATE/v3/UNIQUE_EVALUATION_RESULTS.csv`; values below are original CSV tokens, without metric recomputation.

| Sequence | Profile | H RMSE (m) | 3D RMSE (m) | Up RMSE (m) | yaw RMSE (deg) | CSV row |
|---|---|---|---|---|---|---|
| BY2 | F01 | 0.09177145533263088 | 0.10351109355664635 | 0.04788054380877193 | 8.089647422454789 | 2 |
| BY2 | F02 | 0.10167042168391813 | 0.11245701732466279 | 0.048059401787514736 | 2.387502021110019 | 3 |
| BY2 | F03 | 0.09942874018593109 | 0.1103501723708457 | 0.04786529188581187 | 2.149759240837629 | 4 |
| BY2 | A04 | 0.09788305204693296 | 0.10995310369005244 | 0.05008585761522742 | 2.116232431517562 | 5 |
| BY2 | F04 | 0.09833550004013293 | 0.10989606602860731 | 0.049063986389418376 | 2.102586167315052 | 6 |
| BY2H | F01 | 0.06292589316025435 | 0.0773049305383686 | 0.04490416746278954 | 7.137487572272005 | 7 |
| BY2H | F02 | 0.07052641924128063 | 0.08387963582274612 | 0.045407240554339263 | 1.7112292640294133 | 8 |
| BY2H | F03 | 0.06888244431434563 | 0.08222261583580157 | 0.044897298584245335 | 1.827474957827435 | 9 |
| BY2H | A04 | 0.0688386599992056 | 0.08272455961957677 | 0.04587582864392402 | 1.8292666502216393 | 10 |
| BY2H | F04 | 0.06906331937087641 | 0.08261176077190832 | 0.04533167695234024 | 1.818619110302363 | 11 |
| BY2O | F01 | 0.06284210260933396 | 0.07656942024179673 | 0.043746385631304584 | 5.739037942642961 | 12 |
| BY2O | F02 | 0.05623289091150956 | 0.07277209282853116 | 0.04619133549031268 | 2.459463554105357 | 13 |
| BY2O | F03 | 0.05572585547571861 | 0.07083587931327699 | 0.04373043367706825 | 2.590433964384844 | 14 |
| BY2O | A04 | 0.056215385962533816 | 0.07156744632023422 | 0.04429141851287854 | 2.5886519847978273 | 15 |
| BY2O | F04 | 0.05646322233551191 | 0.07280509497024816 | 0.04596179257946105 | 2.6519625108013902 | 16 |

Reference-point v3 is reported separately; position consistency uses the original, untransported STD as a diagnostic only. CAD confirmation of antenna–IMU height difference remains open.

The 77-epoch common-support values A04 2.231055 deg and F04 2.226267 deg are diagnostic-only. They must never replace the formal C00 values.

The historical 1.813898 deg final_v23 result is a legacy identity, not the current Canonical C00 result.

---

<!-- CANONICAL541_DETAILED_RESULTS_BEGIN -->

## 7A. Canonical-541 detailed numerical results and interpretation

This subsection completes the Canonical-541 record with the full 541-case
aggregate values, paired comparisons, family behavior, module actions, and
claim limits. The terminal numerical state is:

```text
541 / 541 canonical cases
5951 / 5951 unique solver runs
5951 / 5951 unique offline evaluations
7033 / 7033 logical evaluation rows
0 solver failures
0 evaluation failures
15 / 15 aggregate outputs
```

Terminal:

```text
PASS_CANONICAL541_OFFLINE_EVALUATION_AND_AGGREGATE_READY_FOR_SEPARATE_PLOTTING
```

### 7A.1 Overall 541-case means

Values below are equal-weight means of the case-level RMSE values over all
541 cases, not one epoch-pooled global RMSE.

| Method | East m | North m | Horizontal m | Up m | 3D m | Roll deg | Pitch deg | Yaw deg |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| F01 Single | 0.6349 | 0.6742 | 0.945565 | 1.142035 | 1.562490 | 1.409577 | 1.788949 | 13.407726 |
| F02 Basic | 0.7074 | 0.7471 | 1.066095 | 1.147250 | 1.661130 | 1.421226 | 1.794461 | 5.702272 |
| F03 Strong | 0.6320 | 0.6633 | 0.939803 | 1.140743 | 1.557760 | 1.370176 | 1.781466 | 6.436740 |
| A04 Core candidate | 0.6289 | 0.6617 | 0.935235 | 1.139936 | 1.554172 | 1.358080 | 1.772151 | 6.498098 |
| F04 Full extension | 0.6332 | 0.6628 | 0.942838 | 1.172371 | 1.586502 | 1.273262 | 1.674899 | 5.329333 |

Current interpretation:

```text
Strong:
successful dual-yaw + receiver-velocity backbone.

A04 / AB1011:
best current mean position result;
current core and leading manuscript candidate;
Strong + RD + RP + HV, Source-Aware disabled.

F04 / AB1111:
best average roll/pitch/yaw among the listed main methods;
selected high-tail and quality-mismatch protection;
worse average position, Up, and 3D than Strong/A04;
not a universally superior default estimator.
```

### 7A.2 A04 versus Strong

Delta convention:

```text
delta = candidate - reference
delta < 0 is better for lower-is-better metrics
```

A04 relative to Strong:

| Metric | Mean delta | A04 win rate |
|---|---:|---:|
| Horizontal RMSE | -0.004568 m | 87.6% |
| Up RMSE | -0.000807 m | 97.6% |
| 3D RMSE | -0.003589 m | 94.8% |
| Roll RMSE | -0.012096 deg | 98.2% |
| Pitch RMSE | -0.009315 deg | 96.9% |
| Yaw RMSE | +0.061358 deg mean | 90.0% case wins; median delta about -0.02833 deg |

The yaw mean is pulled upward by a small number of extreme cases. The
case-level median and win rate show that A04 usually improves yaw slightly,
but it does not improve the yaw mean over all 541 cases.

Across the 60 degradation types, A04 versus Strong has majority-seed
improvement in approximately:

```text
Horizontal: 54 / 60 degradation types
Up:         60 / 60 degradation types
3D:         59 / 60 degradation types
Roll:       59 / 60 degradation types
Pitch:      60 / 60 degradation types
Yaw:        56 / 60 degradation types
```

The main A04 result is therefore a small absolute but highly consistent
gain, not a large universal accuracy jump.

### 7A.3 Full versus Strong

Full relative to Strong:

| Metric | Mean delta | Full win rate |
|---|---:|---:|
| Horizontal RMSE | +0.003035 m | 17.6% |
| Up RMSE | +0.031628 m | 4.4% |
| 3D RMSE | +0.028742 m | 9.1% |
| Roll RMSE | -0.096914 deg | 95.9% |
| Pitch RMSE | -0.106567 deg | 96.5% |
| Yaw RMSE | -1.107407 deg | 70.4% |

Full generally improves attitude but usually worsens position, especially
Up and 3D. Its yaw mean gain is substantially influenced by selected severe
cases; it must not be described as uniformly better.

### 7A.4 Full versus A04 / no-SA

Full relative to A04 isolates the net effect of always-on Source-Aware
within the current full context:

| Metric | Mean delta | Full win rate |
|---|---:|---:|
| Horizontal RMSE | +0.007603 m | 15.9% |
| Up RMSE | +0.032435 m | 4.4% |
| 3D RMSE | +0.032330 m | 7.9% |
| Roll RMSE | -0.084818 deg | 13.5% case wins; mean is tail-driven |
| Pitch RMSE | -0.097252 deg | 80.6% |
| Yaw RMSE | -1.168765 deg | 13.1% case wins; median delta about +0.02088 deg |

For roll and yaw, a small set of severe cases produces a favorable mean
while the median and case-win rate show that Full is worse in most ordinary
cases. This is a tail-protection result, not a general nominal-accuracy
result.

### 7A.5 Tail behavior

Selected across-case P95 values:

| Metric | Strong P95 | Full P95 | Interpretation |
|---|---:|---:|---|
| Horizontal RMSE | 4.3815 m | 4.1367 m | Full lower |
| 3D RMSE | 5.4039 m | 5.2202 m | Full lower |
| Roll RMSE | 2.7339 deg | 2.2693 deg | Full lower |
| Pitch RMSE | 3.3750 deg | 2.5905 deg | Full lower |
| Yaw RMSE | 31.9055 deg | 15.4346 deg | Full substantially lower |

Full reduces several high-percentile tails even though its mean position is
worse. It does not guarantee the best absolute maximum in every metric; for
example, its worst observed yaw case is not better than Strong's worst yaw
case.

### 7A.6 Module ablation conclusions

Raw Doppler:

```text
Full versus no-RD:
Horizontal mean delta ≈ -0.00482 m
Up mean delta         ≈ -0.00052 m
3D mean delta         ≈ -0.00362 m

RD-only versus Strong:
Horizontal mean delta ≈ -0.00379 m; about 91.1% wins
Up mean delta         ≈ -0.00046 m; about 97.0% wins
3D mean delta         ≈ -0.00281 m; about 94.1% wins
Yaw mean delta        ≈ -0.02925 deg
```

Raw Doppler is the clearest additional measurement module: small in
absolute magnitude, but highly consistent over cases, families, and seeds.

Go2 roll/pitch weak prior:

```text
Full versus no-RP:
Horizontal mean delta ≈ -0.00072 m
Up mean delta         ≈ -0.00061 m
3D mean delta         ≈ -0.00092 m
Roll mean delta       ≈ -0.01099 deg
Pitch mean delta      ≈ -0.00261 deg
Yaw mean delta        ≈ -0.07064 deg
```

RP produces a small but highly consistent attitude benefit. It is a weak
auxiliary observation and must not be called truth.

Go2 horizontal-velocity weak prior:

```text
Full versus no-HV:
Horizontal mean delta ≈ -0.00043 m
3D mean delta         ≈ -0.00032 m
Horizontal/3D case win rate ≈ 30.7%
```

HV is near-neutral overall. Its favorable mean is driven by selected
windows/cases rather than broad case-level dominance. It is not a primary
standalone innovation claim.

Source-Aware:

```text
SA-only versus Strong:
Horizontal mean delta ≈ +0.00897 m
Up mean delta         ≈ +0.03269 m
3D mean delta         ≈ +0.03352 m

Full versus no-SA:
position is worse in the large majority of cases;
selected severe quality-mismatch and mixed-source cases improve.
```

Always-on Source-Aware is selectively useful but not generally beneficial.
It does not implement nominal-silent/fault-active behavior in the completed
algorithm.

### 7A.7 Family-level Full versus Strong behavior

Approximate family-level mean deltas:

| Family | Horizontal delta m | 3D delta m | Yaw delta deg | Interpretation |
|---|---:|---:|---:|---|
| Clean | +0.0023 | +0.0358 | -0.0075 | small attitude gain, position cost |
| GNSS outage | +0.1580 | +0.1430 | -0.0084 | position clearly worse |
| Sampling/dropout | +0.0525 | +0.0945 | -0.0179 | position worse |
| Position-value degradation | -0.0269 | +0.0239 | -1.9449 | horizontal/yaw gain; Up can erase 3D gain |
| Std/status mismatch | -0.1053 | -0.1054 | -2.0906 | clear Full benefit |
| Dual-yaw degradation | +0.0023 | +0.0358 | +0.0492 | no general Full advantage |
| Velocity/Raw-Doppler degradation | +0.0024 | +0.0362 | -0.0044 | near clean trade-off |
| Go2 prior/metadata | +0.0023 | +0.0358 | -0.0030 | near clean trade-off |
| Multi-source mixed | -0.0609 | -0.0554 | -8.2169 | clear selected Full benefit |

Representative favorable Full cases:

```text
D27:
bad position values with optimistic reported quality;
Full materially improves horizontal, Up, 3D, and yaw.

D60:
mixed position, heading, and velocity degradation with optimistic quality;
Full materially improves position and yaw.
```

Representative unfavorable Full cases:

```text
D04:
20 s GNSS-position outage;
Full substantially worsens horizontal and 3D error.

D12:
60% random GNSS loss;
Full worsens horizontal and 3D error.

D58:
outage + yaw spikes + recovery-oriented sequence;
Full gives only a very small yaw benefit while worsening position.
```

These examples must be shown together when discussing applicability. Do
not select only favorable D27/D60 examples.

### 7A.8 Clean mechanism-action counts

For the Full clean case:

```text
GNSS position updates:             274
receiver-velocity updates:         274
dual-yaw attempts:                 274
dual-yaw accepted:                 268

Scheme-C normal/downweight/reject: 121 / 147 / 6

Raw-Doppler provider rows:         1248
Raw-Doppler actual updates:        223
Raw-Doppler rejects:               0
satellite count min/median/max:    7 / 10 / 12
Raw-Doppler residual P95:          about 2.510 m/s

Go2 RP updates:                    274
Go2 HV updates:                    274

Source-Aware evaluations:          1587
Source-Aware changed weights:      1346
Source-Aware clean touch rate:     about 84.8%
```

The module switches were active in the real solver. The Source-Aware clean
touch rate confirms that it was almost continuously active rather than
nominal-silent.

### 7A.9 Metric coverage and uncertainty boundary

```text
defined evaluation fields:        542
supported fields:                 412
full 5951-row coverage fields:    334
unsupported fields:               130
```

Most unsupported fields are velocity-error or velocity-calibration metrics
for which the selected same-source reference does not provide a suitable
reference velocity. Unsupported fields remain `NA`; never convert them to
zero.

Uncertainty results use diagonal `KF_GINS_STD.txt` fields:

```text
diagonal normalized-error consistency diagnostic only
not full-covariance NEES
```

The predicted STD values are generally overconfident relative to the
same-source reference. No integrity or calibrated-confidence claim is
allowed from these diagonal results.

Recovery-time fields remain `NA` where no frozen recovery rule or
identifiable event window exists. Do not invent a threshold after seeing
the results.

### 7A.10 Canonical-541 claim boundary

Allowed:

```text
Canonical-541 completed 541 cases, 5951 unique runs/evaluations,
and 7033 logical rows with zero evaluation failures;

Strong is a successful dual-yaw + receiver-velocity backbone;

Raw Doppler gives a small but highly consistent benefit;

RP gives a small but consistent attitude benefit;

HV is near-neutral overall;

A04 is the current core and leading manuscript candidate;

always-on Source-Aware has a robustness-accuracy trade-off;

Full provides selected quality-mismatch, mixed-fault, and attitude-tail
protection.
```

Not allowed:

```text
Full universally outperforms Strong or A04;

Source-Aware is nominal-silent/fault-active;

all four added modules contribute equally;

D01-D60 are 60 independently collected real environments;

the Fixposition-derived reference is independent ground truth;

Canonical-541 alone proves cross-sequence or cross-platform generalization;

unsupported velocity metrics are zero;

diagonal consistency is full NEES.
```

No ordinary plotting, manuscript organization, horizontal comparison, or
documentation task may rerun the Canonical numerical chain.

<!-- CANONICAL541_DETAILED_RESULTS_END -->

---

## 8. Horizontal comparison registry

Horizontal root:

```text
/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/
CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/
```

Completed evidence roots:

```text
12_FINAL_EVIDENCE_INTEGRATION/
13_HORIZONTAL_CROSS_LAYER_SYNTHESIS/
14_HORIZONTAL_FULL_PLOTTING/
```

Active cross-layer structure:

```text
Layer A — raw dual-antenna carrier/ambiguity methods:
EXT01 C-LAMBDA
EXT02 C-WLS
EXT03 Yang 2024 DD-KF + M-LAMBDA

Supplementary raw diagnostic:
EXT04 constrained FAR/PAR module only

Layer B — solution-level LC:
LC01 Pavlasek two-receiver IEKF
LC02 GINav official SPP/INS LC

Layer C — proprioceptive structural evidence:
Hartley contact-aided InEKF

Internal:
F02 Basic
F03 Strong
A04 Core
F04 Full
```

Do not add another horizontal method by default. The present technical-route coverage is sufficient for the active claim set.

---

## 9. Raw dual-antenna evidence boundaries

Use method-native state names. Do not flatten them into a shared “fix success” rate.

```text
EXT01 C-LAMBDA:
1077 / 1509 globally certified integer solutions;
no ambiguity acceptance test;
do not call them successful or correct fixes;
unresolved fractional-DD phase-bias applicability boundary.

EXT02 C-WLS:
1057 / 1509 accepted wrapped solutions;
ambiguity correctness unknown;
poor physical heading applicability on BY2.

EXT03 Yang 2024 primary mode:
609 / 1509 valid;
105 paper-ratio-fixed;
900 invalid;
101 / 105 ratio-fixed rows are proxy-inconsistent.

EXT04:
module-only diagnostic;
exact PAR policy not closed;
all declared policy/mode accepted counts are zero;
not a fourth complete raw method.
```

Hard-constrained 0.350 m baseline lengths in EXT01/EXT02 are not independent accuracy evidence.

---

## 10. Solution-level LC and Hartley boundaries

Formal C00 anchors:

```text
LC01 Pavlasek:
coverage             100%
horizontal RMSE      0.169139 m
3D RMSE              0.379009 m
roll / pitch / yaw   1.209563 / 1.567624 / 2.994827 deg

GINav official SPP/INS LC:
row coverage         28.0%
time-span coverage   62.043%
horizontal RMSE      130.818726 m
3D RMSE              219.883711 m
roll / pitch / yaw   14.936207 / 14.107015 / 69.753332 deg
alignment delay      113.002 s
configured/eligible  295 / 116
SPP valid/invalid    48 / 68
native rows          80
LC updates           11
INS-only rows        68
max gap / segments   11 s / 38
```

GINav label:

```text
EXACT_OFFICIAL_ROUTE_WITH_POOR_BY2_ACCURACY_AND_AVAILABILITY
```

LC01 and GINav have different information structures and legal supports. Their numerical gap is not a pure filter-formula comparison.

Hartley is complete for its intended structural role:

```text
63,277 real native state rows;
3 global translations + 1 gravity-axis yaw gauge;
full-precision real-data gauge equivalence;
4-contact bias-augmented rank/nullity = 23 / 4;
2-contact bias-augmented rank/nullity = 17 / 4;
rank/nullity stable across 0.1× / 1× / 10× thresholds.
```

Hartley does not provide legal absolute yaw RMSE or absolute position RMSE and must not appear in a flat accuracy ranking.

---

## 11. Corrected Classic-18 and generalization

Corrected Classic-18 is not required by default.

It becomes conditionally necessary only if the manuscript claims systematic degradation superiority over external solution-level methods. In that case, the only allowed set is:

```text
LC01
F02
F03
A04
F04
```

Do not include GINav, EXT01–EXT04, or Hartley. Do not start without explicit human authorization.

Priority remaining evidence gaps:

```text
independent or more independent reference;
additional real sequences/platforms;
[x] real single-antenna obstruction or one-side quality degradation;
cross-sequence/cross-platform generalization;
[x] final A04/F04 role selection.
[x] position gap decomposition (stage 2 frozen parity ladder and calibrated-chain record);
remaining: BY2O gating sensitivity to IMU integration convention.
```

BY2O records GNSS2 RTK float for 57 epochs, not a stream outage.

P-07 corrected-chain degradation subset is complete: 61 mechanically selected cases, 480 excluded, NOT_TRANSFERABLE=[]; CAL 669 COMPLETED / 2 FAILED_TECHNICAL and V2S 663 / 8, with no retries. Across v3/v2, main-metric pair/version items are 23 maintained / 13 flipped / 24 incomplete; the decision is `HUMAN_DECISION_REQUIRED`, with 66 missing-evidence entries across pair/metric/version/chain. No full-matrix rerun was executed or automatically authorized. The 295 subset capture consistency failures retain their original wrapper terminal states and metrics; GINav horizontal v3 remains `UNAVAILABLE_EVALUATION_FAILED`. Sources: `docs/paper_rebuild/CLEAN5_DEGRADATION_SUBSET_RESULTS.md` and `<CLEAN_ROOT>/stages/CLEAN5_DEGSUBSET_BY2/08_AGGREGATE/DEGRADATION_SUBSET_DECISION.json`. The original main chain and Outcome are unchanged.

Do not automatically repeat the full 541 × 11 matrix on another dataset.

---

## 12. Current publication-figure task

The active horizontal publication task contains exactly four composite figures:

```text
FIG01 — horizontal comparison information hierarchy
FIG02 — formal C00 solution-level navigation comparison
FIG03 — raw dual-antenna BY2 applicability
FIG04 — Hartley yaw unobservability
```

Output root:

```text
/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/
CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/
15_HORIZONTAL_PUBLICATION_FIGURES/
```

Out of scope:

```text
Canonical-541 overall robustness;
D01–D60 atlases;
541-case heatmaps;
ablation matrices;
selected degradation time series;
P01–P18;
EXT04 publication figures;
77-epoch diagnostic figures;
full 66-family atlas cleanup;
TIM figure ranking.
```

Keep these existing roots unchanged as exploratory evidence libraries:

```text
14_HORIZONTAL_FULL_PLOTTING/
<CANONICAL541_ATTEMPT>/14_PAPER_FOCUSED_PLOTTING/
```

Do not spend time globally cleaning their automatic dashboard templates as part of the four-figure task.

---

## 12b. Canonical-541 publication-figure task (authorized 2026-09-04)

A second publication-figure task is authorized alongside Section 12. It builds the
manuscript figures for the Canonical-541 matrix and the internal ablation from frozen
results only.

Inputs (read-only, frozen):

```text
<CANONICAL541_ATTEMPT>/12_OFFLINE_EVALUATION/UNIQUE_EVALUATION_RESULTS.csv
<CANONICAL541_ATTEMPT>/12_OFFLINE_EVALUATION/LOGICAL_EVALUATION_RESULTS.csv
<CANONICAL541_ATTEMPT>/13_AGGREGATE/*.csv
<CANONICAL541_ATTEMPT>/12_OFFLINE_EVALUATION/RUN_*/error_series.csv.gz (display curves only)
<CANONICAL541_ATTEMPT>/08_FULL_ALGORITHM_RUNS and 10_INTERNAL_ABLATION_RUNS C00 NAV files (body-frame bias diagnostic only)
```

Authorized derived analysis (plotting-side, no solver, evaluator, or provider rerun):

```text
case-level pairwise tables A04_vs_F03, A04_vs_F02, F04_vs_F02 built by joining
LOGICAL_EVALUATION_RESULTS.csv on case_id; bootstrap confidence intervals of paired
deltas; family-stratified Wilcoxon signed-rank tests; N/E/U bias versus random
decomposition (signed mean, standard deviation, bias share of RMSE) and the body-frame
mean of the horizontal error vector using the C00 solver yaw.
```

Derived tables must reproduce the Section 7A.2 A04-versus-Strong values
(horizontal mean delta -0.004568 m, win rate 87.6%) before any figure is rendered;
mismatch is fail-closed.

Manuscript identities: Single (F01), Dual-basic (F02), Backbone (F03 = AB0000, an
ablation row of the proposed method, never labelled a strong baseline), Core (A04),
Full (F04). The proposed-method identity remains provisional until
`docs/paper_rebuild/A04_F04_ROLE_DECISION_RULE.md` is executed on BY2H and BY2O.

Output root:

```text
<CLEAN_ROOT>/stages/CLEAN6_PUBLICATION_FIGURES/01_CANONICAL541/
```

Figure set (main text candidates; final selection after BY2H/BY2O):

```text
MFIG01 matrix overview (541-case means/medians, ECDFs)
MFIG02 Core-versus-Backbone consistency (per-type deltas with seed spread, family win/tie/loss, majority-seed counts)
MFIG03 Full trade-off and tail protection (family deltas, mean/median/win-rate, across-case P95, paired scatter)
MFIG04 module ablation (Dual-basic -> Backbone -> +RD -> +RP/HV -> +SA)
MFIG05 representative cases D27, D60 together with D04, D12, D58 (favorable and unfavorable shown together)
MFIG06 mechanism panels (Scheme-C actions, Source-Aware R-scale and touch rate, Raw-Doppler updates)
supplementary: 60-type x method heatmaps, diagonal consistency diagnostic, remaining atlases
```

The visual contract of Section 13 applies unchanged (panel labels only, no machine
title, no scope badge, no field-coverage panel, no absolute path, no PASS/FAIL,
units on separate axes, readable at about 174 mm double-column width, grayscale-safe).
The execution contract of Section 14 applies unchanged. Exploratory atlases under
`14_PAPER_FOCUSED_PLOTTING/` and `14_HORIZONTAL_FULL_PLOTTING/` stay read-only.

Out of scope: any solver, provider, evaluator, or Canonical rerun; recovery-time
thresholds invented after seeing results; per-case or per-figure metric recomputation
that replaces a frozen aggregate value.

Status (2026-09-07):

Derived tables: src/legsa_gins/paper_rebuild/publication/derived_tables.py (commit 39a1f4e). Plotting layer: src/legsa_gins/paper_rebuild/publication/{style,qa,loaders,tables,canonical541_figures}.py, configs/paper_rebuild/publication/{canonical541_display_names.yaml,CANONICAL541_PUBLICATION_FIGURE_REGISTRY.csv}, scripts/paper_rebuild/render_canonical541_publication_figures.py (commits 88485c7, e9fe61e, ba51524, 1bf64e5).
Figures MFIG00-MFIG06, SFIG01 and Table S1 (STAB01) rendered from frozen tables; IEEE/TIM figure rules applied (Okabe-Ito palette, one line style per method, hatched secondary bars, 7 pt minimum, 174 mm width, PNG >= 4096 px + PDF + SVG); machine QA all-pass.
MFIG00 draws the hash-locked BY2 reference trace (sha256 ee3ee42d…4aa4c, passed only via --trace-path, never committed) with the frozen time origin and yaw formula; the consistency gate against estimate-minus-frozen-error passes at 0.2 cm / 0.0 cm / 0.00 deg.
Confirmed on 56 642 full-rate samples: body-frame horizontal error offset forward -0.20..-0.22 m, right +0.15..+0.17 m (0.261-0.265 m, 54-56% of horizontal MSE, all five configurations); position error is input-bound.
Open: reference uncertainty statement needs the full trace/odometry fields (fix status, covariance) or manufacturer specification.

## 13. Publication visual contract

Publication figures are not engineering dashboards.

Every publication composite must:

```text
use only panel labels (a), (b), (c), (d);
contain no figure-wide machine title;
contain no right-top scope badge;
contain no “ONLY” badge;
contain no field-coverage panel;
contain no absolute source path;
contain no PASS/FAIL or management state;
separate metres, degrees, counts, rates, and time onto legal axes;
keep legends clear and non-overlapping;
remain readable at about 174 mm double-column width.
```

Visible reference labels, when needed:

```text
Truth
Truth Trajectory
```

Do not place `same-source reference`, `Fixposition-derived reference`, `not independent ground truth`, or their Chinese equivalents inside the figure. The human controls that explanation in manuscript prose.

Figure-specific boundaries:

```text
FIG01:
clean information-flow diagram only; no registry bars, claim ceilings, field completeness, or method PASS/FAIL.

FIG02:
LC01, GINav, F02, F03, A04, F04 formal C00 only;
position, attitude, and support separated;
use logarithmic overview plus readable low-error inset or facets;
never use 77-epoch diagnostic values.

FIG03:
EXT01, EXT02, EXT03 only;
use method-native outcome semantics;
show availability, yaw consistency, baseline-direction consistency, and failure composition;
never label certified/accepted outputs as correct fixes.

FIG04:
Hartley gauge ensemble, normalized gauge residuals, rank/nullity, and singular-value spectrum;
no absolute RMSE and no flat comparison with other methods.
```

Use consistent method colors and line styles/markers/hatching so grayscale printing remains interpretable.

---

## 14. Plotting execution contract

```text
default plotting workers: 16
hard maximum workers:     24
progress heartbeat:       every 10 seconds
minimum PNG width:        4096 px
outputs:                  PNG + vector PDF + SVG
```

Use independent plotting processes. Each worker must use one numerical-library thread.

Render only from frozen results. Do not run a solver, evaluator, MATLAB, provider, Canonical runner, or Canonical robustness plotter.

Do not create ZIPs, hash manifests, seals, evidence packages, contact-sheet atlases, large galleries, or reviewer chains for the four-figure task. A short figure index, captions file, and plotting summary are sufficient.

---

## 15. Runtime provenance: proportionate requirements

Formal numerical runs must record enough to identify:

```text
data mode;
case and method identity;
scientific solver commit;
executable identity;
runtime configuration;
input paths/roles;
synthetic/semi-synthetic flags;
trace-used-online flag;
forbidden solver-input flags;
terminal status.
```

Do not require repeated whole-payload SHA-256 calculations for plotting, literature reading, monitoring, routine adapters, or reuse of completed evaluations.

Hashing, seals, sidecars, ZIPs, and publication-parity packages are not default requirements. Use them only when the human explicitly requests archival closure or a concrete integrity problem exists.

---

## 16. Engineering and anti-overengineering rules

Simple bounded tasks should be executed directly by one agent. Do not automatically create planner/worker/reviewer chains.

Keep checks that protect scientific meaning:

```text
formula and frame correctness;
input availability;
method/case identity;
finite outputs;
no trace-driven tuning;
no result substitution.
```

Do not block work for:

```text
directory-size metadata;
timestamps;
absolute log-path differences;
report-only fields;
repeated hashes of unchanged files;
missing optional archival metadata.
```

Forbidden process patterns:

```text
idle “waiting for agents” loops;
long model sessions that only tail an OS job;
front-loaded full-matrix preflight before useful output;
multiple full validation passes over the same payload;
a new stage for every metadata correction.
```

Long computations should use `systemd-run --user`, `tmux`, or `nohup` with visible progress counts.

Generic code must not hard-code old stage IDs, old roles, old method allowlists, one historical attempt path, or a paper baseline length in place of current physical geometry.

---

## 17. Filesystem and Git safety

- Raw data are immutable and must never be overwritten, moved, or deleted by an experiment worker.
- Preserve the Canonical attempt, NAV, STD, evaluation, aggregate, and time-series assets needed for figures and manuscript evidence.
- Runtime outputs and large generated artifacts remain untracked unless the human explicitly authorizes a small tracked report.
- Preserve unrelated user changes. Never reset, stash, clean, or overwrite them automatically.
- Never rewrite Git history or force-push.
- Do not merge, tag, push, delete branches, or create a new worktree without explicit human authorization.
- Tracked files use portable paths/aliases; machine-local absolute paths remain in ignored local configuration.

---

## 18. Current next actions

Current next actions:

```text
1. CAD verification of antenna–IMU height difference and lever-arm z; retain the source-defined v3 transform until independently confirmed;
2. conversation A: frozen error-budget ladder, body-frame bias, sensitivity heatmap, and calibrated three-sequence tables; show evaluator version and protocol identity explicitly;
3. conversation D: reference-uncertainty record using timing, baseline, derived diagnostic velocity difference, consistency ratios, and frozen calibrated vrw/abstd/c;
4. remaining: BY2O gating sensitivity to IMU integration convention; any new execution requires its own bounded authorization;
5. post-hoc BY2O rejection/downweight timeline and Source-Aware Up cost by source, using frozen artifacts;
6. human review of the P-07 decision: 13 primary flips, 24 incomplete primary pair/version items, and 66 missing-evidence entries; retain capture consistency diagnostics and GINav UNAVAILABLE; no automatic full-matrix rerun;
7. registered, not executed: gyro z-axis scale input-side check using integrated gyro angle increments versus A1 angle increments on turn segments, with zero trace reads.
```

Stage 2 and the calibrated-chain execution are complete. Sources: `docs/paper_rebuild/CLEAN5_STAGE2_CLOSEOUT.md`, `docs/paper_rebuild/CLEAN5_CALIBRATED_CHAIN_RESULTS.md`, and `<CLEAN_ROOT>/stages/CLEAN5_CALIBRATED_SENSOR_MODEL/`. The original main protocol and Outcome remain authoritative.

Do not restart Canonical-541, reselect horizontal literature algorithms, rerun GINav, reopen Hartley absolute-reference evaluation, or run corrected Classic-18 by default.
