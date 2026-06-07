# PAPER4G Git Safety Report

Commit hash: `not_committed_in_report_generation`.

Allowed staging scope:
- `suanfahengxiangduibi/PAPER4G_YAW_BOUNDARY_FREEZE_NATIVE_METRICS_WRITE_PACKAGE/**`
- `AGENTS.md`
- `PLANS.md`
- `PHASE_LOG.md`
- `CLAIM_BOUNDARY.md`

Forbidden staging scope:
- raw receiver data
- UBX/RTCM/RINEX/NAV/OBS/RNX files
- `_runtime/`
- `_external_code/`
- external source code
- large epoch payloads

Pre-existing dirty files were observed before PAPER4G. The commit process must not include unrelated dirty files outside the explicit scope.
