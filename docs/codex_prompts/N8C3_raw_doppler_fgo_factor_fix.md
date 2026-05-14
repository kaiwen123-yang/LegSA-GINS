# N8C3 Codex prompt summary

Goal: fix RawDopplerVelocityFactor activation in the no-feedback FGO solver
residual vector.

The fix must prove factor rows, residual rows, nonzero Jacobian entries,
velocity-state-block touch, raw_doppler_off removal, residual-dimension delta,
and diagnostic weight-sensitivity reruns.

Forbidden actions:

- do not merge PR #41;
- do not create N8C or N8C3 tags;
- do not create a new PR;
- do not enter N8D;
- do not modify EKF;
- do not feed FGO output back to EKF;
- do not replace EKF NAV with FGO output;
- do not use trace/final_v23 for solver input or weight tuning;
- do not commit runtime outputs or figures;
- do not make a paper performance claim.

Runtime paths must be command-line arguments only.  Tracked docs, configs,
scripts, and tests use role aliases.
