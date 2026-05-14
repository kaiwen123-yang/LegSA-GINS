# N8E Formal Ablation With Caveat Prompt

Goal:

- Build the N8E formal engineering ablation matrix.
- Summarize EKF front-end and no-feedback FGO backend module contributions.
- Preserve the Raw Doppler FGO active-but-low-marginal-value caveat.
- Generate runtime-only reports and figures.
- Keep claim boundaries explicit.

Required boundaries:

- Do not use trace/final_v23 as solver input.
- Do not use trace/final_v23 output for FGO weight tuning.
- Do not feed FGO output back into EKF.
- Do not replace EKF NAV with FGO output.
- Do not commit runtime artifacts or figures.
- Do not commit raw data.
- Do not make a paper performance claim.
- Do not claim outperform final_v23.
- Do not rewrite low marginal value as failure.
