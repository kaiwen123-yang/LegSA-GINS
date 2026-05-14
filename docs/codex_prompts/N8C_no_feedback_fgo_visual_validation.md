# Codex Prompt: N8C No-Feedback FGO Visual Validation

Run N8C after N8B is merged and tagged.

Do:

- load N8B and N8A2 reports
- rerun missing time series runtime-only if needed
- generate the mandatory N8C figure set
- audit plot data coverage
- review factor contribution
- keep candidate factors diagnostic-only
- create an N8C PR

Do not:

- feed FGO output back into EKF
- replace EKF NAV with FGO output
- use trace/final_v23 as solver inputs
- formalize candidate diagnostic factors
- commit runtime reports or figures
- make a paper performance claim
