# final_v23 Artifact Recovery

N4H2C-2 searches runtime-only roots for actual final_v23 artifacts:

- `ACTUAL_FINAL_V23_CASE_ROOT`
- `EXTERNAL_KFGINS_ROOT`
- `HOME_ROOT`
- `MNT_C_USERS_YKW`
- `MNT_C_USERS_86187`

Tracked docs use role aliases only. Runtime JSON may contain full local paths in
`/tmp`.

## Searched Artifacts

- `input.gnss`
- `KF_GINS_Navresult.nav`
- `KF_GINS_STD.txt`
- `KF_GINS_IMU_ERR.txt`
- `summary.json`
- `error_series.csv`
- `case_review.md`
- process_data yaw calibration reports

## Runtime Snapshot

The N4H2C-2 runtime search writes full paths only to `/tmp`; this tracked
document records role aliases and group identifiers only.

- artifact_groups_found: 71
- best_final_v23_candidate_group: `EXTERNAL_KFGINS_ROOT:10`
- candidate_rank_evidence: `nominal_none_path`, `single_case_path`
- actual input.gnss recovered: true
- actual summary recovered: true
- contains NAV / STD / error_series: true
- input.gnss lines: 303
- NAV lines: 56642
- STD lines: 56642

The originally supplied `ACTUAL_FINAL_V23_CASE_ROOT` remains
`evidence_missing`, but runtime recovery found a nominal-none candidate group
under the external-source role. This is enough to compare actual candidate
input against the N4H2 reconstructed input, but it is still diagnostic evidence
rather than a committed artifact.

## Remaining Risk

Recovered artifacts must stay runtime-only. If future evidence shows the
recovered candidate is not the intended final_v23 nominal input, the report must
preserve that as `evidence_missing` rather than silently upgrading the claim.

## Boundary

- no artifact is copied into git
- no raw data is committed
- no performance claim
