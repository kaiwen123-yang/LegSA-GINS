# GINav BY2 C00 output conversion contract

This contract was fixed before the reference trace was opened. No reference error, coordinate search, sign search, time search, point shift, or bias selection informed it.

## Time

- Native time is GPST `(gps_week, gps_sow)` from the official `.pos` output. `outsol.m:11-16` calls `time2gpst` and prints week/SOW; `outsolhead.m:163-168` identifies the header as GPST.
- Frozen case identity is GPS week 2408. GPS-UTC is fixed to 18 s for 2026-03-06.
- `unix_time_s = 315964800 + gps_week*604800 + gps_sow - 18`.
- With `base_time=1772784000.0`, `relative_time_s=unix_time_s-base_time=gps_sow-460818.0`.

## Position and physical point

- Native position columns are ECEF XYZ metres (`outsolhead.m:171-179`). `udsol_lc.m:13-16` and `ins2sol.m:16-19` convert the INS state LLH to ECEF and emit that position.
- The physical point is the GINav INS mechanization/IMU point. The configured RFU lever arm is used inside the official LC measurement model; this offline conversion applies no evaluator point shift, no antenna translation, and no reference-derived correction.
- LLH is WGS84 geodetic latitude, longitude, ellipsoidal height. WGS84 constants are `a=6378137 m`, `f=1/298.257223563`, matching `ecef2pos.m:3`; degrees are used in the CSV.

## Velocity and navigation frame

- Native XYZ-mode velocity is ECEF m/s: `udsol_lc.m:15`, `ins2sol.m:18`, and `outsol.m:29-46`.
- ECEF velocity is rotated at each emitted WGS84 LLH point to local ENU `[E,N,U]`, using the same axis definition as `xyz2enu.m:3-6` / `xyz2blh.m:11-14`.
- Project local velocity is NED `[N,E,D]=[N,E,-U]`, in m/s.

## RFU to project FRD/NED attitude

- GINav mechanizes in local ENU with body RFU. The frozen input adapter maps Go2 FLU to RFU as `[R,F,U]=[-L,F,U]`; the fixed common lever maps project FRD `[+0.03,+0.03,-0.30] m` to RFU `[+0.03,+0.03,+0.30] m`. These are physical contracts, not reference-selected transforms.
- Coordinate permutation/sign matrix `P=[[0,1,0],[1,0,0],[0,0,-1]]` maps project NED coordinates to native ENU and project FRD coordinates to native RFU. Therefore `C_ned_frd=P^T C_enu_rfu P`.
- The official state angle order is pitch, roll, yaw: `att2Cnb.m:3-8`, `Cnb2att.m:3`, and the emitted header `outsolhead.m:195-198`. The project CSV reorders this to roll, pitch, yaw.
- `udsol_lc.m:16-22` and `ins2sol.m:19-25` convert radians to degrees and emit yaw as `360-internal_yaw` for nonnegative internal yaw, otherwise `-internal_yaw`; equivalently the emitted yaw is `(-internal_yaw) mod 360`. The emitted yaw is retained directly as project NED/FRD yaw; there is no data-dependent wrap/sign choice.
- All attitude columns in the standard CSV are degrees. Roll/pitch are signed; yaw is the official emitted `[0,360)` convention.

## Row/status preservation

- All 80 finite native rows are preserved in original order.
- Q=5 is an official SPP-fed LC update; Q=3 is INS output. Row 0 is the alignment output; `INS_ONLY_DIAGNOSTIC` excludes it, leaving 68 propagation rows.
