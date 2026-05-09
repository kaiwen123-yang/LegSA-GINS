# N4H4D3 Decision

`N4H4D3_DECISION_REPORT.json` determines the next stage.

If source-backed audit and guarded replay pass, the next stage is visual
validation for the LegSA-v23 core. If replay partially improves, the next stage
targets the remaining yaw/update gap. If there is no material improvement, the
next stage revisits mechanization or time alignment.

No output-only correction, tuning, epoch deletion, trace solver input, or
performance claim is allowed.

