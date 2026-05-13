# N8A1 Factor Policy Review

The factor-policy review checks that N8A keeps the active/default factor stack
separate from diagnostic candidate factors.

Active/default factors:

- receiver position
- receiver velocity
- dual yaw
- raw Doppler velocity
- Go2 proprioceptive joint factor
- smoothness

Diagnostic candidates:

- Go2 foot kinematic velocity
- Go2 yaw-rate between factor
- Go2 relative odometry
- contact probability weighting

The review reports candidate leakage, smoothness/yaw factor policy suspects,
and per-factor residual proxies. Diagnostic ablations are runtime-only
engineering probes and are not final policy selection.

Trace/final_v23 outputs are not used to tune FGO weights.
