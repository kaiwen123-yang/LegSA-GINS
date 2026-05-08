# final_v23 Deep Source Map

This document defines the N4H2C deep source-audit surface. It intentionally uses
role names instead of local absolute paths.

## Source Roles

- external source root: `EXTERNAL_KF_GINS_ROOT`
- actual final_v23 case root: `ACTUAL_FINAL_V23_CASE_ROOT`
- N4H2 artifacts root: `N4H2_ARTIFACTS_ROOT`

## External Git Provenance

The runner records external source evidence at runtime. Tracked docs do not
commit local path strings or copied source.

- remote: recorded in runtime probe if available
- branch: recorded in runtime probe if available
- commit: recorded in runtime probe if available
- external source copied: false

## Located Source Targets

N4H2C searches for:

- `process_data.py`
- final_v23 run scripts
- final_v23 config candidates
- `GIEngine`
- `GnssFileLoader`
- `INSMech`
- `kf_gins.cpp`

The committed source map does not claim all targets are currently present. The
runtime report `PROCESS_DATA_DEEP_AUDIT.json`,
`FINAL_V23_ENGINE_SOURCE_AUDIT.json`, and `KFGINS_CORE_FLOW_AUDIT.json` carry
the exact path and line-number evidence outside git.

Runtime probe summary for the current N4H2C run:

- actual final_v23 case root: `evidence_missing`
- actual `input.gnss`: missing
- process_data path role: `EXTERNAL_KF_GINS_ROOT/bin/process_data.py`
- run script candidates: 173
- config candidates: 40
- `GnssFileLoader` / runtime GNSS column support: position, std, velocity,
  velocity std, yaw, and yaw std evidence found
- GIEngine velocity update evidence: found
- GIEngine yaw update evidence: found
- KF-GINS core flow matrix: all requested flow terms found in external source
  evidence
- unavailable runtime keyword: `E001_single_nominal_none`

## Evidence Missing Policy

If a file or keyword is not found, N4H2C records `evidence_missing`. It must not
invent a final_v23 command, historical hash, or runtime branch claim.

## Boundary

- trace is evaluation-only
- final_v23 is not proposed
- no external source is copied
- no formal performance claim
