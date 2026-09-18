# T5bc v3 candidate pilot — preregistration

Status: **HUMAN_AUTHORIZED_PREREGISTRATION**. Authorization: `T5bc prompt 2026-09-19`. Start commit: `404b252eba9f87941b4c93a79deff76fcfa730b5`. This record is outside the frozen v2.1 chain. Real native/evaluator/trace calls remain **0** at preparation; no calibration or performance result is claimed here.

## Authorized matrix and definitions

The contract records D1–D8 and every ID in the existing 61-case definition: C00_clean_normal and D01_seed_00 through D60_seed_00. Three-sequence runs are F04-R5σ/F04-R5W and B3 F02′/A04′/F04′: 15 native. The 61-case BY2 subset has F04-R5/R5σ/R5W/B3: 244 native. Two candidate scalar-mode BY2/C00 F02/F04 identity runs precede providers and the matrix. Maximum budget is 261 native and 518 evaluator calls, with no retries. Only evaluator children may open trace, exactly once per invocation.

The raw heading uses common-iTOW HPPOSECEF GNSS2 minus GNSS1, fixed NED, double-fixed validity and the frozen A1 conversion. Model length is 0.35 m. R5 keeps 2.933193 degrees. R5σ is constant; R5W uses per-epoch pAcc. B3 predicts C_nb[0,-0.35,0] and uses isotropic k_b² S covariance. B3 scalar yaw_valid is zero on every GNSS row. F02 scalar-weight variants are excluded because its frozen parser guard and basic path do not support them.

BY2 1 s pairs determine all applied values: sigma²=Var(r_psi)/2; k²=Var(r_psi)*0.35²/mean(S_second+S_first); k_b²=trace(Cov(r_vector))/(6*mean(S_second+S_first)). The scalar residual subtracts installed gyro-z integration. The vector residual uses starting raw yaw and frozen RP to map the integrated body rotation to NED. No floor, clipping, trimming or search is applied. The 0.2 s results, BY2H/BY2O calibrations and three S bins are report-only. Residuals contain gyro, initial-heading and RP mapping motion error.

## Provenance and gates

`T5BC_FROZEN_SOURCE_INDEX.yaml` pins all sequence configurations and all 61 frozen F04 case configurations, providers, archive/terminal receipts, comparator tables and T5a R5 providers. Runtime configurations are cloned by exact line replacement only; YAML round trips are forbidden. Only gnsspath and the four B3-required additions may change. Actual effective options must match the 211 frozen static options with explicitly declared path/model differences.

Candidate SHA256: `cbf554baf9c83490e40b207b97f04ef77f51d9962f7bce463f1e644416ef789e`. Frozen SHA256: `96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c`. Candidate use is restricted to B3 and the two identity gates. The latter require exact retained NAV_10HZ.csv.gz bytes and effective-option equality before any matrix solve. Evaluation retains the frozen sequence-specific point-conversion lengths, base times, windows, trace and --std policy, distinct from the new 0.35 m measurement model.

The 18 C++ synthetic tests include numerical Jacobian and scalar/B3 small-angle equivalence. The maximum observed Jacobian difference is 8.8819e-11; the yaw-correction difference is 1.32339e-13 rad. The historical initial circular-angle assertion failure is preserved; only its angle-difference assertion was repaired after continuation authorization. These are synthetic implementation checks, not native budget usage or real-data identity evidence.

Final validation: **255 distinct tests passed** (187 joint + 68 calibration/provider/aggregate; includes 18 C++ synthetic tests and 27 T5a regressions). The 14 environment warnings concern Matplotlib/pyparsing and unused Axes3D. Independent read-only review closed the scientific, role-filtering, classification and archive-batch issues. Follow-up metadata-only row bindings have targeted regression coverage. These counts consume no real native/evaluator/trace budget.

## Preregistered bookkeeping decisions

- All 61 cases remain included. Frozen non-yaw columns and IMU/RD/RP/HV bytes survive; original yaw/A1 fault columns are replaced by the new raw input. No equivalent B3 fault is invented, and no original heading injection is claimed to survive.
- D57 retains its irregular frozen time grid. Exact raw-grid matches within 1 microsecond are used; unmatched rows are invalid, without nearest matching or interpolation. A zero-input formal activation failure is classified separately from all attempted updates being rejected.
- Frozen D37 failed before producing an effective-options echo. D36 supplies a declared witness only after a byte proof of exactly five metadata/path-line differences. No historical D37 echo or metrics are fabricated.
- Frozen subset C00 retains real_clean. D01–D60 retain their authoritative outer semisynthetic roles; the historical native config/echo flags are recorded separately.
- R5W NIS is measured after scheme-C and before source-aware scaling, using dz without Hdx subtraction. B3 NIS uses dz-Hdx before its NIS gate and source-aware policy. Coverage is descriptive, and negative/missing values are explicitly accounted for.
- The subset summary uses absolute RMSE P95 for the worst-five-percent threshold. Paired differences require available same-case rows. Failed metrics remain unavailable across the complete canonical schema.

## Delivery plan

Output directories follow 01_CALIBRATION, 02_IDENTITY_GATE, 03_PROVIDER_TABLES, 04_NATIVE_C00_SEQ, 05_NATIVE_SUBSET61, 06_EVAL/v3 and v2, 07_AGGREGATE, 08_FIGURES and 09_HANDOFF under the independent task root. Writes begin on ext4 scratch and are hash-verified into G:. Pre/post checkpoints protect frozen inputs, binary, evaluators, 28 figures and render manifest.

Final delivery will include complete CSV tables and differences, calibration, identity, gating/NIS, BY2O segment results, independent figures and manifest, factual narrative, a bookkeeping appendix, and a complete ZIP with member SHA256/CRC and whole-package SHA256/bytes. Frozen v2.1 is not replaced. Heading-family injection, HV source changes and A1/A2 family reimplementation remain separately preregistered v3 work.
