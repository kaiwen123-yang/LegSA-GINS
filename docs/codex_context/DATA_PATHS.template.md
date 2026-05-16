# DATA_PATHS.template.md

Copy this template to `DATA_PATHS.local.md` for local machine use. Do not commit local absolute paths by default.

## Workspace Aliases

```text
<WINDOWS_AUDIT_ROOT>=
<WSL_AUDIT_ROOT>=
<WSL_ALGO_REPO>=
<BY2_PLOT_AUDIT_ROOT>=
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
- Do not use local paths in claim text or committed scripts unless the user explicitly approves.
