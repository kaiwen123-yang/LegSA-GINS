# N8E Final Ablation Matrix

The matrix contains 22 required rows:

- 5 EKF front-end module rows
- 7 no-feedback FGO backend rows
- 5 diagnostic removal rows
- 5 diagnostic candidate-factor rows

Each row records run status, source of result, active factors, diagnostic-only
status, no-feedback status, metric namespace, available H/Up/Yaw/Roll/Pitch
engineering deltas, factor notes, and caveat notes.

Rows derived from no-feedback FGO remain engineering deltas against EKF outputs.
They are not used to feed back EKF state, replace EKF NAV, or claim paper-level
performance.
