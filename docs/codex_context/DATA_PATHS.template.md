# DATA_PATHS.template.md

Copy this template to `DATA_PATHS.local.md` for local machine use. Do not commit local absolute paths by default.

## Workspace Aliases

```text
<WINDOWS_AUDIT_ROOT>=
<WSL_AUDIT_ROOT>=
<WSL_ALGO_REPO>=
<BY2_N9B2_WINDOWS_ROOT>=
<BY2_N9B2_WSL_ROOT>=
<BY2_N9B2_FULL_MATRIX_ROOT>=
<BY2_N9B2_DEFERRED_EXT4_ROOT>=
<BY3_OUTPUT_ROOT>=
<BY3_STAGE_ROOT>=
<BY3A1_STAGE_ROOT>=
<BY3A2_STAGE_ROOT>=
<BY3A3_STAGE_ROOT>=
<BY3A4A_STAGE_ROOT>=
<BY3A4C_STAGE_ROOT>=
<BY3A5B_STAGE_ROOT>=
<BY3A6_STAGE_ROOT>=
<BY3A7_STAGE_ROOT>=
<BY3A8_STAGE_ROOT>=
<BY3B_STAGE_ROOT>=
<BY3C_STAGE_ROOT>=
<BY3_FULL_MATRIX_ROOT>=
<XB1_OUTPUT_ROOT>=
<XB1_STAGE_ROOT>=
<XB1A1_STAGE_ROOT>=
<XB1A2_STAGE_ROOT>=
<XB1_FULL_MATRIX_ROOT>=
<XB1A1_NORMAL_GATE_ROOT>=
<XB1A2_RELPOS_DIFF_REPAIR_ROOT>=
<XB1_EXPORT_CLEAN_ROOT>=
<PG_MULTI_REVIEW_ROOT>=
<PG_MULTI_A0_STAGE_ROOT>=
<PG2_XB2_RECEIVER_ROOT>=
<PG2_XB2_BODY_SOURCE>=
<PG3_XB3_RECEIVER_ROOT>=
<PG3_XB3_BODY_SOURCE>=
<PG4_XB4_RECEIVER_ROOT>=
<PG4_XB4_BODY_SOURCE>=
<BY2_DEGRADATION_ARCHIVE_ROOT>=
<BY2_DEGRADATION_TEXT_SUMMARY_ROOT>=
```

## BY2 Fixposition / GNSS Sources

```text
<BY2_FIXPOSITION_ROOT>=
<GNSS1_RAW>=
<GNSS2_RAW>=
<GNSS1_STATUS>=
<GNSS2_STATUS>=
<TRACE_TRUTH>=
<FIXPOSITION_IMU_DATA>=
<FIXPOSITION_IMU_BIASES>=
<FIXPOSITION_IMU_TEMP>=
```

## Go2 Body / High-Level Source

```text
<GO2_BODY_IMU_HIGHLEVEL>=
```

## BY3 Sources

```text
<BY3_RECEIVER_ROOT>=
<BY3_GO2_BODY_SOURCE>=
<BY3_TRACE_TRUTH>=
<BY3_FIXPOSITION_IMU_DATA>=
<BY3_GNSS1_RAW>=
<BY3_GNSS2_RAW>=
<BY3_GNSS1_STATUS>=
<BY3_GNSS2_STATUS>=
```

## XB1 Sources

```text
<XB1_RECEIVER_ROOT>=
<XB1_BODY_SOURCE>=
<XB1_TRACE_TRUTH>=
<XB1_FIXPOSITION_IMU_DATA>=
<XB1_GNSS1_RAW>=
<XB1_GNSS2_RAW>=
<XB1_GNSS1_STATUS>=
<XB1_GNSS2_STATUS>=
```

## PG Multi-Repeat Poor-GNSS Sources

```text
<PG2_XB2_RECEIVER_ROOT>=
<PG2_XB2_BODY_SOURCE>=
<PG3_XB3_RECEIVER_ROOT>=
<PG3_XB3_BODY_SOURCE>=
<PG4_XB4_RECEIVER_ROOT>=
<PG4_XB4_BODY_SOURCE>=
```

## Auxiliary Sources

```text
<NTRIP_INFO>=
<NTRIP_LATENCY>=
<CORR_RAW>=
<TF>=
<TF_STATIC>=
<USER_IO_RAW>=
<USER_IO_STATUS>=
<USER_IO_OUT_ODOM_STATUS>=
<USER_IO_OUT_POI_GEODETIC>=
<USER_IO_OUT_POI_ODOMETRY>=
<USER_IO_OUT_POI_SMOOTH_ODOMETRY>=
```

## Notes

- Keep real absolute paths only in `DATA_PATHS.local.md`.
- Use aliases in tracked docs and reports.
- Runtime outputs remain untracked.
- Future BY2/N9B outputs use the `BY2_N9B2_*` aliases.
- BY3 generalization outputs use the `BY3_*` aliases, including `<BY3A4A_STAGE_ROOT>` for the lateral yaw repair memory-lock stage, `<BY3A4C_STAGE_ROOT>` for the git-history yaw-reference reconstruction stage, `<BY3A5B_STAGE_ROOT>` for the A1 dual-diff yaw-input repair stage, `<BY3A6_STAGE_ROOT>` for the trace-truth/initatt/gate forensic stage, `<BY3A7_STAGE_ROOT>` for the A1 yaw dynamic-quality / IMU gate repair stage, `<BY3A8_STAGE_ROOT>` for the yaw error-budget safe-repair stage, `<BY3B_STAGE_ROOT>` for position/up degradation planning with diagnostic yaw, and `<BY3C_STAGE_ROOT>` for approved Batch0-Batch3 position/up degradation execution.
- XB1 poor-GNSS generalization outputs use `<XB1_OUTPUT_ROOT>`, `<XB1_STAGE_ROOT>`, `<XB1A1_STAGE_ROOT>`, `<XB1A2_STAGE_ROOT>`, `<XB1_FULL_MATRIX_ROOT>`, `<XB1A1_NORMAL_GATE_ROOT>`, `<XB1A2_RELPOS_DIFF_REPAIR_ROOT>`, and `<XB1_EXPORT_CLEAN_ROOT>`. XB1 receiver/body sources use `<XB1_RECEIVER_ROOT>` and `<XB1_BODY_SOURCE>`.
- PG multi-repeat poor-GNSS review outputs use `<PG_MULTI_REVIEW_ROOT>` and `<PG_MULTI_A0_STAGE_ROOT>`. PG2/PG3/PG4 receiver/body sources use only their `PG*_XB*` aliases in tracked docs.
- BY2 degradation reporting/archive outputs use `<BY2_DEGRADATION_ARCHIVE_ROOT>` and text-summary outputs use `<BY2_DEGRADATION_TEXT_SUMMARY_ROOT>`.
- Do not use local paths in claim text or committed scripts unless the user explicitly approves.
