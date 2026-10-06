# Carrier robustness checkpoint — 2026-10-06

This stage advances the experimental carrier frontend under the author's carrier-only scope. It implements causal fixed-window integer consistency checks, physical signal fault diagnostics, fault sensitivity, and a full-temporal-covariance validation path. All algorithm edits and computations run in the E-drive Ubuntu 22.04 WSL. V3, the production EKF, manuscripts and earlier result directories are preserved.

## What is usable now

- The first five epochs select the best and second distinct active integer classes. Those integers are frozen; only the next five registered time slots validate them. Missing support is not replaced by later samples, and a failed primary is not exchanged for the competitor.
- Residual consistency and known baseline length have separate gates with explicit statistical assumptions. A shadow pass never becomes a production FIX measurement. A global search certificate concerns the optimization problem, not integer truth.
- A per-signal fault map models reference-satellite faults across all affected phase DDs with the correct sign, wavelength and shared covariance. Persistent diagnostics join only identical physical SD arcs. Holm-corrected profiles and aliases remain diagnostic.
- Fault sensitivity computes minimum detectable cycle bias and its free-GLS baseline response using the supplied geometry and covariance. This addresses the observed distinction between correct integers and reliable baseline measurements. It does not provide a heading protection bound.
- The new joint-covariance path accepts an explicit full future Q, performs joint free-baseline GLS, and uses marginal baseline-length tests with a Bonferroni allocation. It never replaces cross-time Q by its diagonal. Selection dependence is explicit and blocks admission.

## Original registered synthetic trial

72 independent base draws (24 calibration, 48 heldout), 72 CILS calls and 504 paired validation conditions completed. Every search certified the registered objective; no timeout was hidden and no call was repeated to obtain a better outcome. All thresholds were fixed before those outcomes. [Full results and adverse cases](SYNTHETIC_READOUT.md) include 504 rows and stratified accepted-subset angular errors.

In the heldout clean condition, M3/M4/M9 correct integer shadow acceptance was 10/16, 15/16 and 16/16. The three-group M9 model rejected all registered quarter-cycle target/pivot faults, missed slips and two-signal biases on those 16 heldout draws. That result is limited to the specified geometries, signals and Q.

The counterexamples are material. Calibration contains two wrong-integer shadow passes and one pass under an unrepresentable missed-slip model, from two independent draws. With a quarter-cycle pivot bias, 21 heldout cases passed with correct integers but their accepted-subset three-dimensional baseline-angle RMSE averaged 13.562 degrees; the largest per-case RMSE was 15.352 degrees. This is why integer correctness cannot stand in for a heading measurement-quality claim.

Review also found that the original rho=0.8 generator links the first validation noise to the last selection noise. Its old results remain unchanged and are explicitly model-mismatch stress tests. A correct future marginal Q alone does not remove dependence on integer selection.

## New real-data window

The [registered scope](00_SCOPE_AND_CONTRACT.md) chose BY2 120–140 s before inspecting that window. It yielded 100 exactly paired raw epochs. Navigation remains restricted to source messages available by 100 s. Ten fixed five-plus-five windows across three requested signal families required 30 CILS calls; all objective certificates completed. Real integer truth is unknown.

| Family | Windows | Shadow passes | Unresolved arc support | Unresolved competition | Residual rejection | Length rejection |
|---|---:|---:|---:|---:|---:|---:|
| GPS L1 | 10 | 1 | 0 | 7 | 0 | 2 |
| GPS L1/L2 | 10 | 2 | 5 | 0 | 3 | 0 |
| GPS/Galileo/BeiDou dual frequency | 10 | 0 | 10 | 0 | 0 | 0 |

Arc status has precedence in this table. On the retained observation rows, nine of ten multi-GNSS primary residuals also exceed their nominal gates; treating these as merely arc bookkeeping failures would be incorrect. The only multi-GNSS window whose primary passes both gates has identical primary/competitor scores after the distinguishing arc disappears, so dropping that arc cannot establish a distinct integer class.

There are no pivot-coordinate switches in these windows. Most changes involve invalid carrier/half-cycle flags, lock loss or reacquisition. Some otherwise continuous signals cross the registered TDCP-Doppler diagnostic threshold; those events are suspicious links, not proof of physical cycle slips. A few group losses involve an unavailable fixed pivot. Exact pivot transport may preserve remaining contrasts, but cannot restore a reset SD integer or explain the large residuals.

The 3 passes are GPS dual at window starts 120 and 126 s, and GPS L1 at 136 s. They are algorithmic shadow decisions under the RAWX working covariance, not confirmed correct FIX or measured navigation improvements. The six old-window replays add no CILS calls and produce no passes. See [36-window table](REAL_SHADOW_RESULTS.csv) and [source/result summary](REAL_SHADOW_SUMMARY.json).

## Fault sensitivity and interpretation

All 36 saved real windows were analyzed without new integer searches, giving 426 physical signal/arc profiles in [REAL_FAULT_SENSITIVITY.csv](REAL_FAULT_SENSITIVITY.csv). For the new window, finite modeled minimum detectable biases have medians of about 9.263 cycles (GPS L1), 0.143 cycles (GPS dual) and 0.094 cycles (multi-GNSS), across different physical hypothesis sets. Unknown-arc columns remain explicitly undetectable. These aggregate values are diagnostics rather than a fair accuracy ranking.

The large GPS L1 sensitivity follows from weak phase redundancy after eliminating a free three-dimensional baseline: many phase errors can be absorbed by baseline changes and only noisy code residuals expose them. The known-length gate adds information that this free-GLS sensitivity does not model. Large computed free-baseline biases therefore must not be described as physically realized errors of the length-constrained solution.

The real working Q is heterogeneous: GPS L1 residual sums are only 0.219–1.118 on 15 degrees of freedom, whereas many multi-GNSS windows are incompatible. A blanket covariance inflation would have no established physical calibration and can make candidate competition worse. No scale was fitted to force acceptance.

## Follow-up, evidence scope and continuation

[The follow-up contract](01_FOLLOWUP_MECHANISM_CONTRACT.md) is explicitly post-result development: full-Q replays reuse the old candidates/geometries, and fresh future-only AR(1) noise is independent of selection. No additional CILS is performed. Original rho08 replay reports UNRESOLVED_SELECTION_DEPENDENCE. The new covariance is known from simulation generation; it is not an estimated real receiver model.

The completed follow-up contains 216 joint validations, 72 new matched IID validations, three synthetic sensitivity models (21 physical signal columns), and zero new integer searches. The producer read the synthetic truth only to generate the declared mean; the validator read no truth, and outcome labels were evaluated after decisions were sealed.

| Paired dataset | Joint correct shadow passes | IID correct shadow passes | Joint wrong shadow passes | Joint unresolved |
|---|---:|---:|---:|---:|
| Original CLEAN, 72 reused selections | 60 | 60 | 0 | 7 |
| Original rho08 with selection dependence, 72 | 0 | 60 | 0 | 72 |
| Fresh independent-future rho08, 72 reused selections | 60 | 58 | 0 | 8 |

In the fresh-future comparison, two correct candidates rejected by the IID residual gate passed the joint method. No wrong candidate passed either method in this small simulation. Mean angle RMSE among accepted correct cases was about 1.804 degrees (joint marginal sphere projections) and 1.796 degrees (IID sphere fits), on different accepted subsets. This is not a demonstrated angle-accuracy improvement. The method also changes the length test from a summed statistic to marginal Bonferroni tests; aggregate decision differences cannot be attributed solely to covariance. The two methods exchange one clean-case pass each while retaining equal clean totals.

The original rho08 row is a refusal to claim supported conditional validation under selection dependence, not a numerical recovery experiment. Full details and paired rows are in [COVARIANCE_FOLLOWUP_READOUT.md](COVARIANCE_FOLLOWUP_READOUT.md), [COVARIANCE_FOLLOWUP_RESULTS.csv](COVARIANCE_FOLLOWUP_RESULTS.csv), and [COVARIANCE_FOLLOWUP_SUMMARY.json](COVARIANCE_FOLLOWUP_SUMMARY.json). Generative Q remains an oracle model, so there is still no calibrated real-data false-fix guarantee.

The next engineering priority is a qualified temporal/cross-frequency error model and phase-fault-aware measurement quality, followed by predefined partial-arc admission that still distinguishes the competing classes. Reconnecting raw loss-of-lock arcs or scaling Q on rejected outcomes is not supported by these results. V3 remains the navigation baseline until a new carrier measurement earns admission and demonstrates heading benefit.

Reproduction scripts live in scripts/paper_rebuild/carrier_phase: robustness_trial.py, shadow_replay.py, sensitivity_replay.py and the joint-covariance follow-up runner. Native LAMBDA/state-provider roots use configs/paper_rebuild/EXT_REPRODUCTION_ROOTS.local.json. Scientific scratch products are under /home/kaiwen/research/LegSA-GINS-SCRATCH/CARRIER_ROBUSTNESS_20261006. Replays write new directories; original results are not overwritten.

## Automated verification

The complete carrier-focused regression run passed 212 tests in Ubuntu 22.04 WSL at the frozen follow-up source checkpoint 8e268ba. Coverage includes the prior solver/arc/native-interface tests and new GLS residuals, shared-pivot faults, fixed future support, candidate immutability, full temporal covariance, marginal length gates, detection-power calculations and selection/validation separation. Independent dense-matrix checks also reviewed the joint GLS and fault-diagnostic formulas. This is the carrier suite, not a claim that every unrelated repository test was run.

Run from the source worktree:

    PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -m pytest -q tests/paper_rebuild/test_carrier_*.py tests/test_carrier_robustness_design.py tests/test_carrier_covariance_followup.py

New milestones are labelled feat(ar-research), test(ar-research), and docs(ar-research) on research/ar-tim-exploration-20261006 and maintained through draft PR #65. Documentation tables retain failures; source/runtime receipts remain in the registered scratch folders.
