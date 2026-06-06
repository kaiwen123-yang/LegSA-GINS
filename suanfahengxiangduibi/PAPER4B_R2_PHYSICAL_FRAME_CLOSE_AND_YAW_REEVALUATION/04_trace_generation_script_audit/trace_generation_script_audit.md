# Trace Generation Script Audit

Known trace generation facts recorded for PAPER4B_R2:

- The bag export script described by the user uses bagpy to recursively scan `<REFERENCE_BAG_ROOT>` for `.bag` files and exports topics to CSV.
- The trace generation script reads `user_io-out-poi_geodetic.csv`, including `p.vector3.x/y/z`, `Time`, and `ypr.vector3.x/y/z`.
- The generated trace columns are `time, lat, lon, height, processed_lat, processed_lon, processed_height, yaw, pitch, roll`.
- Trace yaw is the raw `ypr.vector3.x` output. `yaw2standard(yaw)` is used only for lever-arm Cbn rotation, not for the final trace yaw field.
- `deltp_bs = [[0,0,0]]`; therefore the lever-arm correction is effectively zero for the generated trace.

Evaluator field policy in this stage:

- Use raw numeric `time` and `yaw` only for offline yaw error evaluation.
- Do not use trace as solver input.
- Do not use `processed_lat`/`processed_lon` blindly; the available trace sample has longitude-like values in `processed_lat` and latitude-like values in `processed_lon`, consistent with prior BY3A6 caution.
- The potential bug `lon, lat, alt = pm.ecef2geodetic(x, y, z); return lat, lon, alt` remains recorded as an evaluator-field caution if any evaluator consumes processed fields. PAPER4B_R2 does not consume processed lat/lon for yaw metrics.
