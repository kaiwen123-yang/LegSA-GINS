# Phase 3 EXT03 Yang 2024 C00 report

Terminal status: `PASS_PHASE3_EXT03_YANG2024_C00_READY_FOR_NATIVE_COMPARISON`

The native Yang-2024 GPS/BDS DD Kalman-filter outputs were sealed before any
same-source trace or NAV-HPPOSECEF semantic access. The implementation is
`FAITHFUL_ALGORITHM_REPRODUCTION WITH_DECLARED_UNSPECIFIED_STOCHASTIC_INSTANTIATION`.
The formal publisher PDF was access-closed in this environment; the supplied
formal Eq. (1)-(9) contract was used, and no attributable official source code
or supplement was found in the single focused search.

Native freeze: `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/04_EXT03_YANG2024/C00/EXT03_C00_NATIVE_FREEZE.json`
Post-native child: `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/04_EXT03_YANG2024/C00/POST_NATIVE`
Supported modes: `GPS_DUAL_FREQUENCY, BDS_DUAL_FREQUENCY, GPS_BDS_DUAL_FREQUENCY`
Proxy-inconsistent ratio-fixed rows (>30 deg): `1744`
RTKLIB diagnostic status: `COMPLETE`

No phase-bias calibration or subtraction was applied. EXT01/EXT02, EXT04,
Classic-18, common-backbone navigation, and Canonical-541 were not executed by
this Phase-3 runner.

## Identity and equation-to-code map

- Paper: Yang et al., IEEE TIM 73 (2024), article 1003414, DOI 10.1109/TIM.2024.3374423.
- RTKLIB: `180043ee24b6d2b168f98b64be15f69d50046b1a`, BSD-2-Clause, unmodified provider plus audited bridges.
- Eqs. (1)-(3),(8)-(9): `build_epoch_blocks` and `build_dd_observation`.
- Eq. (4): `ned_attitude`; Eqs. (5)-(7): `baseline_constraint_linearization` and `constraint_update`.
- KF/dynamic state/MLAMBDA: `process_epoch`, `reconcile_ambiguity_state`, and `mlambda_resolve`.

## Native evidence

- Signal inventory: `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/04_EXT03_YANG2024/C00/EXT03_C00_SIGNAL_AVAILABILITY.csv`.
- Stochastic registry: `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/04_EXT03_YANG2024/C00/EXT03_STOCHASTIC_PARAMETER_REGISTRY.csv` (all `trace_tuned=false`).
- Mode and sensitivity summaries: `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/04_EXT03_YANG2024/C00/EXT03_C00_MODE_SUMMARY.csv`, `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/04_EXT03_YANG2024/C00/EXT03_C00_SENSITIVITY_SUMMARY.csv`.
- Float/fixed/invalid rows, ratios, ambiguity-state counts, constraint innovation/NIS, native baseline/yaw/pitch, runtime, and worker determinism are recorded in the 15-file native inventory and freeze.
- Primary `GPS_BDS_DUAL_FREQUENCY` constrained sigma 0.010 row/fixed/invalid counts: `1509/105/900`.
- Parallel strategy: independent variants only; every recursive variant is strict chronological order. The input-only workers 1 versus 16 scientific-field comparison is hashed in the native summary resource evidence.

## Post-native descriptive evidence

- Proxy rows/summary: `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/04_EXT03_YANG2024/C00/POST_NATIVE/EXT03_C00_PROXY_DIAGNOSTICS.csv`, `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/04_EXT03_YANG2024/C00/POST_NATIVE/EXT03_C00_PROXY_SUMMARY.csv`.
- Trace rows/summary: `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/04_EXT03_YANG2024/C00/POST_NATIVE/EXT03_C00_TRACE_DIAGNOSTICS.csv`, `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/04_EXT03_YANG2024/C00/POST_NATIVE/EXT03_C00_TRACE_SUMMARY.csv`.
- Fractional-DD relationship: `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/04_EXT03_YANG2024/C00/POST_NATIVE/EXT03_C00_PHASE_BIAS_RELATIONSHIP.json`; relationship only, no calibration.
- Unmodified RTKLIB diagnostic: `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/04_EXT03_YANG2024/C00/POST_NATIVE/EXT03_C00_RTKLIB_DIAGNOSTIC.json`; diagnostic-only and never solver input.

## Reproduction

`python3 scripts/paper_rebuild/run_horizontal_literature_phase3.py --paths-config configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml --method-id EXT03_YANG2024 --case-id C00 --trace-mode disabled --workers 16`

Focused implementation tests are maintained in `test_horizontal_ext03_yang2024.py` and `test_horizontal_phase3_c00.py`. Independent reviewer verdict remains `PENDING`; the supervisor/human owns the final review and Git decision. No commit, push, merge, or tag is performed by this runner.
