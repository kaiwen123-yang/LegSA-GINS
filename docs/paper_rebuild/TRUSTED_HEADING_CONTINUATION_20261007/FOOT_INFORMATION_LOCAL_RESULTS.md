# Foot-information passive diagnostic qualification

Status: local synthetic qualification complete; real-window calls remain 0. This is an implementation and numerical-diagnostic result, not an explanation of all 2510 archived SKIP decisions.

## What changes

`LEGSA_FOOT_INFORMATION_DIAGNOSTICS=1` enables passive logging for the existing PAIR_YOUNG update. It records the complete prior P24/mean, H3x24, R3x3, residual, fixed current21 weights, five original candidate scores, comparison scores/ties/actions and T/J. Default off preserves the original output set. The original epsilon grid, quality gate, full Young covariance bound, selected update, feedback and retirement are unchanged. Unsupported or nonfinite C++ J is logged as unavailable; no jitter or changed state update is introduced.

The offline `foot_information_diagnostic.py` only reads this dump. It independently checks all five full-P scores, their ordered tie-based selection and the final native action. It reports numerical ranks/spectra, J/T, the continuous-family derivative criterion and a bracketed diagnostic minimum. No continuous optimizer is applied to the filter.

For fixed working P/H/R/W, T=tr(WP), J=tr(WPH^T R^-1 HP) and f'(0)=T-J. J>T allows a mathematical improvement within the continuous Young/CI trace family; the report separately records whether the proposed score beats the original floating-point SKIP tie. This is not a yaw-accuracy, physical-observability, SDK-independence or integrity guarantee.

## Numerical boundary review and repair

An independent static review found that a mixed-unit global eigenvalue threshold could discard a tiny positive variance with a large weight, making a false score reduction at SKIP. The first 24 passing tests had not covered this case. The repaired diagnostic normalizes P by its nonzero diagonal for factorization and retains every positive mode. Reported numerical rank does not remove score mass. The final score is independently evaluated with complete P; omega=0 returns T exactly. T, J and objective consistency have separate relative/absolute tolerances. Inconsistency gives UNRESOLVED/NA rather than a continuous-optimum claim. Numerical rank is not used to assert a zero-noise impossibility theorem; Gmax and that theorem's decision remain NA, with numerical quantities separately identified.

Two added tests cover P=diag(1,1e-16), W=diag(1,1e16), H=0 and diagonal changes of coordinate units with the corresponding W/H transformations. The former correctly reports T=2, J=0, score=2 and zero reduction.

## Actual calls and results

- Attempt 01: one configure/build/harness compile; one pytest invocation, 24/24 passed (16 existing native-clone cases plus 8 new diagnostic cases).
- Independent review repair: the original attempt remains unchanged. Attempt 02 rebuilt the passive binary and ran only the 8 affected diagnostic cases plus 2 new boundary cases. Initial result: 9 passed, 1 failed because NumPy boolean reporting was not JSON serializable. Reporting-only casts repaired it; only that one test was rerun, and passed.
- Unique tests across both attempts: 26; actual test executions: 35. Total configure/build/harness compile calls: two each. No real navigation, evaluator, raw or reference reads.
- New-versus-old sealed synthetic harness comparison covers six engine scenarios with byte-identical stdout. On/off passive logging preserves state output, original event log, fixed weights and runtime manifest bytes in the synthetic engine scenario.
- One earlier source-edit literal replacement failed on indentation before any build/test; completed edits were retained and the unique replacement corrected. Details are in FOOT_INFORMATION_IMPLEMENTATION_LOG.jsonl.

The final binary, source pins, stage aliases and both retained test attempts are identified in FOOT_INFORMATION_LOCAL_RESULTS.json. The local runner's post-run path parameterization does not change numerical sources; its original test scope remains the original 24 cases.

## Three-window handoff, not yet executed

FOOT_INFORMATION_TRIAL_PLAN.json registers three PAIR-only calls and zero evaluators. `foot_information_trial.py` requires the plan/source to match a registration commit and the scratch root to match the original sealed alias. It reuses exact configuration bytes and all old providers, with only the CLI output destination and passive logging flag changed. Its diagnostic identity is separate from the inherited transport run_id. The old sealed event hash is checked; each new dump row must match the old accepted-for-selection END time/action in order.

The scientific-state gate is exact equality of new NAV and STD to the corresponding old PAIR outputs, plus original event-log byte identity. On any mismatch, preserve failure and stop; do not evaluate or substitute output. All three calls must be sealed before readout. Commands use `prepare`, `native`, then `summarize`, each with `--registration-commit`, `--scratch-root`, and the fixed new `--stage`.

## Foot-source boundary

The evidence remains SportModeState robot-reported foot positions. The real FK/internal filter/IMU generation chain, physical SDK-body to IMU mapping, acquisition delay and joint error model are not established by this work. No raw encoder FK or statistically independent leg odometry is claimed. This diagnostic does not shrink R, change epsilon, reselect feet, or calibrate the 1 cm working marginal bound using navigation errors.
