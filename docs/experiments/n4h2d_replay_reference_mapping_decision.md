# N4H2D Replay Reference Mapping Decision

N4H2D decides whether the old N4H2 yaw=93 summary is invalidated by fresh evaluation against the reconstructed dual official reference.

The decision report records:

- selected official reference sign
- actual dual summary reproduction status
- fresh replay summary and target gates
- old summary versus fresh summary difference
- stale summary evidence
- reference mapping mismatch evidence
- baseline replay parity status
- recommended next stage

Possible next stages:

- `N4H3_controlled_final_v23_reference_import`
- `N4H3_reference_import_with_yaw_near_gate_caveat`
- `N4H2D_official_error_series_schema_fix`
- `N4H2C_runtime_yaw_update_config_audit_continue`

Yaw gate remains strict at <= 2.0. Near-gate evidence is not a pass.
