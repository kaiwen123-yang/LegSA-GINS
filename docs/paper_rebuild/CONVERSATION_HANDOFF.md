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

| Manuscript label | Registry id | Role |
|---|---|---|
| Single | `F01` = `single_antenna_EKF` | baseline (position + receiver velocity, no yaw) |
| Dual-basic | `F02` = `basic_dual_yaw_EKF` | baseline (dual yaw only, fixed 1.5 deg std) |
| Backbone | `F03` = `A02` = `AB0000` | proposed method without RD/RP/HV/SA; ablation row only, never a "strong baseline" |
| Core | `A04` = `AB1011` | candidate proposed method (Source-Aware disabled) |
| Full | `F04` = `A01` = `AB1111` | candidate proposed method (Source-Aware enabled) |

The graduation-design algorithm (`final_v23`, the backbone) has never been published;
the manuscript still adds one sentence declaring reuse of graduation-design material,
as TIM requests for thesis material.

Proposed-method identity: `PROVISIONAL_PENDING_BY2H_BY2O`, decided only by
`docs/paper_rebuild/A04_F04_ROLE_DECISION_RULE.md` (commit hash: `b9f9a44f288966c95961f7a15564b2b57bf07b65`).

## 3. Comparison structure

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
| Same-day poor-heading run | `BY2H`, `CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE` |
| Same-day single-antenna occlusion run | `BY2O`, `CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE` |
| C00 input-parity experiment (A04 fed 5 Hz GNSS1 HPPOSECEF; EXT05C single-receiver IEKF) | `CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF` |
| Publication figures | `CLEAN6_PUBLICATION_FIGURES/01_CANONICAL541`, `.../02_HORIZONTAL` |

Rules for BY2H/BY2O: BY2-frozen parameters, own yaw physical gate, occlusion window
defined from input-side flags before evaluation, no Canonical matrix rerun, no tuning.

## 5. Task ownership

| Conversation | Owner | Scope | Status |
|---|---|---|---|
| A | Claude (matrix-figure conversation) | derived tables (A04 vs F03 / F02, F04 vs F02, bootstrap CI, stratified Wilcoxon, bias/random decomposition), publication plotting common layer, Canonical-541 figures, captions, this file | common layer + BY2 draft figures rendered; waiting for BY2H/BY2O |
| B | new conversation | horizontal publication figures FIG02/FIG03 (FIG04 supplementary), reuses A's common layer | common layer available (src/legsa_gins/paper_rebuild/publication/) |
| C | Codex / execution conversation | BY2H, BY2O, input-parity runs and evaluation | waits for authorization |
| D | new conversation | yaw uncertainty budget, consistency diagnostic, bias/precision wording | after A's decomposition |
| E | new conversation | manuscript | last |
| F | new conversation | clean submission repository, data/code release | last |

## 6. Data handoff locations

- Canonical-541 authoritative attempt: `<CANONICAL541_ATTEMPT>` (see AGENTS section 3).
- Packed subset for conversation A: `~/c541_handoff.zip` produced by `c541_pack_v2.py`
  (aggregates, whitelisted evaluation columns, decimated representative error series,
  C00 NAV files, identity probe). Decimated series are display-only; every metric comes
  from the frozen aggregate tables.
- Horizontal synthesis tables for conversation B: `<CLEAN4 root>/13_HORIZONTAL_CROSS_LAYER_SYNTHESIS/`.

## 7. Open items

- [x] Decision-rule file committed; hash recorded above.
- [x] AGENTS section 12b (Canonical-541 publication figures) inserted.
- [x] Stale tracked docs (ACTIVE_CONTEXT, NEXT_STAGE_INSTRUCTIONS, GINav/Hartley BLOCKED reports) synchronised before BY2H/BY2O run.
- [x] Bias/random decomposition result reported (conversation A) and consumed by C and D.
- [x] Derived pairwise `A04_vs_F02`, `F04_vs_F02`, `A04_vs_F03` added under the publication namespace.

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
