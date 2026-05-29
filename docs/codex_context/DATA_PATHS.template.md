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
<BY3_FULL_MATRIX_ROOT>=
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
- BY3 generalization outputs use the `BY3_*` aliases, including `<BY3A4A_STAGE_ROOT>` for the lateral yaw repair memory-lock stage.
- BY2 degradation reporting/archive outputs use `<BY2_DEGRADATION_ARCHIVE_ROOT>` and text-summary outputs use `<BY2_DEGRADATION_TEXT_SUMMARY_ROOT>`.
- Do not use local paths in claim text or committed scripts unless the user explicitly approves.
