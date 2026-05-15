# N9A R1 Source Lineage

N9A_R1 records BY2 normal-condition source roles with aliases only:

- `<BY2_FIXPOSITION_ROOT>` is the Fixposition data root used at runtime.
- `<GNSS1_RAW>` and `<GNSS2_RAW>` are raw dual-antenna GNSS streams.
- `<GNSS1_STATUS>` and `<GNSS2_STATUS>` are status, solution, and relative yaw
  observation streams.
- `<TRACE_TRUTH>` is truth/reference/evaluation only and is not solver input.
- `<GO2_BODY_IMU_HIGHLEVEL>` is the fused Go2 body IMU/high-level source.
- `<FIXPOSITION_IMU_DATA>`, `<FIXPOSITION_IMU_BIASES>`, and
  `<FIXPOSITION_IMU_TEMP>` are receiver IMU diagnostics only.
- `<NTRIP_INFO>`, `<NTRIP_LATENCY>`, `<CORR_RAW>`, `<TF>`, and `<TF_STATIC>`
  support correction, NTRIP, transform, and output-chain audit.

This role separation is the main correction over the initial N9A run. The
initial run did not find the user-specified raw/status/trace/by2 source files
and therefore could not support a BY2 normal-condition source-chain audit.

Go2 position, Go2 yaw, Go2 contact, and Go2 velocity are not truth. Fixposition
receiver IMU data is not the fused body IMU. Trace remains evaluation-only.
