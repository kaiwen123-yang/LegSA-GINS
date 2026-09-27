# UNCERTAINTY_HANDOFF — measurement-uncertainty results for the manuscript conversation

Date 2026-09-27. Fills the placeholder [PENDING: measurement uncertainty] in the writing handoff. The uncertainty conversation is closed with this file; nothing in it changes a sealed result, and no rerun is requested. All files live in docs/paper_rebuild/v3/uncertainty/ on branch stage/clean3-math-repair; UA-01 inputs are at commit 58d6d9c, this delivery is the UA-02 commit.

## 1. What to paste where

| Manuscript place | Take from | Notes |
|---|---|---|
| Experimental setup / evaluation: "Measurement uncertainty" paragraph (≈250 words) | UNC03_MANUSCRIPT_TEXT.md §1 | already in the field-native wording; keep the receiver description verbatim |
| Limitations: three sentences | UNC03_MANUSCRIPT_TEXT.md §2 | rows 2, 3, 6 of the budget |
| Main three-sequence table note | UNC03_MANUSCRIPT_TEXT.md §3 | intervals of the proposed method |
| Results, BY2 comparison with the loosely coupled baseline (optional sentence) | UNC03_MANUSCRIPT_TEXT.md §4 | use only if the "direction holds, interval includes zero" wording is adopted |
| Supplement: uncertainty budget table | UNC01_UNCERTAINTY_BUDGET.md §1 (13 rows) or UNC_BUDGET.csv | condense to 8–10 rows for the supplement; keep rows 1–6, 9, 10 |
| Supplement: paired-difference intervals | UNC_DISTINGUISHABILITY.csv (56 rows) | one table: sequence, pair, Δ, 95 % interval |
| Supplement: window-realization intervals | UNC_REALIZATION_INTERVALS.csv | all 37 rows × yaw/horizontal/height |
| Supplement: fault-matrix dispersion and quantile intervals | UNC_SEED_DISPERSION_SUMMARY.csv; UA01_DISTRIBUTION_QUANTILES.csv (type-cluster columns) | never quote the case-level (naive) intervals |

## 2. Numbers the text may quote (all sourced; see UNC01 for line references)

- Reference heading 1.1° (0.4° at 1 m → 0.35 m separation; receiver-reported 0.9–1.0°); reference position 0.02–0.05 m; short-term reference heading noise ≤ 0.06°.
- Common-mode motion-induced heading term 1.1–1.4° RMS (all thirteen estimators; 0.06° stationary); along-track offset 0.03–0.04 m; shares ≈ half of heading MSE (BY2/BY2H; 20 % on BY2O) and ≈ one fifth of horizontal MSE.
- Estimator-dependent heading bias 0.3–1.4° (installation yaw, frozen uncorrected).
- Decomposition of the proposed method's heading error: BY2 1.886° = bias 1.09 ⊕ slow 0.82 ⊕ fast 1.31; BY2H 1.934° = 0.54 ⊕ 1.22 ⊕ 1.41; BY2O 2.434° = 0.34 ⊕ 2.08 ⊕ 1.08 (quadrature). Estimator-specific part √(bias² + slow²) = 1.36 / 1.34 / 2.10°.
- Window-realization 95 % intervals of the proposed method: heading [1.60, 2.16] / [1.60, 2.04] / [1.36, 3.61]°; horizontal [0.045, 0.152] / [0.045, 0.085] / [0.038, 0.073] m.
- Paired heading differences (A − B, Δ [95 %]): LC01 − F04 BY2 +1.11 [−0.22, +2.57]; BY2H +0.27 [−0.05, +0.51]; BY2O +0.02 [−1.34, +1.40]; BY2O float segment +3.78 [+2.20, +4.44]. F04 − F02 BY2 −0.35 [−0.69, −0.06]; BY2H −0.35 [−0.83, −0.02]; BY2O +0.12 [−0.03, +0.22]. F04 − F03 and F04 − A04: |Δ| ≤ 0.03°, intervals include zero. LC01-S − F04 BY2 −0.35 [−0.59, −0.15].
- Paired horizontal differences: LC01 − F04 −0.3 / +6.4 / −0.2 mm, all intervals include zero; F04 − F02 −4.0 / −3.1 mm (BY2 / BY2H, intervals exclude zero, below practical relevance).
- BY2O segments: heading F04 / LC01 0.233 / 4.008° inside the float segment, 2.589 / 1.878° outside.
- Fault matrix: F04 heading seed SD < 0.1° for 50 of 60 types (median 0.002°), ≥ 1° only for the gross-fault types D14, D15, D41, D59; LC01 − F04 heading difference positive for every seed where both are finite (min 0.92°); D62 position outage F04 − F03 −1.61 m (10 s) and −10.5 m (20 s), 9/9 seeds; F04 − A04 parity.
- Type-cluster 95 % interval of the F04 heading P95 over 541 cases: [2.00, 4.18]° (point 2.45°).

## 3. Rules for wording and precision (agreed in the uncertainty conversation)

1. Tables: three decimals for heading (degrees) and position (metres); the values are exact for the windows.
2. Absolute levels in prose carry the realization interval of §2 once per sequence.
3. Between-method differences on the same sequence carry their paired interval; verdict by the rule in UNC02 §1 (RESOLVED / RESOLVED_NEGLIGIBLE / PARITY / DIRECTION_ONLY); no percentages, no "significant".
4. BY2O is always written by segment.
5. Fault-matrix quantiles carry type-cluster intervals; failure rates of two types are compared only when they differ by ≥ 5 of 9 seeds.
6. The ablation ladder: only the F02 → F03 step (residual gating + roll/pitch prior) is resolved for nominal heading (BY2, BY2H); RD, HV and SA are neutral for nominal heading and are argued from the D62 family and the D14/D21 completion rate.
7. Do not quote a single "true" estimator RMSE; quote the decomposition.

## 4. Decisions and limitations to carry into the manuscript

- The common-mode fast heading term is reported as an evaluation-chain term of undetermined origin (limitation sentence 1); it is not subtracted from any table value.
- The installation yaw is a limitation (sentence 2); the chain stays frozen.
- The lever-arm vertical component is a limitation (sentence 3), bounded by the height residual.
- The filter's own covariance is not used as an uncertainty statement (heading consistency ratio 3.3–5.9).
- The "+40 ms" residual time-offset pilot stays in future work; it is one of several consistent explanations of rows 2 and 5, not the headline.

## 5. File index (docs/paper_rebuild/v3/uncertainty/)

| File | Content |
|---|---|
| UNC01_UNCERTAINTY_BUDGET.md | budget table, heading decomposition, position decomposition, realization intervals, fault-matrix statistics, A1/A2, changes vs the 09-26 draft, open items |
| UNC02_DISTINGUISHABILITY.md | verdict rule and the manuscript comparisons with wording |
| UNC03_MANUSCRIPT_TEXT.md | English paragraph, limitation sentences, table note, optional results sentence, Chinese notes |
| UNC_BUDGET.csv | budget table, machine-readable |
| UNC_YAW_DECOMPOSITION.csv, UNC_FAST_COMPONENT_RANGE.csv | heading decomposition of all C00 rows; per-sequence fast-component range |
| UNC_HORIZONTAL_BODY_DECOMPOSITION.csv | body-frame position decomposition parsed from CLEAN5_STAGE2_CLOSEOUT.md §10 |
| UNC_REALIZATION_INTERVALS.csv | SE and moving-block bootstrap intervals of every whole-window RMSE |
| UNC_DISTINGUISHABILITY.csv | 56 paired comparisons with verdicts |
| UNC_SEED_DISPERSION_SUMMARY.csv | per-configuration seed-SD summaries over the 60 fault types |
| UNC_CLAIM_CHECKS.csv, UNC_CLAIM_CHECK_RESULTS.csv | 277 numeric claims of the documents asserted against the derived tables |
| UNC_INPUT_PINS.json | sha256 of the 12 UA-01 inputs |
| scripts/paper_rebuild/unc02_derive_and_check.py | regenerates every UNC_*.csv from the UA-01 outputs and runs the claim checks |
| UA01_* (commit 58d6d9c) | the read-only statistics this delivery is built on |
