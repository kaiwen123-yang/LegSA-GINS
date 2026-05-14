# N8G FGO Feedback EKF Foundation

N8G starts after N8F1 merged and tagged.

It adds a controlled feedback path from sliding-window no-feedback FGO terminal
states into the EKF as pseudo-measurements/error-state corrections.

Boundary:

- FGO feedback enters the EKF update path.
- FGO output is not copied over EKF NAV.
- Feedback observations use no future data.
- Covariance and gates are conservative and not trace/final_v23 tuned.
- Runtime NAV/STD/EVAL_NAV/RUN_MANIFEST are generated under runtime output dirs.
- This is engineering diagnostic evidence, not a paper performance claim.
