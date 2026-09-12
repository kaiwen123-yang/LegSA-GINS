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

P-09c selects protocol v2 as the preregistered manuscript target while retaining v1 as the original preregistered record. Full-matrix numerical switch and final v2 handoff remain NOT_EXECUTED: the explicitly authorized restart stopped during batch 8 archive with `OSError [Errno 12] Cannot allocate memory`. Its sequence gate and first seven complete batches passed; original failure records are preserved. Method identity A04 and its existing Outcome remain unchanged.

| Manuscript label | Registry id | Role |
|---|---|---|
| Single | `F01` = `single_antenna_EKF` | baseline (position + receiver velocity, no yaw) |
| Dual-basic | `F02` = `basic_dual_yaw_EKF` | baseline (dual yaw only, fixed 1.5 deg std) |
| Backbone | `F03` = `A02` = `AB0000` | proposed method without RD/RP/HV/SA; ablation row only, never a "strong baseline" |
| Core | `A04` = `AB1011` | proposed method (Source-Aware disabled) |
| Full | `F04` = `A01` = `AB1111` | protection extension (Source-Aware enabled) |

The graduation-design algorithm (`final_v23`, the backbone) has never been published;
the manuscript still adds one sentence declaring reuse of graduation-design material,
as TIM requests for thesis material.

Proposed-method identity: `A04`, decided 2026-09-08 by
`docs/paper_rebuild/A04_F04_ROLE_DECISION_RULE.md` (rule commit: `b9f9a44f288966c95961f7a15564b2b57bf07b65`;
evidence commit: `09caf1e7e6151f18cc25dafad4a7ef5704ae62d2`).

## 3. Comparison structure

Protocol v2 full-matrix comparison status: `NOT_EXECUTED / UNAVAILABLE_FULL_MATRIX_INCOMPLETE`. The restart sequence gate passed with P-07 C00 77/77 and P-06 105/105 hash matches. Batch 1 completed the C00 eleven-profile v3/v2 evaluations; these anchors are recorded in AGENTS section 7 and `docs/paper_rebuild/clean6/P09C_RESTART_C00_ANCHORS.csv`. Full-matrix median/CI/win-rate and v1/v2 maintained/flipped tables were not generated after the batch-8 archive stop. Neither partial-case statistics nor v1 tables substitute for them.

- Comparison tables/figures (with external methods): Single, Dual-basic, proposed
  (plus the other candidate as "+/- Source-Aware" where space allows).
- Ablation table/figure: Dual-basic -> Backbone -> +RD -> +RP/HV -> +SA, all from the
  frozen Canonical-541 tables (541 x 11 unique configurations).
- Delta convention everywhere: candidate - reference, negative is better; always report
  mean, median, and case win rate together.
- Reference label inside figures follows AGENTS section 13 (`Truth`); prose carries the
  same-source caveat. Risk noted for a metrology journal; the human owns this choice.

## 4. Planned stages and naming

| Purpose | Stage id / dataset id |
|---|---|
| Same-day poor-heading run | `BY2H`, `CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE`; status: `EVALUATED` |
| Same-day single-antenna occlusion run | `BY2O`, `CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE`; status: `EVALUATED` |
| C00 input-parity experiment (A04 fed 5 Hz GNSS1 HPPOSECEF; EXT05C single-receiver IEKF) | `CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF` |
| Publication figures | `CLEAN6_PUBLICATION_FIGURES/01_CANONICAL541`, `.../02_HORIZONTAL` |

Rules for BY2H/BY2O: BY2-frozen parameters, own yaw physical gate, occlusion window
defined from input-side flags before evaluation, no Canonical matrix rerun, no tuning.

## 5. Task ownership

| Conversation | Owner | Scope | Status |
|---|---|---|---|
| A | Claude (matrix-figure conversation) | derived tables (A04 vs F03 / F02, F04 vs F02, bootstrap CI, stratified Wilcoxon, bias/random decomposition), publication plotting common layer, Canonical-541 figures, captions, this file | common layer + BY2 draft figures rendered; waiting for BY2H/BY2O |
| B | new conversation | horizontal publication figures FIG02/FIG03 (FIG04 supplementary), reuses A's common layer | common layer available (src/legsa_gins/paper_rebuild/publication/) |
| C | Codex / execution conversation | BY2H, BY2O, input-parity runs and evaluation | generalization complete, stage 2/3 pending |
| D | new conversation | yaw uncertainty budget, consistency diagnostic, bias/precision wording | after A's decomposition |
| E | new conversation | manuscript | last |
| F | new conversation | clean submission repository, data/code release | last |

## 6. Data handoff locations

- P-09c explicit restart terminal, 2026-09-12 05:16:10 Asia/Shanghai: `STOPPED_GATE_FAILURE` during batch 8 archive SHA reading (`OSError [Errno 12] Cannot allocate memory`). Seven batches passed archive/cleanup. Total native terminals: 1989 COMPLETED +59 ALL_YAW_REJECTED (D14=34, D15=25); 3925 unique runs unexecuted. Native/evaluator technical failures=0; archive technical failure=1. Batch 8 has 256 completed solvers, 512 completed evaluations, 255/256 archive receipts; missing `RUN_01963` (D20_seed_06, A03/AB0111). Its full scratch batch and partial G archive remain, with no retry or cleanup. Current record: `docs/paper_rebuild/CLEAN6_CANONICAL541_V2_RESTART_STOP.md`; machine report `<CANONICAL541_V2_ROOT>/RESTARTS/RESTART_20260912/RESTART_STOP_REPORT.json`. Final ZIP and SHA-256 are UNAVAILABLE.
- P-09c restart first-batch and sequence gates remain PASS: original native reuse 33, reruns 0, P-06 105/105 and P-07 C00 77/77 byte checks. First-batch measured table: `docs/paper_rebuild/CLEAN6_CANONICAL541_V2_RESTART_PILOT.md`. Peak forecast 221127477999 bytes was a continuation forecast; exact whole-execution disk peak is UNAVAILABLE because early absolute baselines were not stored. Coverage is documented in `docs/paper_rebuild/CLEAN6_CANONICAL541_V2_RESTART_RESOURCE_COVERAGE.md`. Do not automatically resume or finish the partial archive.

- Original protocol-v2 stop: `<CANONICAL541_V2_ROOT>/99_STOP_REPORT/`, terminal `STOPPED_GATE_FAILURE` as of 2026-09-11. Authorized restart reused the original outputs; batch-1 archives now reside in `RETAINED_RUNS/`, and its scratch files were ledger-cleaned after verification.
- P-09c record: `docs/paper_rebuild/CLEAN6_CANONICAL541_V2_PILOT_STOP.md`; family/config counters and attempted-run timings under `docs/paper_rebuild/clean6/P09C_*.csv`.
- `scripts/paper_rebuild/c541_pack_v3.py` is implemented but NOT_EXECUTED. `~/c541_v2_handoff.zip` is NOT_PRODUCED; SHA-256 UNAVAILABLE.

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

- [x] Decision-rule file committed; hash recorded above.
- [x] AGENTS section 12b (Canonical-541 publication figures) inserted.
- [x] Stale tracked docs (ACTIVE_CONTEXT, NEXT_STAGE_INSTRUCTIONS, GINav/Hartley BLOCKED reports) synchronised before BY2H/BY2O run.
- [x] Bias/random decomposition result reported (conversation A) and consumed by C and D.
- [x] Derived pairwise `A04_vs_F02`, `F04_vs_F02`, `A04_vs_F03` added under the publication namespace.

- [ ] BY2O 门控拒绝/降权历元的 post-hoc 时间线（A/D）。
- [x] BY2H/BY2O 水平误差体坐标分解：stage 2 与标定链各版 BODY_FRAME_BIAS.csv 已冻结；图件归对话 A。
- [ ] SA 的 Up 代价按源分解（A/D）。
- [x] Stage 2 position gap decomposition 与输入时标/RV 同历元重配记录已冻结；v3 使用人类安装声明与冻结几何，不含 trace 拟合。
- [ ] CAD 核对天线–IMU 高度差及杆臂 z；v3 上向残差仅报告，不据此继续修正。
- [ ] 对话 A 图件：误差预算阶梯、体坐标偏差、敏感性热图、标定链三序列表；保留主链/标定链与 v2/v3 标识。
- [ ] remaining: BY2O gating sensitivity to IMU integration convention；V2 与 V2is 同时改变处理约定和加速度计标度，不能作为独立积分因果项。
- [ ] 对话 D 不确定度输入：时标约 0.205 s、BY2 半基线约 0.178 m、PVT−trace 差分垂直速度差标准差约 0.043 m/s（DERIVED_DIAGNOSTIC_ONLY）；各 run 的高度/北/东/yaw 一致性比见标定链 UNIQUE 表（v3 位置 STD 未传输）。BY2 冻结 s=1.0308398903907543；vrw=[9.478382094779873, 9.784198200134004, 7.6321402201126745] (m/s)/√h；abstd=[4817.482008954474, 8259.572423450163, 2257.241538343225] mGal；拟合 c=[0.010830809489394968, 0.013550612232080246, 0.020536668097236248] (m/s)²。原始数值、三轴窗数与来源见 `08_AGGREGATE/FROZEN_SENSOR_MODEL.csv` 和 `00_CALIBRATION/LAG_VARIANCE_FIT.csv`。

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
