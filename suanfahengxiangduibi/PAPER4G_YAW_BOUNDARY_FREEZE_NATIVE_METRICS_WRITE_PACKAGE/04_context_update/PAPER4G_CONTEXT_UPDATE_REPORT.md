# PAPER4G Context Update Report

Tracked context files updated by append-only PAPER4G sections:

- `AGENTS.md`
- `PLANS.md`
- `PHASE_LOG.md`
- `CLAIM_BOUNDARY.md`

Update scope:
- freeze external-method body-yaw claims as diagnostic-only after PAPER4F_R2;
- record native DD/LOS baseline/residual/ambiguity/provider metrics as the write-ready external-method route;
- preserve prohibitions on trace online use, receiver IMU as Go2 body IMU, exact/full external reproduction, RTKLIB-as-literature exact reproduction, BY3 yaw generalization, XB severe-GNSS proof, and raw/runtime/external-code staging.

Pre-existing dirty diffs in these context files were observed before PAPER4G. The commit safety process should stage only PAPER4G package files and PAPER4G appended context content, leaving unrelated dirty files unstaged.
