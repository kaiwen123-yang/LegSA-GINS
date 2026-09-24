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

P-09d/P-10 aliases: `<ADDENDUM_ROOT> = <CLEAN_ROOT>/stages/CLEAN6_ADDENDUM_FAMILIES_A1_A2`; `<PUBLICATION_ROOT> = <CLEAN_ROOT>/stages/CLEAN6_PUBLICATION_FIGURES`; `<HANDOFF_ROOT>` resolves through ignored local key `handoff_root`. The addendum scratch directory resolves through `addendum_a1_a2_scratch`.

If the local active branch contains unpushed commits and the remote branch is stale, do not add an unrelated documentation commit directly to that stale remote branch. Use a separate documentation branch or let the human push the complete local history.

---

## 3. Authoritative Canonical-541 roots and solver identity

Historical input gate for the explicit archive-only continuation from `5ce94dd`, before the 2026-09-12 human acceptance: `FAIL_MISSING_PRIOR_EVALUATION_FULL_FILE_SEAL`. All batch-8 solver pins and 6375 evaluator-file pins from 255 receipts matched; RUN_01963 lacked a complete historical evaluator-output seal. That input-check attempt invoked no new solver, evaluator, archive or cleanup. Its record remains `docs/paper_rebuild/CLEAN6_CANONICAL541_V2_IO_RECOVERY.md`; the accepted current post-hoc seal and completed continuation below supersede that historical stop.

P-09c protocol v2 root: `<CANONICAL541_V2_ROOT> = <CLEAN_ROOT>/stages/CLEAN6_BY2_CANONICAL_541_PROTOCOL_V2`. Scratch alias `<CANONICAL541_V2_SCRATCH>` resolves through ignored local key `canonical541_v2_scratch`. P-09c protocol v2 full execution, both frozen aggregates, v1/v2 comparison and validated handoff are complete: 5973 native terminals (5869 COMPLETED; 104 ALGORITHM_FAILURE_ALL_YAW_REJECTED), 11946 v3/v2 evaluator terminal records, archive pending 0. Scientific code `737a0fb5a4a5418500824855b89b0d25af69824a`; archive I/O code `ea478eea88aaf9739823dfc152fa108dd17f8d0c`. Original native reuse=33; native/evaluator repeat calls=0. Sequence/C00 gate PASS 182/182 (P-06 105/105; P-07 CAL C00 77/77). Full factual record: `docs/paper_rebuild/P09C_PROTOCOL_V2_FINAL.md`; source tables `<CANONICAL541_V2_ROOT>/13_AGGREGATE/v3/` and `/v2/`.

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
# bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only)
<CANONICAL541_ATTEMPT>/10_INTERNAL_ABLATION_RUNS/
# bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only)
<CANONICAL541_ATTEMPT>/12_OFFLINE_EVALUATION/
# bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only)
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
# bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only: 04_SOLVER_RUNS/, 04_SOLVER_RUNS_V2/, 07_OFFLINE_EVALUATION/)
<CLEAN5_BY2O_ROOT> = <CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE
# bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only: 04_SOLVER_RUNS/, 04_SOLVER_RUNS_V2/, 07_OFFLINE_EVALUATION/)
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

P-09ab policy-v2 exact-file completion (2026-09-11, audit `<CLEAN_ROOT>/storage_purge/20260911T070041Z`): C1/C2/C3/C4/C5/D PASS; 73,039 listed files / 530,120,461,090 logical bytes quarantined and purged. All annotations below mean listed bulk only; retained records remain at their registered locations. Final ledger SHA-256: `9e28e07eea72f9de8b3ebc2ba033139d2f694c9934357dab2a40a8e60ad4f814`. Completion record: `docs/paper_rebuild/purge/STORAGE_PURGE_20260911T070041Z.md`.

Additional exact-file scope:

```text
<CLEAN5_PARITY_ROOT> = <CLEAN_ROOT>/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/
<CLEAN5_PARITY_ROOT>/03_PARITY_RUNS/  # bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only)
<CLEAN5_PARITY_ROOT>/07_OFFLINE_EVALUATION/  # bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only)
<CLEAN5_PARITY_ROOT>/10_IMU_PROCESSING/  # bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only)
<CLEAN5_PARITY_ROOT>/12_PARITY_GENERALIZATION/  # bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only)
<CLEAN5_PARITY_ROOT>/13_NOISE_MODEL_SENSITIVITY/  # bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only)
<CLEAN5_P07_ROOT> = <CLEAN_ROOT>/stages/CLEAN5_DEGSUBSET_BY2/
<CLEAN5_P07_ROOT>/03_RUNS/  # bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only)
<CLEAN5_P07_ROOT>/07_EVALUATION/  # bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only)
<CANONICAL_STAGE> = <CLEAN_ROOT>/stages/CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX/
<CANONICAL_STAGE>/.attempt_20260808T192851P0800/01_COMPACT_READINESS_RUN/  # bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only)
<CANONICAL_STAGE>/.attempt_20260808T192851P0800/02_MATRIX_SPEC_LOCK/INTERNAL_ABLATION_QUEUE_DRAFT.csv  # bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only)
<CANONICAL_STAGE>/.attempt_20260808T195407P0800/01_COMPACT_READINESS_RUN/  # bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only)
<CANONICAL_STAGE>/.attempt_20260808T195407P0800/02_MATRIX_SPEC_LOCK/INTERNAL_ABLATION_QUEUE_DRAFT.csv  # bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only)
```

P-07 retained subset results and decision: `<CLEAN5_P07_ROOT>/08_AGGREGATE/` and `<CLEAN5_P07_ROOT>/08_AGGREGATE/DEGRADATION_SUBSET_DECISION.json`; record: `docs/paper_rebuild/CLEAN5_DEGRADATION_SUBSET_RESULTS.md`.

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

The reference is Fixposition-derived and not independent ground truth. This limitation belongs in manuscript prose and claim boundaries. For publication graphics, the human requires visible labels `Truth` or `Truth Trajectory`; do not place “the fused navigation solution output directly by the commercial low-cost dual-antenna GNSS/INS receiver (Fixposition Vision-RTK 2); the estimator under test never reads it (file-access audit)” wording inside the figure itself.

---

## 7. Internal method identities and current interpretation

<!-- P13_SECTION_7_BEGIN -->
### Protocol v2.1 current anchors (P-13)

Current manuscript protocol: v2.1. F04 remains the proposed method; the v1 rule and A04 Outcome are unchanged. Primary evaluator: v3; v2 is parallel.

| Sequence | Profile | Status | H RMSE (m) | 3D RMSE (m) | Up RMSE (m) | Yaw RMSE (deg) | Roll RMSE (deg) | Pitch RMSE (deg) | CSV row |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BY2 | F02 | COMPLETED | 0.10193086285530993 | 0.11269262038758635 | 0.048059607649174926 | 2.3131754694996527 | 3.3382092245764645 | 2.918852028781131 | 2 |
| BY2 | F03 | COMPLETED | 0.09919307794859032 | 0.11013793160092439 | 0.04786540780579205 | 2.250660249295421 | 3.3291820977434514 | 2.923446485452237 | 3 |
| BY2 | F04 | COMPLETED | 0.09716199583877864 | 0.10881571662731311 | 0.04899394605194471 | 2.2211070025147257 | 2.254053976093779 | 2.2633582019083436 | 4 |
| BY2 | A03 | COMPLETED | 0.09732041302814125 | 0.10869756330028135 | 0.048413814923538766 | 2.2090301507646393 | 2.253440585931212 | 2.2632130119301097 | 5 |
| BY2 | A04 | COMPLETED | 0.09616685973422963 | 0.10839664016171717 | 0.05001766375197666 | 2.22360844484946 | 2.066601967091301 | 2.1396053708581535 | 6 |
| BY2 | A05 | COMPLETED | 0.09789124513240088 | 0.10923369703914852 | 0.0484696265228925 | 2.2579230800811567 | 3.330586399014229 | 2.9238639927530827 | 7 |
| BY2 | A06 | COMPLETED | 0.09825542533256626 | 0.1097912272228355 | 0.048989641433805076 | 2.224103947855017 | 2.25422161215289 | 2.263278546761912 | 8 |
| BY2 | A07 | COMPLETED | 0.09911674040651422 | 0.11033189433397571 | 0.0484664696311919 | 2.260695738938855 | 3.330893141578931 | 2.9240352620142334 | 9 |
| BY2 | A08 | COMPLETED | 0.09903075172575321 | 0.1106914749600939 | 0.04945212676390496 | 2.2593132413839867 | 3.3292873977318616 | 2.923219018869731 | 10 |
| BY2 | A09 | COMPLETED | 0.09925543267175785 | 0.11018739966389386 | 0.04784999613200422 | 2.248764315320997 | 3.3293166284027964 | 2.9235984056315263 | 11 |
| BY2H | A03 | COMPLETED | 0.068939219267719 | 0.0825261750110712 | 0.045364673576642374 | 1.768062843104732 | 1.9642618812485193 | 1.6980356895800854 | 12 |
| BY2H | A04 | COMPLETED | 0.07017230953325597 | 0.08384840109553972 | 0.04589554816153109 | 1.7824851872621246 | 1.835168382951697 | 1.6592873174582772 | 13 |
| BY2H | A05 | COMPLETED | 0.06801024807979977 | 0.08150639185702768 | 0.044921020354344546 | 1.7739301906361205 | 2.781679345582052 | 1.8806505467534202 | 14 |
| BY2H | A06 | COMPLETED | 0.06908916686863224 | 0.08264646740953738 | 0.04535554648192444 | 1.7743380988924626 | 1.963487186032263 | 1.6983218961084199 | 15 |
| BY2H | A07 | COMPLETED | 0.06850155672421525 | 0.08191827143337015 | 0.044923712235192974 | 1.774520669051904 | 2.7806233381287315 | 1.8813180137868417 | 16 |
| BY2H | A08 | COMPLETED | 0.06853546616127866 | 0.08221670982833543 | 0.045414504875127014 | 1.7758540488181764 | 2.7810460547430735 | 1.879863499327224 | 17 |
| BY2H | A09 | COMPLETED | 0.06889270822020953 | 0.0822567201306383 | 0.04494399582519593 | 1.7627328257218304 | 2.7807822480443742 | 1.8812371683388185 | 18 |
| BY2H | F02 | COMPLETED | 0.07063888091064825 | 0.08397461970937586 | 0.04540798673169235 | 1.6567572212082546 | 2.7837750386115134 | 1.8799417805283283 | 19 |
| BY2H | F03 | COMPLETED | 0.06889414440320393 | 0.08223248246837273 | 0.04489741685065756 | 1.7640484726849452 | 2.781127084792018 | 1.8813001224077461 | 20 |
| BY2H | F04 | COMPLETED | 0.06855282395068205 | 0.08219724192687043 | 0.04535302535411786 | 1.773436559706182 | 1.963704160466064 | 1.6982671193113674 | 21 |
| BY2O | A03 | COMPLETED | 0.05701069531318317 | 0.07321763295077699 | 0.04594129291630895 | 3.213744643444327 | 1.505574467754178 | 1.6962307935153256 | 22 |
| BY2O | A04 | COMPLETED | 0.05642104424081327 | 0.07166108209524331 | 0.044181177596770684 | 3.188831733943275 | 1.4493535680834266 | 1.6792478396510406 | 23 |
| BY2O | A05 | COMPLETED | 0.05648395151879894 | 0.07245331408188485 | 0.045376711452795065 | 3.1905238704844403 | 1.872754824475464 | 1.7382398811649729 | 24 |
| BY2O | A06 | COMPLETED | 0.05790854742590718 | 0.07387160808779875 | 0.04586517869254179 | 3.194113001806082 | 1.5059000119082486 | 1.6960354796864674 | 25 |
| BY2O | A07 | COMPLETED | 0.05731208785930977 | 0.07310336849060958 | 0.04538091085335998 | 3.187585327998862 | 1.872269867017242 | 1.7376240588860825 | 26 |
| BY2O | A08 | COMPLETED | 0.057198769583016014 | 0.0719608586238077 | 0.04366538597178179 | 3.1701140175509566 | 1.8726066967916004 | 1.7379576589915084 | 27 |
| BY2O | A09 | COMPLETED | 0.05726426166377618 | 0.07310806493209508 | 0.04544880080065924 | 3.2045094306884527 | 1.8708858828414452 | 1.7380053876729116 | 28 |
| BY2O | F02 | COMPLETED | 0.05733296748353202 | 0.07362105267855322 | 0.0461843072593989 | 2.899741525819664 | 1.8741892051185538 | 1.736278656870533 | 29 |
| BY2O | F03 | COMPLETED | 0.05721958446878508 | 0.07201252666057631 | 0.04372325638901775 | 3.199298927139811 | 1.870957628261041 | 1.738096829436202 | 30 |
| BY2O | F04 | COMPLETED | 0.057041149159153724 | 0.0731928014290208 | 0.04586385814158297 | 3.197136492350906 | 1.5059072247937308 | 1.6961129933181778 | 31 |
| BY2 | F01 | COMPLETED | 0.09177145533263088 | 0.10351109355664635 | 0.04788054380877193 | 8.089647422454789 | 3.3312964026882526 | 2.933247658474164 | 32 |
| BY2H | F01 | COMPLETED | 0.06292589316025435 | 0.0773049305383686 | 0.04490416746278954 | 7.137487572272005 | 2.7849178101091736 | 1.8837935867303504 | 33 |
| BY2O | F01 | COMPLETED | 0.06284210260933396 | 0.07656942024179673 | 0.043746385631304584 | 5.739037942642961 | 1.8638937566682607 | 1.7427301533457709 | 34 |

`<CLEAN_ROOT>/stages/CLEAN6_SENSOR_MODEL_V21/20_FINALIZE/13_AGGREGATE_SEQUENCES/v3/UNIQUE_EVALUATION_RESULTS.csv`; SHA-256 `e26dfcd830d6c711ffbb7debd68293fbf7b7ea28240e16bce582381b61ea6a0b`

Full factual report: `docs/paper_rebuild/P13_FINAL_REPORT.md`.

数据包：`<HANDOFF_ROOT>/c541_v21_handoff.zip`; SHA-256 `98a77b4601b897956a6d87f5bfa92e008b584add35e48e2b22a9088ddec07585`

新二进制 SHA-256：`96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c`；旧二进制：`9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f`。

聚合来源 code_commit：`f9e3d82f614a803a20cb4934f36687fa3e1ffdc6`；文档准备 code_commit：`a2048cdeb52fb3b49e626970a1bc0b36219ca354`。
<!-- P13_SECTION_7_END -->

**pre-correction — original section text and numbers preserved.**

<!-- P13_PRE_CORRECTION_SECTION_7_BEGIN -->

Human decision (2026-09-13): manuscript proposed method: F04 under protocol v2; A04 = v1 pre-registered decision, retained as ablation. The ablation ladder is F01→F02→F03→A04→F04. Primary evaluation point: v3. Full statement and exact frozen rows: `docs/paper_rebuild/PROTOCOL_V2_METHOD_STATEMENT.md`.

### Addendum families A1/A2 anchors

P-09d terminal: `PASS_ADDENDUM_FAMILIES_A1_A2_COMPLETE`. Separate root: `<ADDENDUM_ROOT> = <CLEAN_ROOT>/stages/CLEAN6_ADDENDUM_FAMILIES_A1_A2`; aggregate tables: `13_AGGREGATE_ADDENDUM/{v3,v2}`. A1/D61 = 10/20/30 s × 9 seeds = 27 cases; A2/D62 = 10/20 s × 9 seeds = 18 cases. Each case has 11 configurations. Native terminals 495/495 COMPLETED; v3 and v2 each 495/495 COMPLETED; native/evaluation failures 0; retries 0; core solver/evaluator calls 0; archive pending 0; final scratch files 0.

Contract commit `98c1d42eeabe707115f9e67c21ed993572e4d0d1`; contract SHA-256 `fd11e416a3bd1a67c992a3606de0bb988035cae5c80647efa2091d00614546ec`. Scientific addendum code `f93cb84c2e67432873362fe00324d1c2c28fd899`; BOM continuation `3a61d157ef82af4bfb12f3d1f5c6491742da592c`; archive I/O continuation `9802311754fdc49f151ff36b4ffbff715085dfd9`. PRE/POST raw checkpoints each PASS 22/22. Earlier technical events and reused outputs remain separately recorded.

Seed ids 260306001–260306009 use anchors `[206.2, 107.20639, 189.207044, 227.201927, 148.204964, 226.215803, 258.208267, 247.210403, 299.203403]` s in that order. The original Go2 RP/HV source values and validity are retained; outage injection does not fabricate Go2 validity.

Both evaluator versions retain H1 `PARTIALLY_SUPPORTED`, H2 `SUPPORTED`, H3 `OBSERVED_SOME_SEED_HARM`; H3 full_vs_no_Go2 harm case–metric rows 32, missing 0. The complete eight comparisons, duration groups and seed signs are in `docs/paper_rebuild/ADDENDUM_FAMILIES_A1_A2_RESULTS.md` and its linked CSV companions. Addendum tables never enter the frozen 541-core PAIRWISE_SUMMARY. `data_mode=semisynthetic`, `synthetic_data_used=false`, `semisynthetic_data_used=true`, `trace_used_online=false`.

ADDENDUM_FAMILIES_A1_A2 — pre-registered 2026-09-13, added after the 541-core results were seen, to cover a scenario absent from the library.

### Protocol v2 anchors (P-09c)

The original role-validation stop, batch-8 archive interruption and missing historical evaluation seal remain preserved as historical records. RUN_01963 received the explicitly accepted current post-hoc seal; historical_full_file_seal_available=false. Its completed archive is identified by resolved rows; the original partial archive is retained.

Manuscript protocol selection: v2. Protocol v1 remains the original preregistered record. Existing v1 main-chain anchors, method identities and A04 Outcome are unchanged. Full factual record: `docs/paper_rebuild/P09C_PROTOCOL_V2_FINAL.md`; source tables `<CANONICAL541_V2_ROOT>/13_AGGREGATE/v3/` and `/v2/`.

P-07 CAL C00 eleven-profile native anchors each passed 7/7 byte checks (77/77 total); P-06 five configurations across three sequences passed 105/105. All eleven C00 v3/v2 evaluations are available, with the original 33 native outputs reused. The original 22 failed outer-validation records remain historical; separate revalidation records carry the repaired metadata.

Protocol v2 CAL C00 anchors, primary evaluator v3, window 66–340 s. Values are copied from the completed first-batch evaluations; all eleven native anchors are byte-equal to P-07 CAL C00. [Full-precision v3/v2 rows](docs/paper_rebuild/clean6/P09C_RESTART_C00_ANCHORS.csv).

| Method | Configuration | H RMSE (m) | 3D RMSE (m) | Up RMSE (m) | Yaw RMSE (deg) |
|---|---|---:|---:|---:|---:|
| F01 | single_antenna_EKF | 0.091771 | 0.103511 | 0.047881 | 8.089647 |
| F02 | basic_dual_yaw_EKF | 0.101670 | 0.112457 | 0.048059 | 2.387502 |
| F03 | AB0000 | 0.099429 | 0.110350 | 0.047865 | 2.149759 |
| F04 | AB1111 | 0.098336 | 0.109896 | 0.049064 | 2.102586 |
| A03 | AB0111 | 0.098475 | 0.109762 | 0.048481 | 2.105506 |
| A04 | AB1011 | 0.097883 | 0.109953 | 0.050086 | 2.116232 |
| A05 | AB1101 | 0.099349 | 0.110540 | 0.048466 | 2.142496 |
| A06 | AB1110 | 0.098401 | 0.109954 | 0.049064 | 2.102604 |
| A07 | AB1100 | 0.099407 | 0.110592 | 0.048466 | 2.142513 |
| A08 | AB1000 | 0.099272 | 0.110907 | 0.049452 | 2.149459 |
| A09 | AB0100 | 0.099532 | 0.110436 | 0.047850 | 2.140686 |

```text
F01 = single-antenna EKF
F02 = basic dual-yaw EKF
F03 = strong dual-yaw EKF = AB0000
A04 = AB1011 = no Source-Aware; v1 pre-registered decision retained as ablation
F04 = AB1111 = Full; manuscript proposed method under protocol v2
```

Current manuscript role:

```text
A04:
v1 pre-registered decision (2026-09-08), retained as no-SA ablation

F04:
protocol v2 proposed method (human decision, 2026-09-13)

final manuscript identity:
F04 (AB1111); v1 rule text and A04 Outcome unchanged
```

Do not claim Full universally dominates Strong or A04. Do not claim Source-Aware is nominal-silent/fault-active; clean touch rate is about 84.8%.

Historical protocol v1 full-C00 anchors (unchanged):

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

Protocol v2 full-matrix key pairs, primary evaluator v3. Delta is candidate minus reference; negative is better. Median intervals are paired percentile 95% CI (10000 resamples; seed 20260904). Finite and failure-aware denominators remain distinct.

| Comparison | Metric | Median delta | Median 95% CI | Finite win rate | Finite N | Failure-aware win rate | Denominator |
|---|---|---:|---|---:|---:|---:|---:|
| A04_vs_F03 | horizontal_rmse_m | -0.001546 | [-0.001548, -0.001546] | 89.54% | 526 | 88.54% | 541 |
| A04_vs_F03 | yaw_rmse_deg | -0.033527 | [-0.033532, -0.033527] | 94.68% | 526 | 93.53% | 541 |
| A04_vs_F03 | yaw_p95_absolute_deg | -0.134468 | [-0.134468, -0.134467] | 97.91% | 526 | 96.67% | 541 |
| full_vs_strong | horizontal_rmse_m | -0.001097 | [-0.001108, -0.001093] | 87.95% | 523 | 86.32% | 541 |
| full_vs_strong | yaw_rmse_deg | -0.047173 | [-0.047229, -0.047173] | 97.32% | 523 | 95.38% | 541 |
| full_vs_strong | yaw_p95_absolute_deg | -0.139524 | [-0.139525, -0.139524] | 97.90% | 523 | 95.93% | 541 |
| full_vs_no_SA | horizontal_rmse_m | 0.000446 | [0.000437, 0.000452] | 24.29% | 527 | 24.21% | 541 |
| full_vs_no_SA | yaw_rmse_deg | -0.013646 | [-0.013650, -0.013646] | 88.43% | 527 | 86.69% | 541 |
| full_vs_no_SA | yaw_p95_absolute_deg | -0.005057 | [-0.005057, -0.005057] | 78.56% | 527 | 77.08% | 541 |

All 15 pairs, five primary/secondary metrics and both evaluator versions: [full tables](docs/paper_rebuild/clean6/P09C_PROTOCOL_V2_FINAL_KEY_PAIRS.csv). Frozen MAINTAINED / FLIPPED / INCOMPLETE classifications: [v1/v2 comparison](docs/paper_rebuild/clean6/P09C_PROTOCOL_V2_FINAL_V1_V2_COMPARISONS.csv).


<!-- P13_PRE_CORRECTION_SECTION_7_END -->

## 7A. Canonical-541 detailed numerical results and interpretation

The numerical records in section 7A are protocol v1 preregistration history; the manuscript uses the protocol v2 tables in section 7 above.

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
for which the declared receiver reference does not provide a suitable
reference velocity. Reference description: the fused navigation solution output directly by the commercial low-cost dual-antenna GNSS/INS receiver (Fixposition Vision-RTK 2); the estimator under test never reads it (file-access audit). Unsupported fields remain `NA`; never convert them to
zero.

Uncertainty results use diagonal `KF_GINS_STD.txt` fields:

```text
diagonal normalized-error consistency diagnostic only
not full-covariance NEES
```

The predicted STD values are generally overconfident relative to the
declared receiver reference (the fused navigation solution output directly by the commercial low-cost dual-antenna GNSS/INS receiver (Fixposition Vision-RTK 2); the estimator under test never reads it (file-access audit)). No integrity or calibrated-confidence claim is
allowed from these diagonal results.

Recovery-time fields remain `NA` where no frozen recovery rule or
identifiable event window exists. Do not invent a threshold after seeing
the results.

### 7A.10 Canonical-541 claim boundary

Historical v1 interpretation below is retained as recorded. Current manuscript authority is the 2026-09-13 human decision in §7: F04 under protocol v2; A04 remains the v1 decision and an ablation.

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

<!-- H_EXT_SECTION_8_BEGIN -->
H-EXT-04L：合约 v1.2 只读收束；native/evaluator/trace 读取均为 0，分段补齐、段外诊断及 FIG02S/FIG02S-b 见 H_EXT_04L_RECORD.md。
论文 LC01 采用文献配置（BY2/BY2O FILE_START，BY2H CONTRACT_START）；S 完整进补充，amended_after_results_seen=true。
H-EXT-04 执行部分取消；仅库代码 NOT_AUTHORIZED_FOR_EXECUTION，T5 待预注册；额外身份验证预算问题作废。
v2.1、原28图及 RENDER_MANIFEST 不变；新派生仅 <HEXT_ROOT>/11_READONLY_CLOSEOUT_H_EXT_04L/，旧 H03 证据保留。
<!-- H_EXT_SECTION_8_END -->

Protocol v2 publication uses frozen v3 evaluation-point rows; LegSA rows are the v2-chain C00 F04 and A04. External methods without compatible IMU-point NAV/v3 evidence remain visible as `Not comparable` (不可比), with method-native information structure retained. Missing comparable NAV is not a zero error and does not remove the method from the registry.

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

Raw-layer outputs remain method-native diagnostics. Their presence in the figure registry does not create v3 navigation-point comparability. The v2 package lists unavailable/non-comparable external rows explicitly.

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

<!-- P13_SECTION_11_BEGIN -->
### Protocol v2.1 completed execution and diagnostics

主链归档闭合：5880 新 native、11760 evaluator terminal slots、5880 已验证归档、pending=0。下游诊断：21 native、42 evaluator terminal slots、21 已验证归档、pending=0，九格原点诊断 `PASS`（按原记录报告，不作为额外停止条件）。正式核心每评估器 5951 行、附加族 495 行、三序列 33 行；三序列 BY2/C00 为同一组输出别名。完整 F01 正式复用 588 native，不计为新增主链求解。

| Sequence | Gate | Max absolute difference | Compared statistics | Final scaled HV residual σ (m/s) |
| --- | --- | --- | --- | --- |
| BY2 | PASS_HV_RP_REPRODUCTION | 8.326672684688674e-17 | 183 | 0.13145029910885764 |
| BY2H | PASS_HV_RP_REPRODUCTION | 2.7755575615628914e-17 | 183 | 0.21125519645608834 |
| BY2O | PASS_HV_RP_REPRODUCTION | 1.1102230246251565e-16 | 233 | 0.10363380102981933 |

F01 不变门：50/50 runs、350/350 完整文件；二进制桥接：44/44。三序列基础 GNSS15/18 非 yaw_std token 相同，yaw_std 全为 2.933193；注入表按原顺序保留预注册 yaw_std 倍乘，验证口径见 `docs/paper_rebuild/clean6/P13_APPENDIX.md`。IMU/RD 哈希门通过。

| Evaluator | Profile | H7 | H8 | H9 | H10 | H11 |
| --- | --- | --- | --- | --- | --- | --- |
| v3 | F02 | NOT_SUPPORTED | UNCHANGED | NOT_SUPPORTED | PARTIALLY_SUPPORTED | REPORTED_NON_DIRECTIONAL |
| v3 | F03 | NOT_SUPPORTED | NOT_SUPPORTED | NOT_SUPPORTED | PARTIALLY_SUPPORTED | INCOMPLETE |
| v3 | F04 | NOT_SUPPORTED | SUPPORTED | SUPPORTED | PARTIALLY_SUPPORTED | INCOMPLETE |
| v3 | A03 | INCOMPLETE | SUPPORTED | SUPPORTED | PARTIALLY_SUPPORTED | INCOMPLETE |
| v3 | A04 | NOT_SUPPORTED | NOT_SUPPORTED | SUPPORTED | PARTIALLY_SUPPORTED | INCOMPLETE |
| v3 | A05 | INCOMPLETE | SUPPORTED | SUPPORTED | PARTIALLY_SUPPORTED | INCOMPLETE |
| v3 | A06 | INCOMPLETE | SUPPORTED | NOT_SUPPORTED | PARTIALLY_SUPPORTED | INCOMPLETE |
| v3 | A07 | INCOMPLETE | SUPPORTED | NOT_SUPPORTED | PARTIALLY_SUPPORTED | INCOMPLETE |
| v3 | A08 | INCOMPLETE | NOT_SUPPORTED | NOT_SUPPORTED | PARTIALLY_SUPPORTED | INCOMPLETE |
| v3 | A09 | INCOMPLETE | SUPPORTED | NOT_SUPPORTED | PARTIALLY_SUPPORTED | INCOMPLETE |
| v2 | F02 | NOT_SUPPORTED | UNCHANGED | NOT_SUPPORTED | PARTIALLY_SUPPORTED | REPORTED_NON_DIRECTIONAL |
| v2 | F03 | NOT_SUPPORTED | NOT_SUPPORTED | NOT_SUPPORTED | PARTIALLY_SUPPORTED | INCOMPLETE |
| v2 | F04 | NOT_SUPPORTED | SUPPORTED | SUPPORTED | PARTIALLY_SUPPORTED | INCOMPLETE |
| v2 | A03 | INCOMPLETE | SUPPORTED | SUPPORTED | PARTIALLY_SUPPORTED | INCOMPLETE |
| v2 | A04 | NOT_SUPPORTED | NOT_SUPPORTED | SUPPORTED | PARTIALLY_SUPPORTED | INCOMPLETE |
| v2 | A05 | INCOMPLETE | SUPPORTED | SUPPORTED | PARTIALLY_SUPPORTED | INCOMPLETE |
| v2 | A06 | INCOMPLETE | SUPPORTED | NOT_SUPPORTED | PARTIALLY_SUPPORTED | INCOMPLETE |
| v2 | A07 | INCOMPLETE | SUPPORTED | NOT_SUPPORTED | PARTIALLY_SUPPORTED | INCOMPLETE |
| v2 | A08 | INCOMPLETE | NOT_SUPPORTED | NOT_SUPPORTED | PARTIALLY_SUPPORTED | INCOMPLETE |
| v2 | A09 | INCOMPLETE | SUPPORTED | NOT_SUPPORTED | PARTIALLY_SUPPORTED | INCOMPLETE |

A04/F04 robustness and V-CHK A04 use the completed corrected chain without a new decision. Full family counts and all unavailable H7 entries: `docs/paper_rebuild/P13_FINAL_REPORT.md`.
<!-- P13_SECTION_11_END -->

**pre-correction — original section text and numbers preserved.**

<!-- P13_PRE_CORRECTION_SECTION_11_BEGIN -->

P-09d A1/A2 is complete: 495 native and 990 evaluator terminals COMPLETED, failure/retry/core-call/archive-pending counts 0; independent aggregates and full record are linked from §7. Exact cleanup removed 47,565 files / 65,698,307,966 bytes; scratch files 0. The original technical-stop, interruption and resource scopes remain preserved.

Historical archive-only input check, before the 2026-09-12 human acceptance: the first seven batch ledgers and available batch-8 pins passed, but the missing RUN_01963 historical evaluation seal stopped that check. It invoked no new solver or evaluator. The accepted current post-hoc seal and completed continuation are recorded below.

P-09c protocol v2 full execution, both frozen aggregates, v1/v2 comparison and validated handoff are complete: 5973 native terminals (5869 COMPLETED; 104 ALGORITHM_FAILURE_ALL_YAW_REJECTED), 11946 v3/v2 evaluator terminal records, archive pending 0. Scientific code `737a0fb5a4a5418500824855b89b0d25af69824a`; archive I/O code `ea478eea88aaf9739823dfc152fa108dd17f8d0c`. Original native reuse=33; native/evaluator repeat calls=0. Sequence/C00 gate PASS 182/182 (P-06 105/105; P-07 CAL C00 77/77). Full factual record: `docs/paper_rebuild/P09C_PROTOCOL_V2_FINAL.md`; source tables `<CANONICAL541_V2_ROOT>/13_AGGREGATE/v3/` and `/v2/`.

Historical original P-09c attempt: 33 native exits were zero, but 22 outer records failed on runtime_role. Those original records and their FAIL gate are preserved; the authorized restart revalidated them and obtained the current 182/182 PASS gate without repeating native execution.

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


<!-- P13_PRE_CORRECTION_SECTION_11_END -->

## 12. Current publication-figure task

P-10 figure delivery is complete: 29 composites (8 reissued + 21 new; 2 supplementary as an overlapping role), 87 PNG/PDF/SVG exports, 29/29 visual PASS. Figure root `<PUBLICATION_ROOT>/figures/v2/`; index `FIGURE_INDEX.md` has GPS Solutions and TIM section columns. ZIP `<HANDOFF_ROOT>/figures_v2_handoff.zip`, SHA-256 `d304001f0f77818cef0604b3b790cc414649c06892d1a7963b1c0d7869c52a60`, 29063129 bytes. Full record: `docs/paper_rebuild/PROTOCOL_V2_FIGURE_DELIVERY.md`. v1 original/copy bytes remain unchanged; no new scientific execution.

P-10 (2026-09-13) carries the four registered composites below into `<PUBLICATION_ROOT>/figures/v2/` as FIG01–FIG04. No prior rendered `15_HORIZONTAL_PUBLICATION_FIGURES` directory was present at the P-10 source check. FIG02 uses compatible frozen v3 rows and the protocol v2 C00 F04/A04 rows. FIG01/FIG03/FIG04 retain their information-layer, native raw and observability roles; native diagnostics are not re-labelled as v3 navigation accuracy. The original task boundaries below are historical; the separate P-10 instruction also authorizes the matrix/addendum figure package.

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

P-10 authorizes the protocol v2 MFIG00–MFIG22 series, SFIG01–SFIG02, and the four horizontal composites registered in §12. The proposed-method label is F04. Output is `<PUBLICATION_ROOT>/figures/v2/`; the byte-identical copy of the eight existing v1 composites is at `figures/v1_prereg/`, with their original registered root retained. New figures consume the combined v3 handoff package and exact source-row hashes; historical v1 exports remain unchanged.

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
Full (F04). The protocol v2 proposed method is F04 by the 2026-09-13 human decision; the executed v1 rule and A04 Outcome remain unchanged.

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

Do not place `the fused navigation solution output directly by the commercial low-cost dual-antenna GNSS/INS receiver (Fixposition Vision-RTK 2); the estimator under test never reads it (file-access audit)`, `Fixposition-derived reference`, `not independent ground truth`, or their Chinese equivalents inside the figure. The human controls that explanation in manuscript prose.

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

冻结解析器读取的 runtime config 只能逐行文本替换克隆，禁止 YAML 往返。

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

<!-- H_EXT_SECTION_18_BEGIN -->
H-EXT-04L：合约 v1.2 只读收束；native/evaluator/trace 读取均为 0，分段补齐、段外诊断及 FIG02S/FIG02S-b 见 H_EXT_04L_RECORD.md。
论文 LC01 采用文献配置（BY2/BY2O FILE_START，BY2H CONTRACT_START）；S 完整进补充，amended_after_results_seen=true。
H-EXT-04 执行部分取消；仅库代码 NOT_AUTHORIZED_FOR_EXECUTION，T5 待预注册；额外身份验证预算问题作废。
v2.1、原28图及 RENDER_MANIFEST 不变；新派生仅 <HEXT_ROOT>/11_READONLY_CLOSEOUT_H_EXT_04L/，旧 H03 证据保留。
<!-- H_EXT_SECTION_18_END -->

<!-- T5BC_SECTION_18_BEGIN -->
T5bc 人工例外（授权字符串：T5bc prompt 2026-09-19）：冻结链外 v3 候选试点，C00/三序列15次 native（F04-R5σ/R5W 各三序列；B3 F02′/A04′/F04′ 各三序列）与61例完整子集244次 native（F04类 R5/R5σ/R5W/B3 各61），另候选二进制关闭B3的BY2 C00 F02/F04身份门2次。预算 native≤261、evaluator≤518；不需身份评估器，native trace=0，评估器子进程各打开 trace 1次，禁止重试与参数搜索。全61 case ID逐项冻结在T5BC_CONTRACT_V1.yaml，不再沿用旧42例筛选或PENDING列表。
预注册科学定义已由最新提示固定：模型基线0.35 m；σ/k/k_b均只应用BY2双fixed原始5 Hz的1 s免真值标定，0.2 s与BY2H/BY2O数值只报；向量k_b²分母为6·mean(S第二端+S第一端)。F02不跑R5σ/R5W。B3的GNSS标量yaw_valid全0，三维量测替代而不叠加。HV保留冻结1 Hz status A1，IMU/RD/RP/HV、评估器/窗口/评估点、门控/初始协方差/过程噪声不改。
配置仅逐行文本替换，禁止YAML往返：标量只改gnsspath；B3只改gnsspath并增加四个必要键。a逐行字节差与b旧211项有效参数回显相等均为硬门。D37旧运行无回显，先证明与D36回显见证配置仅五个元数据/路径行不同，再派生期望回显；旧失败行保持不可用。C00保留real_clean，退化例外层semisynthetic角色与历史native配置标志分别记录。D57精确时间不匹配行无效，不做时间修复。全61例原yaw/A1故障列由新输入替换，逐例标记，不声称原航向注入保留。
预注册 code_freeze `b0a9230f0711c7b81af9d868a98d0eb537ad6eb9` 已push；顺序为标定、两次NAV_10HZ逐字节身份门、provider、矩阵。单批归档IO失败>1%、身份/config/provider/冻结哈希或评估器进程不等硬停；原生失败沿用H-EXT-03/D12，发散归类后继续，无法分类才停。簿记冲突自行裁定附录记录。当前 **HARD_STOP_PARTIAL_EVIDENCE，T5bc未完成**：标定及64个provider bundle完成，BY2 F02/F04两身份NAV字节/211回显PASS；实际native 62/261（身份2，矩阵60＝58完成+D27发散+D57硬停），evaluator 116/518均完成，native/evaluator trace=0/116、重试0。D57全窗口56642循环、位置/速度/航向尝试1365/1371/0及3321行sidecar全无效证据支持报告层ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT；冻结分类器漏计demo固定stderr前缀而误停。原HARD_STOP不改，D57回显未输出记UNAVAILABLE，不能记D6通过；冻结控制器无追加裁定消费接口，不自动越过硬停。剩余199 native、最多398相关评估待新的控制冻结续作，完整汇总/最终图未产出。停后660项冻结哈希复核PASS；独立partial_v1交接保留现有全部证据与未应用修复提案。预注册255项合成/回归测试通过（含C++18与T5a27），但未覆盖实际stderr前缀边界；不能据此声称本次完整执行通过。首个历史B3合成一致性测试的角度表示失败保留；后续仅圆周角差测试修复，数值雅可比最大绝差8.8819e-11、B3/标量yaw修正差1.32339e-13 rad，C++18项通过。
候选二进制仅B3与身份门使用，SHA256 cbf554baf9c83490e40b207b97f04ef77f51d9962f7bce463f1e644416ef789e；冻结96ae436d…二进制、v2.1任何产物、20_FINALIZE、28图和RENDER_MANIFEST不变。输出根<CLEAN_ROOT>/stages/CLEAN7_T5BC_V3_CANDIDATE_PILOT/；先ext4 scratch后归档G:。两次提交/push按用户授权执行；证据只进敏感性/限制与v3决策记录。记录docs/paper_rebuild/hext/T5BC_V3_CANDIDATE_PILOT.md。
<!-- T5BC_SECTION_18_END -->

<!-- T5A_SECTION_18_BEGIN -->
T5a-R 人工例外（2026-09-18 本任务授权）：原三次 native 均按 INVALID_CONFIG_PARSE 保留历史记录，不进任何续作结果表；新矩阵 native 16、evaluator 32，条件保真 native 至多 1、其 evaluator 至多 2。当前已有有效参数回显，采用 a 字节门与 b 回显门，c 不需要，计划保真调用 0。先修复与合同 v1.1 预注册提交并 push 后执行。
冻结解析器读取的 runtime config 只能逐行文本替换克隆，禁止 YAML 往返。仅 gnsspath 一行可变；其余字节相同，实际静态有效参数回显须与对应冻结回显逐字段相同。A0 只读回查所有冻结 v2.1 runtime config 及每序列每配置的回显，报告后继续，任何结论均不改主链。
D3 修订继续有效：R1=E∩双 fixed，精确子集/差集硬门；BY2O R1F 保持冻结 valid 模式，R5 双 fixed、R5F 双方 fixed/float。yaw_std 固定 2.933193，二进制 96ae436d… 与 IMU/RD/RP/HV、非 yaw 列均不变。a–c/D3/关键输入身份/评估器进程失败硬停，其余记录继续。
新证据只进入敏感性/限制；协议 v2.1 行、原28图与 RENDER_MANIFEST 不变。续作根 <CLEAN_ROOT>/stages/CLEAN7_T5A_HEADING_SENSITIVITY/T5A_R/；v2 包 t5a_heading_sensitivity_handoff_v2.zip，v1 部分包保留。当前状态：T5a-R PASS_T5A_HEADING_SENSITIVITY_COMPLETE，code_freeze d9650fbdf20b2a981a85c1d9875c143c60bc6362；16/16 native、32/32 evaluator 完成，a/b 门 16/16 PASS（b 为 211 静态回显项），保真 0/0、重试 0、trace native 0/evaluator 32。A0 6539 配置语法与归档哈希通过，33 回显样本已映射项无不一致（保留 1 ULP 往返差异与未映射覆盖边界）。新表每版 22 行、BY2O 分段 100 行、门控 74 行、D4 1025 行、误差序列 44 份，6 组图/18 导出机器与视觉 QA PASS。v2 包 902400804 bytes / 1006 members，SHA256 b8d1451345d81bd87edb2288017d4f931d8a303f1ceb45feb67972264e7b1b20；详见 docs/paper_rebuild/hext/T5A_R_HEADING_SENSITIVITY.md。历史 code_freeze a4f2e429c56089e9874097764f337af1f696423b 与三次无效调用原记录不改写。
<!-- T5A_SECTION_18_END -->

### C-CLOSE freeze rule (2026-09-15)

协议 v2.1 是论文唯一链；此后任何新发现只作为限制或后续工作写入论文，不再修改 provider、参数、求解器，不再重跑；唯一例外是逐字节身份门检出的数值错误；EXT06 只新增对比行。

Conversation C is `COMPLETE`. Remaining work is conversation D (uncertainty), conversation E (TIM manuscript assembly), and the EXT06 baseline in an independent conversation. This rule supersedes the historical next-action and execution clauses below; current ownership and the shutdown verification record are in `docs/paper_rebuild/CONVERSATION_HANDOFF.md` §§5–7.

<!-- P13_SECTION_18_BEGIN -->
### Protocol v2.1 delivery state

主链归档闭合：5880 新 native、11760 evaluator terminal slots、5880 已验证归档、pending=0。下游诊断：21 native、42 evaluator terminal slots、21 已验证归档、pending=0，九格原点诊断 `PASS`（按原记录报告，不作为额外停止条件）。正式核心每评估器 5951 行、附加族 495 行、三序列 33 行；三序列 BY2/C00 为同一组输出别名。完整 F01 正式复用 588 native，不计为新增主链求解。

数据包：`<HANDOFF_ROOT>/c541_v21_handoff.zip`; SHA-256 `98a77b4601b897956a6d87f5bfa92e008b584add35e48e2b22a9088ddec07585`

新二进制 SHA-256：`96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c`；旧二进制：`9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f`。

聚合来源 code_commit：`f9e3d82f614a803a20cb4934f36687fa3e1ffdc6`；文档准备 code_commit：`a2048cdeb52fb3b49e626970a1bc0b36219ca354`。

图包：`<HANDOFF_ROOT>/figures_v21_handoff.zip`; SHA-256 `20495ab65d1b7ae41a83de52aa34e80051b7154b45db4d5de63478a064e0c088`。v2.1 共 28 图、84 PNG/PDF/SVG 导出，已完成视觉核查；MFIG21 沿用原 v2 产物。

Current references: `docs/paper_rebuild/P13_FINAL_REPORT.md` and `docs/paper_rebuild/PROTOCOL_V2_METHOD_STATEMENT.md`. Earlier protocol-v2 numbers below are pre-correction. The decision rule and Outcome remain unchanged.
<!-- P13_SECTION_18_END -->

**pre-correction — original section text and numbers preserved.**

<!-- P13_PRE_CORRECTION_SECTION_18_BEGIN -->

P-10 figure delivery is complete: 29 composites (8 reissued + 21 new; 2 supplementary as an overlapping role), 87 PNG/PDF/SVG exports, 29/29 visual PASS. Figure root `<PUBLICATION_ROOT>/figures/v2/`; index `FIGURE_INDEX.md` has GPS Solutions and TIM section columns. ZIP `<HANDOFF_ROOT>/figures_v2_handoff.zip`, SHA-256 `d304001f0f77818cef0604b3b790cc414649c06892d1a7963b1c0d7869c52a60`, 29063129 bytes. Full record: `docs/paper_rebuild/PROTOCOL_V2_FIGURE_DELIVERY.md`. v1 original/copy bytes remain unchanged; no new scientific execution.

P-09d combined data handoff: `<HANDOFF_ROOT>/c541_v2_handoff_v3.zip` (`handoff_root` in ignored local config), SHA-256 `79e75f7d867a4930dc80c0f906173b48aab1bec6a5caac44b63bae993a848dd3`, 601520239 bytes, 9712 ZIP members; full CRC/member-hash validation PASS, 608 base members preserved. Delivery record: `docs/paper_rebuild/clean6/ADDENDUM_HANDOFF_V3.md`. All new handoff packages are on the project G: handoff root.

P-09d A1/A2 is complete: 495 native and 990 evaluator terminals COMPLETED, failure/retry/core-call/archive-pending counts 0; independent aggregates and full record are linked from §7. Exact cleanup removed 47,565 files / 65,698,307,966 bytes; scratch files 0. The original technical-stop, interruption and resource scopes remain preserved.

Current manuscript method: F04 (AB1111), protocol v2, primary evaluator v3. A04 remains the v1 pre-registered decision and an ablation row. P-09d A1/A2 and P-10 publication work are explicitly authorized by the 2026-09-13 instruction. All new handoff ZIPs use `<HANDOFF_ROOT>` (the project handoff directory resolved by ignored local config). Method/reference wording: `PROTOCOL_V2_METHOD_STATEMENT.md` and `REFERENCE_WORDING_ERRATUM_20260913.md`.

P-09c protocol v2 full execution, both frozen aggregates, v1/v2 comparison and validated handoff are complete: 5973 native terminals (5869 COMPLETED; 104 ALGORITHM_FAILURE_ALL_YAW_REJECTED), 11946 v3/v2 evaluator terminal records, archive pending 0. Scientific code `737a0fb5a4a5418500824855b89b0d25af69824a`; archive I/O code `ea478eea88aaf9739823dfc152fa108dd17f8d0c`. Original native reuse=33; native/evaluator repeat calls=0. Sequence/C00 gate PASS 182/182 (P-06 105/105; P-07 CAL C00 77/77). The original role-validation stop, batch-8 archive interruption and missing historical evaluation seal remain preserved as historical records. RUN_01963 received the explicitly accepted current post-hoc seal; historical_full_file_seal_available=false. Its completed archive is identified by resolved rows; the original partial archive is retained. All encountered bookkeeping repairs are collected in the final report notes table.

The accepted post-hoc seal and I/O freeze are under `<CANONICAL541_V2_ROOT>/IO_RECOVERY/IO_RECOVERY_20260912/`. The original failed input audit remains available; its historical seal gap is not rewritten as a historical PASS.

Final scratch release: the supplemental batch-14 exact ledger removed 198 derived preparation files (66,327,303 bytes); remaining scratch file count is 0. The original cleanup ledgers and batch timings remain unchanged. The final ZIP includes this supplemental bookkeeping evidence. P-09c execution and handoff are complete. Full factual record: `docs/paper_rebuild/P09C_PROTOCOL_V2_FINAL.md`; source tables `<CANONICAL541_V2_ROOT>/13_AGGREGATE/v3/` and `/v2/`. Validated package: `~/c541_v2_handoff.zip`, SHA-256 `30e6e263922ed317db0bc6e1cabe4b38d576bd0ec501e1f8f7b45fffa94beefb`. Early whole-execution disk peaks remain UNAVAILABLE where absolute baselines were not recorded; scoped batch and continuation measurements are reported explicitly. No further scientific execution is authorized by this completion record.

Historical original-attempt stop (superseded only by the explicit bounded restart): `STOPPED_GATE_FAILURE`; the initial 256-run pilot was incomplete and its forecasts were UNAVAILABLE. Its 22 metadata failures and original freeze remain historical evidence. The later restart reused and archived the 33 native outputs, with their original scratch files removed only after batch-1 archive verification. The original stop record is `docs/paper_rebuild/CLEAN6_CANONICAL541_V2_PILOT_STOP.md`. The former 64/128 decision clause is void under the restart authorization.

Current next actions:

```text
1. CAD verification of antenna–IMU height difference and lever-arm z; retain the source-defined v3 transform until independently confirmed;
2. P-10 figure delivery complete: error-budget ladder, body-frame bias, sensitivity heatmap and calibrated three-sequence figures are in figures/v2; subsequent manuscript selection belongs to conversation E;
3. conversation D: reference-uncertainty record using timing, baseline, derived diagnostic velocity difference, consistency ratios, and frozen calibrated vrw/abstd/c;
4. remaining: BY2O gating sensitivity to IMU integration convention; any new execution requires its own bounded authorization;
5. post-hoc BY2O rejection/downweight timeline and Source-Aware Up cost by source, using frozen artifacts;
6. human review of the P-07 decision: 13 primary flips, 24 incomplete primary pair/version items, and 66 missing-evidence entries; retain capture consistency diagnostics and GINav UNAVAILABLE; no automatic full-matrix rerun;
7. registered, not executed: gyro z-axis scale input-side check using integrated gyro angle increments versus A1 angle increments on turn segments, with zero trace reads.
```

Stage 2 and the calibrated-chain execution are complete. Sources: `docs/paper_rebuild/CLEAN5_STAGE2_CLOSEOUT.md`, `docs/paper_rebuild/CLEAN5_CALIBRATED_CHAIN_RESULTS.md`, and `<CLEAN_ROOT>/stages/CLEAN5_CALIBRATED_SENSOR_MODEL/`. The original v1 protocol remains a preregistered record; its Outcome is unchanged. The manuscript uses the completed v2 protocol tables.

Do not restart Canonical-541, reselect horizontal literature algorithms, rerun GINav, reopen Hartley absolute-reference evaluation, or run corrected Classic-18 by default.

<!-- P13_PRE_CORRECTION_SECTION_18_END -->

<!-- T5BCR_CONTINUATION_BEGIN -->
T5bc-R explicit human continuation: see `docs/paper_rebuild/hext/T5BC_CONTINUATION_AUTHORIZATION.md`. Preserve the original d580c892 partial record, 62 native / 116 evaluator calls, two identity PASS receipts, old hard stop and partial-v1 ZIP. Only the fixed-prefix classifier and append-only controller continuation are changed; B3 no-heading epochs are `B3_NOT_APPLICABLE_NO_HEADING_EPOCHS`, excluded from algorithm failures and distributions, with missing D6 echo unavailable. Remaining exact budget 199 native / at most 398 evaluator calls; no retries. First continuation-freeze commit and push precede execution; second commit records results. Candidate/scalar binaries, providers and D1–D8 remain unchanged. Add read-only D30–D41 sidecar/HV lineage and D13/D14/D15/D27 B3-versus-frozen-F04 accept/attempt readouts. Original historical hard-stop statement above remains preserved.

T5bc-R completed: `PASS_T5BCR_COMPLETE`; code_freeze `e54df899db74ff8c11e37e09803c296965bfafba`. Added 199 native / 378 evaluator calls, original 62 / 116 preserved; total 261 native (2 identity + 259 matrix) / 494 evaluator, retries and identity reruns 0. Matrix: 247 COMPLETED, 8 ALGORITHM_FAILURE_DIVERGED, 3 scalar ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT, 1 B3_NOT_APPLICABLE_NO_HEADING_EPOCHS. Evaluator terminal slots: 494 COMPLETED + 22 skipped algorithm failures + 2 NOT_APPLICABLE. D6 echo: 257 PASS, 4 UNAVAILABLE_NOT_EMITTED. Archive pending/failures 0; native/controller trace opens 0, evaluator trace opens 494. Every version has 36 pilot and 305 subset rows; 8 current figure groups / 24 exports passed actual visual review and 56 machine checks. The late-import source-graph bookkeeping stop after 189 / 358 and its local receipt adapter remain explicit historical evidence; no frozen source bytes or scientific runtime functions changed. D30-D41 B3 sidecars all equal C00; inherited frozen HV changes are documented. Full factual record and 17 exact CSV companions: `docs/paper_rebuild/hext/T5BC_CONTINUATION_RESULTS.md`. v2 ZIP: 12141243345 bytes / 16329 members, SHA256 `ecc1144523748c7492792669fb6f0ed21ab09aac838f89754874f032adfe7590`; all-member SHA/CRC/size and ext4/G equality verified. Original hard stops and partial packages remain preserved; protocol v2.1 remains the sole manuscript chain.
<!-- T5BCR_CONTINUATION_END -->

## V3-01-R permanent storage discipline (2026-09-19)

The explicit V3-01-R authorization supersedes earlier V3 storage placement and
64-worker dispatch only. Scientific freeze remains
`7d43b9af26120ed5dde21f53e515386361072ba6`; no C++, parameter, case, seed, evaluator,
HV, or non-heading provider change is authorized. The existing C/D commits and
passed identity runs are reused. Protocol v2.1 evidence remains preserved.

- Runtime results, logs, ledgers, and figures reside only in
  `<CLEAN_ROOT>/stages/CLEAN8_PROTOCOL_V3`; packages are written only in
  `<HANDOFF_ROOT>`. Use the existing exFAT I/O retry wrapper, verified copies, and
  per-file SHA256. Do not rely on atomic rename/replacement on G:.
- The only WSL runtime staging location is `<PROTOCOL_V3_SCRATCH>` (the registered
  `CLEAN8_PROTOCOL_V3` directory), limited to 20 GB. No WSL archive is permitted.
  Completed task output must leave no per-case runtime files or ARCHIVE on WSL.
- Each batch solves, evaluates with v3 and v2, records NAV/STD and evaluator-input
  hashes, evaluation results and RUN_MANIFEST, copies retained evidence to G:,
  verifies every copied file, then releases its exact scratch inventory.
  Full NAV/STD/EVAL_NAV payloads are not retained; hashes and evaluation evidence
  remain. Trace access stays confined to evaluator children.
  Record each deletion intent and completion as fsynced rows in an append-only
  journal per archive slot; avoid separate tiny checkpoint files on exFAT.
- Before every batch require actual E: free space from `df --output=avail /mnt/e`
  at least 40 GB, G: at least 30 GB, and scratch at most 20 GB. Record and pause
  ten minutes on failure; three consecutive failed checks hard-stop. The larger
  virtual root-filesystem free-space figure cannot substitute for E:.
- Native concurrency and batch size are 22, with numerical libraries using one
  thread. Reconciled batches and four admitted identity natives are never rerun.
  Only explicitly registered interrupted/unverified whole batches may be rerun;
  any existing NAV/STD hash must match, otherwise hard-stop.
- Run the independent controller in `tmux v3`. All control logs, batch ledgers,
  `STATE.json`, `PROGRESS.txt`, and 60-second heartbeats live in
  `<CLEAN_ROOT>/stages/CLEAN8_PROTOCOL_V3/00_CONTROL`. Primary progress is core
  non-F01 5,410 native / 10,820 evaluator slots; separately expose core F01 541,
  extra sequence 22, A1/A2 495, and the unchanged total 6,468 / 12,936.
- On re-entry read STATE and verified batch ledgers first. Quarantined but
  unverified purge work resumes verification; verified work resumes exact-ledger
  deletion. Any P4 failure restores the quarantine and stops all later phases.
  Matrix recovery never repeats a verified archived batch.
- After matrix completion automatically run registered aggregate tables, figures,
  and machine QA, then write DONE and SUMMARY. Actual visual review, manuscript
  replacement text, final handoff and results commit follow in a later session.

Here GB means 1,000,000,000 bytes.

Before MATRIX, measure both allocated and apparent archive bytes for the eight
reconciled batches, separately for native and evaluator slots. Project the
remaining queue plus an explicit aggregate/control allowance; record this beside
actual G: available bytes in PROGRESS and the execution record. If projected
allocated occupancy exceeds 60% of available G:, retain error series for CORE
C00 and D01–D60 seed_00 (all eleven methods), every extra sequence and all A1/A2;
retain only evaluation metadata, seals and hashes for other CORE error series.
Preserve the registered figure cases, full BY2O segment windows, and C00 Truth
export. This storage rule never removes a result row or changes evaluation.
The separately authorized P′ exception applies only to protocol-v2 RETAINED_RUNS
eligible NAV/STD/strace/per-case logs at least 1 MB; C00 references, evaluation
results, records, figures and v2.1 remain protected. A zero-candidate report does
not authorize expanding the listed file types.

Machine-local paths resolve through ignored local configuration; these rules do
not authorize cleanup of any raw source, provider, protected root, or unlisted file.

## Handoff package rule (2026-09-22; latest explicit user decision)

Create a handoff package only when the human explicitly requests one. A stage
completion or prior default packaging step does not authorize a new package.
The current V3-01-R package is `SKIPPED_BY_USER`; a hash-bound explicit decision
receipt permits final acceptance without a ZIP.

When explicitly requested, handoff packages contain only records, hashes,
receipts, aggregate tables, figures, and documents. All per-case products are
excluded, including runtime/evaluation payloads, per-case manifests and results,
error series, logs, NAV/STD/EVAL_NAV, and per-case archives.
The package size target is at most 2 GB (2,000,000,000 bytes). This rule does not
authorize deleting any existing evidence or expanding cleanup scope.
HX-INV（2026-09-23，只读盘点）：外部方法 23 行（双天线 6、四足 1、松耦合 12、单天线 4、other 0；EXT06 = Luo 待实现），解算/评估调用 0/0，65 项封存表 sha256 两次比对一致；matched.py 部分导入事故与 5 项子代理规则偏差均非硬停，见 docs/paper_rebuild/hext/HX_INVENTORY.md §9；清单 docs/paper_rebuild/hext/HX_INVENTORY.csv。
HX-02（2026-09-24，五类外部方法三序列）：预注册 code_freeze `3e8a43b`，修正 `88594ef`（Hartley 两支各自对齐、空闲等待上限 600 s）；8 方法 × BY2 C00 / BY2H CONTRACT_START / BY2O FILE_START 共 24 次原生运行，参考评估 21 次（航向 15、冻结评估器 2、相对位姿 4）＋无参考覆盖 3 次，LegSA 解算/评估 0/0，控制器与原生进程读参考轨迹 0；失败照实记录（GINav BY2/BY2O D8 速度越界、Hartley BY2H 两支静止陀螺门 ABNORMAL_EXIT、EXT04 三序列有效率 0），无数值门槛；65 项封存表 sha256 两次比对一致，方法本体 423 项前后一致；结果 docs/paper_rebuild/hext/HX02/HX02_RESULTS.md 与 EXTERNAL_FIVE_CATEGORY_TABLE.csv。
