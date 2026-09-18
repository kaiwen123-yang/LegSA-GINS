# Conversation handoff (paper-writing phase)

Every conversation (Claude, ChatGPT, Codex) reads `AGENTS.md` first, then this file,
and appends its own decisions under "Conversation log" before it ends. Nothing in this
file overrides `AGENTS.md`; it only records paper-phase decisions and task ownership.

## 1. Target and page budget

- Target journal: IEEE Transactions on Instrumentation and Measurement (TIM), regular
  paper, free limit 8 pages (IEEE double-column). GPS Solutions is a fallback only.
- Main-text figure budget: about 7 figures + 3-4 tables. Everything else goes to the
  supplementary text file.
- TIM "Important Note" obligations: state the I&M contribution (measurement model,
  uncertainty budget, calibration) in abstract/introduction; compare against I&M
  literature (the three raw-layer comparators are TIM papers).

## 2. Method identities for the manuscript

Protocol v2.1 is the sole manuscript chain, frozen by C-CLOSE on 2026-09-15 (AGENTS §18). Main execution and archival closure: 5880 new native terminals, 11760 evaluator terminal slots, 5880 verified archives, pending 0. Downstream diagnostics: 21 native, 42 evaluator terminal slots, 21 verified archives, pending 0. Formal F01 reuse is 588 native; BY2/C00 and the three-sequence BY2 entries share the same output identities.

The manuscript proposed method is F04 (AB1111); primary evaluator v3, parallel evaluator v2. Protocol v1 remains the original preregistered record and protocol v2 remains pre-correction history. The v1 A04 decision and its existing Outcome are unchanged. Current factual authority: [P13_FINAL_REPORT.md](P13_FINAL_REPORT.md); current finalized sources are under `<CLEAN_ROOT>/stages/CLEAN6_SENSOR_MODEL_V21/20_FINALIZE/`.

| Manuscript label | Registry id | Role |
|---|---|---|
| Single | `F01` = `single_antenna_EKF` | baseline (position + receiver velocity, no yaw) |
| Dual-basic | `F02` = `basic_dual_yaw_EKF` | baseline (dual yaw only; v2.1 base yaw std 2.933193 deg, with preregistered injection multipliers retained) |
| Backbone | `F03` = `A02` = `AB0000` | proposed method without RD/RP/HV/SA; ablation row only, never a "strong baseline" |
| Core / no-SA | `A04` = `AB1011` | v1 pre-registered decision, retained as ablation |
| Full / Proposed | `F04` = `A01` = `AB1111` | manuscript proposed method under protocol v2.1 |

The graduation-design algorithm (`final_v23`, the backbone) has never been published;
the manuscript still adds one sentence declaring reuse of graduation-design material,
as TIM requests for thesis material.

Historical v1 proposed-method identity: `A04`, decided 2026-09-08 by
`docs/paper_rebuild/A04_F04_ROLE_DECISION_RULE.md` (rule commit: `b9f9a44f288966c95961f7a15564b2b57bf07b65`;
evidence commit: `09caf1e7e6151f18cc25dafad4a7ef5704ae62d2`).

The 2026-09-13 F04 role decision is recorded in [PROTOCOL_V2_METHOD_STATEMENT.md](PROTOCOL_V2_METHOD_STATEMENT.md); numerical authority is now the completed protocol v2.1 [P13_FINAL_REPORT.md](P13_FINAL_REPORT.md). Ablation ladder: F01→F02→F03→A04→F04. No new A04/F04 decision is made.

## 3. Comparison structure

Protocol v2.1 comparison and packaging are terminal: `PASS_FINALIZED_V21_HANDOFF`. Per evaluator, the formal core has 5951 unique / 7033 logical rows, the separate addendum has 495 / 585, and the three-sequence table has 33 / 39, including the shared BY2/C00 alias. Sources: `20_FINALIZE/13_AGGREGATE_SEQUENCES/{v3,v2}/` and `20_FINALIZE/P13_MACHINE_REPORT/` under `<CLEAN_ROOT>/stages/CLEAN6_SENSOR_MODEL_V21/`.

The 5880 new native terminals include 5703 `COMPLETED` and 177 `ALGORITHM_FAILURE_ALL_YAW_REJECTED`; associated unavailable evaluator slots remain `NOT_RUN_ALGORITHM_FAILURE`. Finite and failure-aware denominators remain distinct. All frozen H7–H11 classifications, including `INCOMPLETE`, remain as recorded; terminal execution does not imply that every hypothesis is supported or available. Full record: [P13_FINAL_REPORT.md](P13_FINAL_REPORT.md).

- Comparison tables/figures: F01, F02, proposed F04, plus A04 as no-SA ablation. Horizontal LegSA rows use v2.1-chain C00 F04/A04 and evaluator v3; external methods without compatible IMU-point NAV remain explicitly `Not comparable` (不可比). EXT06 may only add comparison rows in its independent conversation; it does not reopen the frozen main chain.
- Ablation table/figure: F01→F02→F03→A04→F04, with module-isolating A03/A05/A06/A07/A08/A09 rows. Frozen 541-core and separately pre-registered A1/A2 tables remain separate.
- Delta convention everywhere: candidate - reference, negative is better; always report
  mean, median, and case win rate together.
- Reference label inside figures follows AGENTS section 13 (`Truth`); prose states:
  the fused navigation solution output directly by the commercial low-cost dual-antenna GNSS/INS receiver (Fixposition Vision-RTK 2); the estimator under test never reads it (file-access audit).

## 4. Stage terminal states and naming

Conversation C stages are closed. Current delivery is protocol v2.1: 28 figures / 84 PNG/PDF/SVG exports, visual review complete; MFIG21 retains its original v2 artifact. The earlier P-10 delivery remains historical evidence: 29 v2 composites / 87 exports, 29/29 visual PASS, with byte-identical v1 originals/copies retained.

Historical failures, technical stops, superseded attempts and hypothesis availability retain their original classifications. The status column below describes stage closure, without changing those underlying results.

| Purpose | Stage id / dataset id | Terminal state / record |
|---|---|---|
| Same-day poor-heading run | `BY2H`, `CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE` | `COMPLETE`; evaluated and sealed, [CLEAN5_OFFLINE_EVALUATION_RECORD.md](CLEAN5_OFFLINE_EVALUATION_RECORD.md) |
| Same-day single-antenna occlusion run | `BY2O`, `CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE` | `COMPLETE`; evaluated and sealed, same record |
| C00 input-parity experiment / stage 2 | `CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF` | `COMPLETE`; [CLEAN5_STAGE2_CLOSEOUT.md](CLEAN5_STAGE2_CLOSEOUT.md) |
| Calibrated-chain execution | `CLEAN5_CALIBRATED_SENSOR_MODEL` | `COMPLETE`; 15 native / 30 evaluations, [CLEAN5_CALIBRATED_CHAIN_RESULTS.md](CLEAN5_CALIBRATED_CHAIN_RESULTS.md) |
| P-07 degradation subset | `CLEAN5_DEGSUBSET_BY2` | `COMPLETE`; original failures, flips and incomplete evidence retained, [CLEAN5_DEGRADATION_SUBSET_RESULTS.md](CLEAN5_DEGRADATION_SUBSET_RESULTS.md) |
| P-09c protocol v2 core | `CLEAN6_BY2_CANONICAL_541_PROTOCOL_V2` | `COMPLETE`; historical v2 execution/aggregate/handoff, [P09C_PROTOCOL_V2_FINAL.md](P09C_PROTOCOL_V2_FINAL.md) |
| P-09d A1/A2 | `CLEAN6_ADDENDUM_FAMILIES_A1_A2`; D61=27 cases, D62=18 cases, 495 unique runs | `PASS_ADDENDUM_FAMILIES_A1_A2_COMPLETE`; historical v2, [ADDENDUM_FAMILIES_A1_A2_RESULTS.md](ADDENDUM_FAMILIES_A1_A2_RESULTS.md) |
| P-10 publication figures | `CLEAN6_PUBLICATION_FIGURES/figures/v2`; v1 archive at `figures/v1_prereg` | `COMPLETE`; historical v2, [PROTOCOL_V2_FIGURE_DELIVERY.md](PROTOCOL_V2_FIGURE_DELIVERY.md) |
| P-13 protocol v2.1 main chain, downstream diagnostics, aggregation and data handoff | `CLEAN6_SENSOR_MODEL_V21`, including `DOWNSTREAM/` and `20_FINALIZE/` | `PASS_FINALIZED_V21_HANDOFF`; main/downstream archive pending 0, [P13_FINAL_REPORT.md](P13_FINAL_REPORT.md) |
| P-13 publication figures and figure handoff | `CLEAN6_PUBLICATION_FIGURES/figures/v21` | `COMPLETE`; 28 figures / 84 exports, [P13_FINAL_REPORT.md](P13_FINAL_REPORT.md#figure-delivery) |

The frozen BY2H/BY2O sequence contracts and input-defined occlusion windows remain in force. AGENTS §18 governs all subsequent work: no provider, parameter or solver changes and no reruns, except numerical errors detected by the byte-for-byte identity gate.

## 5. Task ownership

| Conversation | Owner | Scope | Status |
|---|---|---|---|
| A | Claude (matrix-figure conversation) | derived tables (A04 vs F03 / F02, F04 vs F02, bootstrap CI, stratified Wilcoxon, bias/random decomposition), publication plotting common layer, Canonical-541 figures, captions, this file | P-10 complete: 29 v2 composites and visual QA passed; v1 bytes retained |
| B | new conversation | horizontal publication figures FIG02/FIG03 (FIG04 supplementary), reuses A's common layer | P-10 FIG01–FIG04 rendered and visually verified |
| C | Codex / execution conversation | BY2H/BY2O, stage 2, calibration, protocol v2/v2.1 execution, diagnostics and sealed data/figure delivery | `COMPLETE` — C-CLOSE 2026-09-15; shutdown verification in §6 |
| D | subsequent conversation | uncertainty inputs listed in §7; preserve frozen inputs and distinguish manufacturer specification from derived diagnostics | pending |
| E | subsequent conversation | TIM manuscript assembly; proposed F04 under the sole protocol v2.1 chain | pending |
| EXT06 | independent conversation | Luo et al., single-antenna InEKF + leg odometry, no radar; baseline comparison rows only | pending; no execution or admission claimed |

Conversation C has no remaining scientific or packaging work. The only remaining work is D, E and EXT06 as listed in §7. Earlier submission-repository/release planning (conversation F) is outside this active list.

## 6. Data handoff locations

### Current protocol v2.1 handoff and C-CLOSE verification

`<HANDOFF_ROOT>` and `<CLEAN_ROOT>` resolve through `handoff_root` and `clean_root` in ignored local `configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml`; `<PUBLICATION_ROOT> = <CLEAN_ROOT>/stages/CLEAN6_PUBLICATION_FIGURES`. The two current packages are:

| Package | Path | SHA-256 |
|---|---|---|
| Protocol v2.1 data | `<HANDOFF_ROOT>/c541_v21_handoff.zip` | `98a77b4601b897956a6d87f5bfa92e008b584add35e48e2b22a9088ddec07585` |
| Protocol v2.1 figures | `<HANDOFF_ROOT>/figures_v21_handoff.zip` | `20495ab65d1b7ae41a83de52aa34e80051b7154b45db4d5de63478a064e0c088` |

Finalization record: `<CLEAN_ROOT>/stages/CLEAN6_SENSOR_MODEL_V21/20_FINALIZE/FINALIZE_COMPLETE.json`; SHA-256 `47e5a735c03fc1b9b6d04b6c2b64f21eb7bad3d1b23e3f45601efdb9ae351e16`; status `PASS_FINALIZED_V21_HANDOFF`. Expected identities above come from [P13_FINAL_REPORT.md](P13_FINAL_REPORT.md#pinned-sources).

Shutdown verification on 2026-09-15, before the documentation edit:

| Check | Observed result |
|---|---|
| Starting HEAD, upstream and live GitHub branch | `PASS`: all `cff69bf5f1c461bae3036c11565440a73fd1aa91`, branch `stage/clean3-math-repair` |
| Full `git status` clean | `FAIL`: tracked files clean, two pre-existing untracked scripts listed below; preserved without cleanup or staging |
| Both ZIP SHA-256 values vs P13 | `PASS`: data 1178359812 bytes; figures 24284506 bytes; both exact hashes match |
| Finalization file exists and SHA-256 matches P13 | `PASS`: 3158 bytes; exact hash and terminal status verified |
| v2.1 scratch file count | `PASS`: 0 files; existing directory resolved by local key `sensor_model_v21_scratch` |
| Residual project systemd services | None found in user/system service units or unit files; no project runtime process found |
| C-CLOSE scientific execution | Provider / solver / evaluator / diagnostic / aggregate / plotting / packaging calls: 0; reference-trace payload reads: 0 |

Preserved untracked scripts: `scripts/paper_rebuild/LC02_GINAV2021_RESUME_20260826.py` and `scripts/paper_rebuild/clean6_finalize_aggregate_io.local.py`. The full-worktree cleanliness exception does not alter the sealed P13 artifacts or the completed scientific stages.

### Historical protocol v1/v2 handoff locations

P-10 figure delivery is complete: 29 composites (8 reissued + 21 new; 2 supplementary as an overlapping role), 87 PNG/PDF/SVG exports, 29/29 visual PASS. Figure root `<PUBLICATION_ROOT>/figures/v2/`; index `FIGURE_INDEX.md` has GPS Solutions and TIM section columns. ZIP `<HANDOFF_ROOT>/figures_v2_handoff.zip`, SHA-256 `d304001f0f77818cef0604b3b790cc414649c06892d1a7963b1c0d7869c52a60`, 29063129 bytes. Full record: `docs/paper_rebuild/PROTOCOL_V2_FIGURE_DELIVERY.md`. v1 original/copy bytes remain unchanged; no new scientific execution.

P-09d combined data handoff: `<HANDOFF_ROOT>/c541_v2_handoff_v3.zip` (`handoff_root` in ignored local config), SHA-256 `79e75f7d867a4930dc80c0f906173b48aab1bec6a5caac44b63bae993a848dd3`, 601520239 bytes, 9712 ZIP members; full CRC/member-hash validation PASS, 608 base members preserved. Delivery record: `docs/paper_rebuild/clean6/ADDENDUM_HANDOFF_V3.md`. All new handoff packages are on the project G: handoff root.

P-09d A1/A2 final status: `PASS_ADDENDUM_FAMILIES_A1_A2_COMPLETE`; A1 27 cases, A2 18 cases, 11 configurations, 495 native COMPLETED and v3/v2 each 495 COMPLETED. Failures, repeats, core calls and archive pending are 0. Source: `<CLEAN_ROOT>/stages/CLEAN6_ADDENDUM_FAMILIES_A1_A2/13_AGGREGATE_ADDENDUM/{v3,v2}`; full report: `ADDENDUM_FAMILIES_A1_A2_RESULTS.md`. H1/H2/H3 both versions: `PARTIALLY_SUPPORTED` / `SUPPORTED` / `OBSERVED_SOME_SEED_HARM`. Core tables stay separate and unchanged.

All new handoff packages go to `<HANDOFF_ROOT>` under the project G: root, never the WSL home directory. Existing earlier ZIPs are at `<CLEAN_ROOT>/stages/CLEAN6_PUBLICATION_FIGURES/`; historical home-path records below are retained as history.

- P-09c completed under the 2026-09-12 human decision. P-09c protocol v2 full execution, both frozen aggregates, v1/v2 comparison and validated handoff are complete: 5973 native terminals (5869 COMPLETED; 104 ALGORITHM_FAILURE_ALL_YAW_REJECTED), 11946 v3/v2 evaluator terminal records, archive pending 0. Scientific code `737a0fb5a4a5418500824855b89b0d25af69824a`; archive I/O code `ea478eea88aaf9739823dfc152fa108dd17f8d0c`. Original native reuse=33; native/evaluator repeat calls=0. Sequence/C00 gate PASS 182/182 (P-06 105/105; P-07 CAL C00 77/77). The original role-validation stop, batch-8 archive interruption and missing historical evaluation seal remain preserved as historical records. RUN_01963 received the explicitly accepted current post-hoc seal; historical_full_file_seal_available=false. Its completed archive is identified by resolved rows; the original partial archive is retained.

- Current I/O input acceptance: `ACCEPTED_AUTHORIZED_POSTHOC_SEAL`. Batches 1–7 ledger audit PASS; batch-8 existing pins matched, and RUN_01963 current seal covers all 25 v3/v2 files with its historical gap retained. Full factual record: `docs/paper_rebuild/P09C_PROTOCOL_V2_FINAL.md`; source tables `<CANONICAL541_V2_ROOT>/13_AGGREGATE/v3/` and `/v2/`.

- Historical interrupted restart and pilot evidence: `CLEAN6_CANONICAL541_V2_RESTART_STOP.md`, `CLEAN6_CANONICAL541_V2_RESTART_PILOT.md`, and `CLEAN6_CANONICAL541_V2_RESTART_RESOURCE_COVERAGE.md`. The accepted recovery completed batch-8 cleanup and all later batches. Original native reuse=33, repeat calls=0; full-matrix outputs now reside in the registered retained and aggregate roots.

- Original protocol-v2 stop: `<CANONICAL541_V2_ROOT>/99_STOP_REPORT/`, terminal `STOPPED_GATE_FAILURE` as of 2026-09-11. Authorized restart reused the original outputs; batch-1 archives now reside in `RETAINED_RUNS/`, and its scratch files were ledger-cleaned after verification.
- P-09c record: `docs/paper_rebuild/CLEAN6_CANONICAL541_V2_PILOT_STOP.md`; family/config counters and attempted-run timings under `docs/paper_rebuild/clean6/P09C_*.csv`.
- Final scratch release: the supplemental batch-14 exact ledger removed 198 derived preparation files (66,327,303 bytes); remaining scratch file count is 0. The original cleanup ledgers and batch timings remain unchanged. The final ZIP includes this supplemental bookkeeping evidence.

- `scripts/paper_rebuild/c541_pack_v3.py` completed and validated `~/c541_v2_handoff.zip`; SHA-256 `30e6e263922ed317db0bc6e1cabe4b38d576bd0ec501e1f8f7b45fffa94beefb`. Identity probes, field whitelist, C00 thinned NAV, error-series thinning and recovery provenance passed validation.

- Canonical-541 authoritative attempt: `<CANONICAL541_ATTEMPT>` (see AGENTS section 3).

  - `<CANONICAL541_ATTEMPT>/08_FULL_ALGORITHM_RUNS/`: bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only).
  - `<CANONICAL541_ATTEMPT>/10_INTERNAL_ABLATION_RUNS/`: bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only).
  - `<CANONICAL541_ATTEMPT>/12_OFFLINE_EVALUATION/`: bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only).

- Packed subset for conversation A: `~/c541_handoff.zip` produced by `c541_pack_v2.py`
  (aggregates, whitelisted evaluation columns, decimated representative error series,
  C00 NAV files, identity probe). Decimated series are display-only; every metric comes
  from the frozen aggregate tables.
- Horizontal synthesis tables for conversation B: `<CLEAN4 root>/13_HORIZONTAL_CROSS_LAYER_SYNTHESIS/`.

- BY2H/BY2O evaluated stages: `<CLEAN5_BY2H_ROOT>` / `<CLEAN5_BY2O_ROOT>` (AGENTS section 3).
  Each stage provides `08_AGGREGATE/`, `07_OFFLINE_EVALUATION/PER_RUN/`,
  `02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json`, and `01_SEQUENCE_CONTRACT/`.
  The V2 `EVENT_WINDOW_V2.json` is the contract-pinned
  `01_SEQUENCE_CONTRACT/C04B_CONTINUATION_2_ba7d380bb11d/EVENT_WINDOW_V2.json`
  (`window_contract.event_report_relative_path`, checked by `event_window_report_sha256`).
  `01_SEQUENCE_CONTRACT/OCCLUSION_WINDOW.json` applies to BY2O; BY2H is not applicable.

  - `<CLEAN5_BY2H_ROOT>`: bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only: `04_SOLVER_RUNS/`, `04_SOLVER_RUNS_V2/`, `07_OFFLINE_EVALUATION/`).
  - `<CLEAN5_BY2O_ROOT>`: bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only: `04_SOLVER_RUNS/`, `04_SOLVER_RUNS_V2/`, `07_OFFLINE_EVALUATION/`).

- Decision evidence: `<CLEAN_ROOT>/stages/CLEAN5_DECISION/`.
- Three-sequence handoff: `~/clean5_handoff.zip`, produced by
  `scripts/paper_rebuild/clean5_pack_v1.py`; 10 Hz series are display-only, and metrics
  remain the frozen aggregate values. Reference trace is external via `--trace-path`.

- Stage 2 parity root (`<CLEAN5_PARITY_ROOT>`): `<CLEAN_ROOT>/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/`; P02 `08_AGGREGATE/`, P03 `10_IMU_PROCESSING/08_AGGREGATE/`, vertical diagnosis `11_VERTICAL_DIAGNOSIS/`, three-sequence ladder `12_PARITY_GENERALIZATION/08_AGGREGATE/`, and P05 grid `13_NOISE_MODEL_SENSITIVITY/08_AGGREGATE/`.

  - `<CLEAN5_PARITY_ROOT>/03_PARITY_RUNS/`: bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only).
  - `<CLEAN5_PARITY_ROOT>/07_OFFLINE_EVALUATION/`: bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only).
  - `<CLEAN5_PARITY_ROOT>/10_IMU_PROCESSING/`: bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only).
  - `<CLEAN5_PARITY_ROOT>/12_PARITY_GENERALIZATION/`: bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only).
  - `<CLEAN5_PARITY_ROOT>/13_NOISE_MODEL_SENSITIVITY/`: bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only).

- Calibrated root (`<CLEAN5_CALIBRATED_ROOT>`): `<CLEAN_ROOT>/stages/CLEAN5_CALIBRATED_SENSOR_MODEL/`; `00_CALIBRATION/` holds the one-time BY2 fit and original plus supplementary audit evidence; `08_AGGREGATE/` and its `v3/` contain all five profiles on three sequences, pairwise, consistency and BODY_FRAME_BIAS tables. `CALIBRATED_CHAIN_ROBUSTNESS_CHECK.json/.csv` resides in `08_AGGREGATE/`.
- Stage 2 closeout: `CLEAN5_STAGE2_CLOSEOUT.md`; calibrated run record: `CLEAN5_CALIBRATED_CHAIN_RESULTS.md`. Calibrated values are marked `NOT_THE_PREREGISTERED_COMPARISON_PROTOCOL`; the original main-chain anchors and Outcome are retained.
- Extended handoff: `~/clean5_handoff_v2.zip`, produced by `scripts/paper_rebuild/clean5_pack_v2.py`. It inherits every v1 member byte-for-byte and adds frozen stage 2/calibrated tables, both evaluation versions and body-frame biases. Raw reference trace is excluded; the explicitly pinned trace-difference diagnostic table is `DERIVED_DIAGNOSTIC_ONLY`.

- P-07 corrected-chain degradation subset root (`<CLEAN5_P07_ROOT>`): `<CLEAN_ROOT>/stages/CLEAN5_DEGSUBSET_BY2/`; retained results are in `08_AGGREGATE/`, including `08_AGGREGATE/DEGRADATION_SUBSET_DECISION.json`. Record: `docs/paper_rebuild/CLEAN5_DEGRADATION_SUBSET_RESULTS.md`.

  - `<CLEAN5_P07_ROOT>/03_RUNS/`: bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only).
  - `<CLEAN5_P07_ROOT>/07_EVALUATION/`: bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only).

- Earlier Canonical exact-file scope (`<CANONICAL_STAGE>` = `<CLEAN_ROOT>/stages/CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX/`):

  - `<CANONICAL_STAGE>/.attempt_20260808T192851P0800/01_COMPACT_READINESS_RUN/`: bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only).
  - `<CANONICAL_STAGE>/.attempt_20260808T192851P0800/02_MATRIX_SPEC_LOCK/INTERNAL_ABLATION_QUEUE_DRAFT.csv`: bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only).
  - `<CANONICAL_STAGE>/.attempt_20260808T195407P0800/01_COMPACT_READINESS_RUN/`: bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only).
  - `<CANONICAL_STAGE>/.attempt_20260808T195407P0800/02_MATRIX_SPEC_LOCK/INTERNAL_ABLATION_QUEUE_DRAFT.csv`: bulk purged 2026-09-11; records at docs/paper_rebuild/purge/DELETION_LEDGER_20260911T070041Z.json.gz (listed bulk only).

- P-09ab policy-v2 completion (2026-09-11, audit `<CLEAN_ROOT>/storage_purge/20260911T070041Z`): C1/C2/C3/C4/C5/D PASS; 73,039 listed files / 530,120,461,090 logical bytes quarantined and purged. Final ledger SHA-256: `9e28e07eea72f9de8b3ebc2ba033139d2f694c9934357dab2a40a8e60ad4f814`. Completion record: `docs/paper_rebuild/purge/STORAGE_PURGE_20260911T070041Z.md`.

- P-09ab storage inventory (2026-09-11): C1/C2/C3 PASS, C4 FAIL (`renameat2(RENAME_NOREPLACE)` returned EINVAL), C5/D NOT_EXECUTED. Planned 57,233 files / 439,508,000,426 logical bytes; moved/purged/released by purge 0/0/0. The empty quarantine tree is retained. No root was bulk purged. Planned ledger records at `docs/paper_rebuild/purge/DELETION_LEDGER_20260911T040000Z.json.gz`; terminal and inventory record: `docs/paper_rebuild/purge/STORAGE_PURGE_20260911T040000Z.md`. Main-chain roots and Outcome remain unchanged.

- P-09ab DrvFs continuation (2026-09-11, audit `20260911T062436Z`): `STOPPED_PREFLIGHT_IO_PROBE_FAIL_NO_CANDIDATE_MOVE_OR_PURGE`. The audit-only zero-byte ordinary rename completed, then the implementation-added full-metadata equality assertion failed; source-absent/destination-present/size-zero postconditions hold, and the differing metadata field is UNAVAILABLE. Dispatch stopped before C1/C2/C3, candidate quarantine, C5 or D; candidate moved/purged files and bytes are 0. No root was bulk purged and no retry was made. Planned ledger records at `docs/paper_rebuild/purge/DELETION_LEDGER_20260911T062436Z.json.gz`; terminal, C5 NOT_EXECUTED rows and UNKNOWN top 20 at `docs/paper_rebuild/purge/STORAGE_PURGE_20260911T062436Z.md`. The prior failed audit and empty quarantine are retained.

## 7. Open items

- [ ] D（不确定度）：使用冻结的 v2.1 证据及已记录输入，区分厂家规格、派生诊断和未传输的 v3 位置 STD；保留全部 availability/INCOMPLETE 边界。输入包括时标约 0.205 s、BY2 半基线约 0.178 m、PVT−trace 差分垂直速度差标准差约 0.043 m/s（`DERIVED_DIAGNOSTIC_ONLY`）、一致性比，以及已有 Vision-RTK 2 名义 0.4° @ 1 m 规格和显式 0.35 m 基线换算假设。
- [ ] E（组稿，TIM 版）：主方法 F04，论文唯一链 v2.1；使用 §6 两个封存包，纳入有利/不利结果、有限与失败分母、参考不确定度及限制；新发现只写为限制或后续工作。
- [ ] EXT06 基线（独立对话）：Luo et al.，单天线 InEKF + leg odometry、无 radar；独立完成来源/复现/准入，仅新增对比行。此处不宣称已执行或已准入，不修改或重跑冻结主链。

对话 D 的历史标定来源保留：BY2 冻结 s=1.0308398903907543；vrw=[9.478382094779873, 9.784198200134004, 7.6321402201126745] (m/s)/√h；abstd=[4817.482008954474, 8259.572423450163, 2257.241538343225] mGal；拟合 c=[0.010830809489394968, 0.013550612232080246, 0.020536668097236248] (m/s)²。原始数值、三轴窗数与来源见 `<CLEAN5_CALIBRATED_ROOT>/08_AGGREGATE/FROZEN_SENSOR_MODEL.csv` 和 `00_CALIBRATION/LAG_VARIANCE_FIT.csv`；各 run 的高度/北/东/yaw 一致性比见标定链 UNIQUE 表。历史标定诊断不能替换 v2.1 冻结结果。

原待办中的 BY2O 门控拒绝/降权时间线、SA 的 Up 代价按源分解、天线–IMU 高度差/杆臂 z 的 CAD 证据缺口及 IMU 积分约定敏感性，转为 D/E 的限制或后续工作素材，不再作为对话 C 的执行任务，也不标记为已完成。V2 与 V2is 同时改变处理约定和加速度计标度，不能作为独立积分因果项。所有后续工作遵守 AGENTS §18 冻结规则。

## Conversation log

- 2026-09-04 (A): file created; decisions in sections 1-4 agreed with the human.
- 2026-09-05 (A, derived analysis): identity gate PASS (5951/7033/541/11; C00 yaw values match AGENTS section 7 to 4e-7). Case-level join reproduces section 7A.2 A04-vs-Strong values exactly and matches frozen PAIRWISE_SUMMARY for full_vs_strong, full_vs_no_SA, strong_vs_basic. Module: src/legsa_gins/paper_rebuild/publication/derived_tables.py; CLI: scripts/paper_rebuild/build_canonical541_derived_tables.py; tables under <CLEAN_ROOT>/stages/CLEAN6_PUBLICATION_FIGURES/01_CANONICAL541/00_DERIVED_TABLES/.
  New pairwise (candidate - reference, 541 cases, bootstrap 95% CI, Wilcoxon p<1e-7 for all):
  A04-Basic: H -0.131 m [-0.200,-0.075] win 95.6%; yaw mean +0.80 deg [+0.05,+1.65], median -0.40, win 87.6%, P95 +0.70.
  F04-Basic: H -0.123 m [-0.177,-0.078] win 89.6%; Up +0.025 m win 5.4%; yaw mean -0.37 [-1.37,+0.64], median -0.38, win 91.5%, P95 -1.13.
  A04-Single: H -0.010 m win 88.7%; yaw -6.91 deg win 97.8%.
  A04-Strong yaw mean CI [-0.08,+0.20] includes zero: report median/win rate only.
  Yaw-mean reversal versus Basic is confined to D14, D15, D27, D59, D60 (gross position faults): Basic keeps yaw anchored because it never gates; scheme-C rejects valid yaw after position/velocity contamination; SA partially repairs (yaw>30 deg cases: Basic 19, Strong 29, A04 30, Full 20). Must be stated in the manuscript.
  Position decomposition: C00 N/E/U statistics identical across all five internal configurations (north -0.035/sd 0.236, east +0.045/sd 0.255, up -0.413/sd 0.706 m) -> position error is input-bound, not estimator-bound. Body-frame mean of the horizontal error = forward about -0.22 m, right about +0.15 m (0.265 m, 55-57% of horizontal MSE, identical for Single through Full): fixed POI/IMU offset signature, to be source-proven from Fixposition POI configuration or mount CAD (never fitted from RMSE). Up: constant -0.413 m (25% of MSE) plus slow wander (LF rms 0.67 m, HF 0.12 m) = input height solution wander; check gnss1-status fix type and pos_acc_v.
  Consequences: (1) internal-method position curves coincide in C00, plot once with "input-bound" caption; (2) POI physical transform is a measurement-point definition to be added as a new evaluator contract version if source-proven; (3) LC01 gap is input-structure dominated (1 Hz status vs 5 Hz two-receiver HPPOSECEF); A04@5Hz parity experiment promoted to required.
  Open items added: [ ] Fixposition POI offset source-proof (conversation C); [ ] gnss1-status fix-type / pos_acc_v audit (C).
- 2026-09-07 (A, plotting layer): added src/legsa_gins/paper_rebuild/publication/{style,qa,loaders,canonical541_figures}.py, configs/paper_rebuild/publication/{canonical541_display_names.yaml,CANONICAL541_PUBLICATION_FIGURE_REGISTRY.csv}, scripts/paper_rebuild/render_canonical541_publication_figures.py, tests/paper_rebuild/test_canonical541_publication_figures.py. The common layer (174 mm double column, panel labels only, units on axes, PNG >= 4096 px + PDF + SVG, forbidden-text / panel-label / unit / blank / perceptual-hash-duplicate QA) is shared with conversation B. BY2 draft figures MFIG01-MFIG06 and SFIG01 rendered under <CLEAN_ROOT>/stages/CLEAN6_PUBLICATION_FIGURES/01_CANONICAL541/01_FIGURES_BY2_DRAFT with QA all-pass; final renders wait for BY2H/BY2O and the A04/F04 decision. Full-rate body-frame offset confirmed on 56 642 samples: forward -0.20..-0.22 m, right +0.15..+0.17 m, magnitude 0.261-0.265 m, 54-56% of horizontal MSE for all five configurations.
  Figure-level notes for the manuscript: MFIG03(c) shows yaw Δmean/Core mean -18%, Δmedian/Core median +1%, win rate 13% side by side (tail-driven); MFIG06(a) shows Source-Aware changing a weight on about 85% of evaluations already in the clean case (always-on evidence); MFIG05 D27 yaw jumps of ±180° are wrap-safe residuals, not artefacts.
- 2026-09-07 (A, figures v2.2): IEEE/TIM figure compliance applied to the Canonical-541 set: Okabe-Ito colour-blind-safe palette with luminance-separated Backbone/Core/Full, one line style per method, hatched secondary bars, 7 pt minimum text, MFIG02 full-width per-type panels, bootstrap 95% CI whiskers in MFIG03(c), MFIG05 7.2 in tall with descriptive case labels and type ids resolving to Table S1 (STAB01_degradation_types.csv/.md generated from the case manifest). New MFIG00: Core estimate versus the hash-locked BY2 reference trace (trace passed by --trace-path only, never committed), using the evaluator's frozen time origin (base_time_unix_seconds from final_v23_parity_contract.yaml) and yaw formula wrap360(90 deg - yaw_ENU); a consistency gate requires estimate-minus-frozen-error to reproduce the trace at the matched epochs (BY2 subset: 0.2 cm horizontal, 0.0 cm vertical, 0.00 deg yaw). The minimal trace carries no fix status or covariance: the reference uncertainty statement TIM expects needs the full trace/odometry fields or manufacturer specification (conversation D). Main-text candidates are now MFIG00-MFIG06 (seven); with FIG02/FIG03 from conversation B this exceeds the eight-page budget, so MFIG06 is the first candidate for the supplementary file.
- 2026-09-07 (A, v2.3/v2.4): MFIG00 caption reads C00 values; long axis labels split into two lines to clear panel letters; D12 label shortened. BY2 draft figure set frozen at commit 1bf64e5; conversation A idle until BY2H/BY2O and parity results arrive.
- 2026-09-07 (C): C-01 complete; RAW_FILE_HASH_LOCK_CLEAN5.csv has 44 rows, sha256 faa31580c7fff73b52fcf6d27c97cfdd9187e67a55968a2ab42e6737b0eabb67; BY2 raw lock unchanged; zero solver processes and zero trace-content reads. The kick detector has no BY2H candidate, so rule A is unused; B′ (10, 9) reproduces frozen BY2 66/340. The frozen BY2 initial state differs from the first input epochs by 0.32/0.21/0.06 m and 0.37°; it remains an archived static contract.
- 2026-09-07 (C): C-02 sequence contracts frozen for BY2H/BY2O; BY2O input-side evidence is GNSS2 fix_type 8→7 for 57 epochs, not a stream outage. The primary window 3369.943066596985..3411.951585292816 s (43 epochs) is pre-registered; secondary run 3495.939144849777..3508.9415624141693 s (14 epochs). B′ uses the C-01 three-stream common coverage with the unique integer margins (10, 9) reproducing BY2 66/340; initialization uses the first GNSS1 status position and A1 NED yaw at or after t_start with BY2-frozen parameter blocks. The A04/F04 decision rule is unchanged.
- 2026-09-08 (C): C-03 completed at provider code freeze 727e96da2a585fa1fddca0a6f2efacea5da35cd9: BY2 four byte-hash gates and Raw Doppler 18-column semantic gate PASS; BY2H/BY2O provider freezes and five-profile BY2/BY2H/BY2O frozen_parameter_hash gates PASS. Retained detached execution snapshot has empty status including untracked files; original LC02 script/local YAML, raw locks and frozen solver executable are unchanged. Each sequence has pre/post 22-file hash checks and generation trace/bag/fpl/raw-write counts 0; solver/evaluator executions 0. Full identities and grouped config diffs are indexed in CLEAN5_PROVIDER_FREEZE_RECORD.md; C-04/C-05 remain unexecuted.
- 2026-09-08 (C): C-04 code freeze 417ae5b096d3b292c998e444291da5b1f43000f4; record commit=this commit (docs(clean5): record BY2H/BY2O five-configuration solver runs and output seal). Ten solver exits 0: BY2H 5 counter_mismatch; BY2O 1 counter_mismatch + 4 technical_failure; both seals PARTIAL, zero solver trace/bag/fpl/raw opens, zero evaluation/plotting, pre/post 22/22 unchanged per sequence. OUTPUT_SEAL SHA256 BY2H 825aa1834e5fe8408bc3e94892a9c5c037d7cd55c47a60b6dcd183fc2e896896, BY2O c5c190213fc15ac283a03092a454e48407ff43411042d8440f2f523c9597647e; retained native counter mismatches and validator/loader collection-transport defect, no retries. Full counters, stderr tails, audit/checkpoint hashes and claim boundaries: CLEAN5_SOLVER_RUN_RECORD.md.
- 2026-09-08 (C): C-04b continuation 2 complete; event implementation ba7d380bb11db5cdc5b3a56ed9f86b148e3db554; contract/execution freeze 7a5b48f0920f1c52c3d0f286855231769631e3ee; record commit=this commit. BY2/BY2H/BY2O event and xcorr gates PASS (windows 66/340, 413/683, 3186/3563); v1 revalidation 10/10 PASS reused with unchanged validators and v1 artifacts retained as SUPERSEDED_NOT_EVALUATED. V2 ten runs COMPLETED (exit 0), both seals PASS; zero solver reference-trace/bag/fpl/raw opens, zero evaluation/plotting; event and solver pre/post raw checkpoints 22/22 unchanged per sequence, checkpoint access hash-only. OUTPUT_SEAL_V2 SHA256 BY2H e34f283f753a2e564379bcace85e383d407e8b84b9309f9163f8de4a818374f5, BY2O ab037dadf7725bb47022ee0a86d9c0ee8f8b45a87acc152270bebc23c5d95285. 306 tests passed; full event intervals, initialization, dropout ledger, counters and audit evidence are appended in CLEAN5_SOLVER_RUN_RECORD.md.
- 2026-09-08 (C): C-05 complete; code freeze 64a25e667c10ba30499108edaa8f559a5bef8b64; record commit=this commit. Revised A2 evaluator identity PASS before any BY2H/BY2O evaluator execution: C00 A04/F04 24 metric checks PASS, synthetic 0/1000 m and 90 deg gates PASS, three identical 80-byte headers with zero data-line reads. V2 offline evaluations 10/10 PASS; per-run coverage=finite=1, evaluator reference opens exactly one each, bag/fpl/raw-write/outside-write counts 0. Both pre/post seals unchanged; 432 tests passed. Decision inputs SHA256 d9867e64d9e57caea19cfd83b7c7dfba5e9fc95e789859fefbc1820b8230ef1e: heading FAIL, position FAIL; no Outcome written. Full tables, source rows, gate and aggregate hashes, audits and decision JSON original: CLEAN5_OFFLINE_EVALUATION_RECORD.md.
- 2026-09-08 (C): C-05/C-06 complete; proposed method A04 by the pre-registered rule (rule commit b9f9a44f288966c95961f7a15564b2b57bf07b65, evidence commit 09caf1e7e6151f18cc25dafad4a7ef5704ae62d2); heading test FAIL, position bound FAIL. The rule text is unchanged; only its Outcome block is filled. Generalization complete; stage 2/3 pending. Three-sequence handoff script: scripts/paper_rebuild/clean5_pack_v1.py; artifact: ~/clean5_handoff.zip.

- 2026-09-09 (C): P-06 complete: one trace-free BY2 calibration, identical s/vrw/abstd transferred to BY2H/BY2O, 15/15 calibrated solves and 30/30 v2/v3 evaluations; stage 2 closeout and clean5_handoff_v2 package indexed in §6. Robustness review: heading FAIL maintained, position PASS reversed; original decision rule and A04 Outcome unchanged.
- 2026-09-10 (C): V-CHK V6 PASS_BY_HUMAN_AMENDMENT; P-07 complete at execution contract 3326a9cbd50d80156fe46309cd1ee5336b5a3c3b and code 24cc761e4085561888a9d8546df8b89300d340fe: 61 cases / 480 excluded, NOT_TRANSFERABLE=[], CAL 669 completed / 2 failed and V2S 663 / 8, no retries; v2/v3 evaluations 2664 completed / 20 unavailable; six hash-only checkpoints 22/22 and provider/solver forbidden opens 0, evaluator trace once per call in child only; main pair/version items 23 maintained / 13 flipped / 24 incomplete, HUMAN_DECISION_REQUIRED, no full rerun; 295 subset capture consistency false retained and GINav horizontal v3 UNAVAILABLE_EVALUATION_FAILED; full tables, decision original, horizontal v3, seals and diagnostics in CLEAN5_DEGRADATION_SUBSET_RESULTS.md; AGENTS §§11/18 updated, gyro-z input check registered but unexecuted, original main chain and Outcome unchanged.

- 2026-09-11 (P-09c): preregistration 56ae6021 / fcf3558f, code freeze b26569185638fabdd2ad121fc25cf784d5a8fdb3. Stopped after 33 solver terminals: 11 COMPLETED + 22 FAILED_TECHNICAL (missing runtime_role in outer validator); native exit 0 for all33, 182/182 byte-anchor checks matched, sequence gate FAIL. No remaining pilot solver, evaluator, aggregate, archive, cleanup or science retry. Full pilot/forecast/zip UNAVAILABLE; both scene roots retained.

- 2026-09-13 (Codex, P-09d/P-10): A1/A2 completed and sealed with 495 native / 990 evaluator terminals, zero failures/retries/core calls/pending; result and combined-package record committed at `dd50a2cd6d876dc71ccfbf37d127122ead46c323`. The 2026-09-13 human decision names F04 under protocol v2, with A04 retained as the v1 pre-registered decision and an ablation. Method statement and 19-file/29-occurrence reference-wording correction are registered; frozen contracts, rule/Outcome and v1 figures retain their bytes. Actual v2 figure rendering follows this documentation commit.

- 2026-09-13 (Codex, P-10 final): 29 composites / 87 exports complete, 29/29 automatic and individual visual checks PASS; 8 reissued + 21 new, including 2 supplementary. P-10 figure delivery is complete: 29 composites (8 reissued + 21 new; 2 supplementary as an overlapping role), 87 PNG/PDF/SVG exports, 29/29 visual PASS. Figure root `<PUBLICATION_ROOT>/figures/v2/`; index `FIGURE_INDEX.md` has GPS Solutions and TIM section columns. ZIP `<HANDOFF_ROOT>/figures_v2_handoff.zip`, SHA-256 `d304001f0f77818cef0604b3b790cc414649c06892d1a7963b1c0d7869c52a60`, 29063129 bytes. Full record: `docs/paper_rebuild/PROTOCOL_V2_FIGURE_DELIVERY.md`. v1 original/copy bytes remain unchanged; no new scientific execution. D uncertainty record, E GPS Solutions/TIM narratives and EXT06 reproduction remain assigned to subsequent conversations and are not executed here.

- 2026-09-15 (Codex, C-CLOSE): conversation C `COMPLETE`, starting from `cff69bf5f1c461bae3036c11565440a73fd1aa91`, equal to upstream and the live GitHub branch before edits. Both v2.1 ZIP hashes and `20_FINALIZE/FINALIZE_COMPLETE.json` match P13; v2.1 scratch has 0 files; no residual project user/system service or runtime process was found. Full `git status` cleanliness is `FAIL` only because the two pre-existing untracked scripts listed in §6 remain preserved; tracked files were clean. AGENTS §18 now contains the verbatim human freeze rule. F04 / v2.1 is the sole manuscript chain; stage closure and artifact identities are in §§2–6, with D, TIM assembly E and independent EXT06 the only remaining work. C-CLOSE made zero provider, solver, evaluator, diagnostic, aggregate, plotting or packaging calls and zero reference-trace payload reads; historical failures and hypothesis `INCOMPLETE` states remain unchanged.

- 2026-09-16 (H-EXT-01): 配置对等审计、BY2/BY2H/BY2O 只读探针、EXT05 序列适配及共享参数草案完成；BY2 默认 EXT05A/EXT05C 逐字节身份门 2/2 PASS，native=2、evaluator=0、trace打开/哈希=0；仅新增外部对比准备，v2.1/C-CLOSE冻结不变，H-EXT-02待人授权；详见 `hext/H_EXT_01_AUDIT_PROBE_ADAPTER.md`。

- 2026-09-16 (H-EXT-02): code_freeze `c9e5133d244e0e3ab1e1385f322fbbf5948ee6d5`；BY2 新路径身份门 2/2 PASS；比较 native 14 完成，evaluator 16 PASS / 第17次 BY2H EXT05C-S FILE_START v3 consistency FAIL / 11 未执行，按授权硬停，无重试或参数/门限修改；完整主表与 FIG02S 未生成，原 v2.1/28图哈希不变；仅封存 HARD_STOP_PARTIAL_EVIDENCE，真实包 SHA/两次提交/CRC 见 `<HANDOFF_ROOT>/hext_three_sequences_handoff.validation.json`；详见 `hext/H_EXT_02_EXECUTION_RECORD.md`。

- 2026-09-17 (H-EXT-03): 合约v1.1/code_freeze `b6aaece1b71737693e39ec72ce0ad0726b188592`；0 native、10新evaluator全PASS、原16复用；D8 13/14有界、原成功16/16回溯PASS，D7一native发散对应两科学槽NOT_RUN，旧第17次失败保留；D9 BY2H论文CONTRACT_START（amended_after_results_seen），三序列S；完整52行/版、遮挡/delta/FIG02S交付，09四项UNAVAILABLE；v2.1/原28图/旧包不变；完整包与提交/真实SHA见 `<HANDOFF_ROOT>/hext_three_sequences_handoff_v2.validation.json`。

- 2026-09-18 (H-EXT-04L): 合约v1.2只读收束，native/evaluator/trace=0/0/0；BY2O九方法两版分段/段外及三序列输入-日志-误差诊断完成，QM/QA均关；LC01文献配置为主行、S补充（amended_after_results_seen）；两记分板、FIG02S v2/FIG02S-b自动与视觉QA PASS，原28图/119文件和RENDER_MANIFEST不变；H-EXT-04执行取消、库NOT_AUTHORIZED_FOR_EXECUTION、T5待预注册；42 tests PASS；详见 hext/H_EXT_04L_RECORD.md。

- 2026-09-18 (T5a): code_freeze a4f2e429c56089e9874097764f337af1f696423b；HARD_STOP_PARTIAL_EVIDENCE，native 3/16、evaluator 0/32、trace 0、重试 0；三个调用因 YAML 重序列化与冻结 native 平面解析语义不匹配而技术无效，新增性能及差值全部 UNAVAILABLE，T5a 科学任务 INCOMPLETE；原 v2.1/28图不变，部分表/图/故障包和未应用修复提案见 hext/T5A_HEADING_SENSITIVITY.md。

- 2026-09-18 (T5a-R): code_freeze d9650fbdf20b2a981a85c1d9875c143c60bc6362；PASS_T5A_HEADING_SENSITIVITY_COMPLETE，16 native/32 evaluator 全部完成，a/b211 门通过，保真 0/0、重试 0、trace 0/32；A0 6539 配置与 33 回显样本已映射比较通过，旧 3 次 INVALID_CONFIG_PARSE 保留且排除；每版22行/100段行/74门控/1025源一致性/44误差序列/6组18图交付，v2.1/28图/v1包不变；v2 ZIP 1006成员、902400804 bytes、SHA256 b8d1451345d81bd87edb2288017d4f931d8a303f1ceb45feb67972264e7b1b20；完整原表与限制见 hext/T5A_R_HEADING_SENSITIVITY.md。
