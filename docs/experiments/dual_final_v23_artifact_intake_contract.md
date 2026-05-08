# dual_final_v23 artifact intake contract

Manual artifacts live outside the repository under the role alias
`DUAL_FINAL_V23_ARTIFACT_ROOT`.

Required runtime files:

- `input.gnss`
- `KF_GINS_Navresult.nav`
- `KF_GINS_STD.txt`
- `summary.json`
- `error_series.csv`

Optional runtime files:

- `KF_GINS_IMU_ERR.txt`
- `case_review.md`

The intake module validates required-file completeness, file sizes, line counts,
and summary classification. Runtime reports may contain actual paths; tracked
docs and configs must not.

No artifact file may be copied into tracked docs, results, paper packages, or
source directories. No artifact file may be committed.
