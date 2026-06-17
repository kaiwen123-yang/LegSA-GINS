# PAPER10E0 Validation Pointers

This tracked file records lightweight validation pointers only. Runtime NAV/STD/EVAL_NAV/RUN_MANIFEST, generated figures, and raw/provider data remain untracked.

## Commands

The following commands were run in the active repository on branch `paper10e0/basic-dual-yaw-ekf-baseline-freeze`:

- `python3 -m pytest tests/unit/test_paper10e0_basic_dual_yaw_baseline.py -q`
- `cmake --build build/cpp --target legsa_v23_port_core_demo -j2`
- `build/cpp/legsa_v23_port_core_demo --config <PAPER10E0_STAGE_ROOT>/09_input_provider_and_normal_manifest/runtime_configs/BY2_B00_ORIGINAL_KF_GINS_POSITION_ONLY.yaml --output-dir <PAPER10E0_STAGE_ROOT>/runtime_only_large_outputs/BY2/B00_ORIGINAL_KF_GINS_POSITION_ONLY --debug-update-timeline`
- `build/cpp/legsa_v23_port_core_demo --config <PAPER10E0_STAGE_ROOT>/09_input_provider_and_normal_manifest/runtime_configs/BY2_B01_BASIC_DUAL_YAW_EKF.yaml --output-dir <PAPER10E0_STAGE_ROOT>/runtime_only_large_outputs/BY2/B01_BASIC_DUAL_YAW_EKF --debug-update-timeline`
- `build/cpp/legsa_v23_port_core_demo --config <PAPER10E0_STAGE_ROOT>/09_input_provider_and_normal_manifest/runtime_configs/BY3_B00_ORIGINAL_KF_GINS_POSITION_ONLY.yaml --output-dir <PAPER10E0_STAGE_ROOT>/runtime_only_large_outputs/BY3/B00_ORIGINAL_KF_GINS_POSITION_ONLY --debug-update-timeline`
- `build/cpp/legsa_v23_port_core_demo --config <PAPER10E0_STAGE_ROOT>/09_input_provider_and_normal_manifest/runtime_configs/BY3_B01_BASIC_DUAL_YAW_EKF.yaml --output-dir <PAPER10E0_STAGE_ROOT>/runtime_only_large_outputs/BY3/B01_BASIC_DUAL_YAW_EKF --debug-update-timeline`
- `git diff --cached --check`

## Results

- Basic unit tests: passed.
- C++ build target: passed.
- BY2 B00/B01 smoke: completed with runtime exit code 0.
- BY3 B00/B01 smoke: completed with runtime exit code 0.
- BY2 B01 dual-yaw updates: 274, reject 0, downweight 0.
- BY3 B01 dual-yaw updates: 286, reject 0, downweight 0; diagnostic-only yaw.
- source-aware/Go2/QM/Raw Doppler/FGO/QA fallback/final_v23 robust yaw logic in Basic manifests: disabled.
- trace online: false.
- final_v23 output solver input: false.
- degradation matrix: false.
- generated figures: runtime/C export only, not staged.

## Runtime Evidence Files

- `<PAPER10E0_STAGE_ROOT>/08_unit_and_build_tests/PAPER10E0_CPP_BUILD_REPORT.md`
- `<PAPER10E0_STAGE_ROOT>/07_basic_dual_yaw_code_patch/PAPER10E0_YAW_JACOBIAN_SIGN_TEST.md`
- `<PAPER10E0_STAGE_ROOT>/10_BY2_normal_smoke/PAPER10E0_BY2_NORMAL_SMOKE_METRICS.csv`
- `<PAPER10E0_STAGE_ROOT>/11_BY3_normal_smoke/PAPER10E0_BY3_NORMAL_SMOKE_METRICS.csv`
- `<PAPER10E0_STAGE_ROOT>/17_render_QA/PAPER10E0_RENDER_QA_REPORT.md`
- `<PAPER10E0_STAGE_ROOT>/21_export_QA/PAPER10E0_EXPORT_QA_REPORT.md`

## Boundaries

These pointers do not make runtime outputs tracked evidence. They are reproducibility breadcrumbs for reviewers who have access to the local runtime/export roots.
