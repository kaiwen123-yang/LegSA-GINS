# PAPER10C_R1A Resume Summary

final_status: CONDITIONAL_PASS_RESUME_MANIFEST_READY_BUT_NOT_EXECUTED

PAPER10C_R1A recovered the interrupted PAPER10C_R1 runtime without rerunning from scratch and without overwriting completed rows. The recovery scan found that the active R1 evidence lives under `<PAPER10C_R1_STAGE_ROOT>`; the prompt-listed R1 worktree and R1 C export were not present.

## Counts

- BY2 planned rows: 720
- BY2 completed-evaluable rows: 720
- BY3 planned rows: 720
- BY3 completed-evaluable rows from actual outputs: 543
- BY3 missing rows: 169
- BY3 partial/corrupted rows: 8
- BY3 rows still requiring future resume: 177

## Gate

Runner execution was not started because the environment gate found Windows E free space below the user-defined 50GB threshold. The wrapper was created but not executed.

## Safety

- completed rows overwritten: false
- trace online used: false
- Go2 position/yaw used as truth: false
- final_v23 or LegSA output used as solver input: false
- per-case tuning: false
- external DA/LC/GINav/MATLAB/RTKLIB/contact-aided/complete FGO: not run
