# N7C3 Bounded Adaptive Go2 Horizontal Velocity Std

N7C3 revises the Go2 horizontal velocity prior uncertainty policy for PR #38.
It keeps the measurement Jacobian unchanged and changes only row-wise `R` and
update eligibility.

Policy:

- base std: `1.5 m/s`
- minimum std: `1.0 m/s`
- normal maximum std: `3.0 m/s`
- diagnostic extreme cap: `5.0 m/s`
- No std greater than `5 m/s` is allowed in the bounded policy.
- `std_vd=999.0` and vertical disabled remain mandatory.

Confidence-to-std mapping:

- `confidence >= 0.80`: `std_vn=std_ve=1.0`
- `confidence >= 0.60`: `std_vn=std_ve=1.5`
- `confidence >= 0.35`: `std_vn=std_ve=2.5`
- `confidence >= 0.15`: `std_vn=std_ve=4.0`
- otherwise: `update_flag=false` with a diagnostic `5.0 m/s` cap

Boundary:

- Go2 velocity is not truth.
- std is measurement uncertainty, not speed command.
- No trace/final_v23 tuning.
- No paper performance claim.
- No output-only correction, no epoch deletion, no FGO.
