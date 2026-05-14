# Codex Prompt: N8B FGO Factor Graph Policy Review

Run N8B on the branch stage/N8B-fgo-factor-graph-policy-review after N8A2 is merged and tagged.

Do:

- build the N8B policy grid
- run real no-feedback FGO policy ablations
- review smoothness policy
- review factor weights
- review diagnostic candidate factors
- generate runtime-only figures and reports
- commit and open an N8B PR

Do not:

- merge PR #21
- delete smoothness as a final shortcut
- use trace/final_v23 as solver input or weight-tuning input
- feed FGO output back into EKF
- replace EKF NAV with FGO output
- commit runtime reports or figures
- make a paper performance claim
