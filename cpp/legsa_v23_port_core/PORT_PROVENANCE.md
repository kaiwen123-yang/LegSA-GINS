# Port Provenance

- Source repository: `kaiwen123-yang/KF-GINS-graduation-design`
- Source role: final_v23/KF-GINS reference backbone
- Source commit: `5a4471efd4fcfcdc31e258a677af354c652ff16f`
- Port target: `cpp/legsa_v23_port_core`
- Port method: controlled source-backed refactor into LegSA-owned files with
  provenance headers and Chinese comments.

This port is a mature GNSS/INS backbone implementation target, not paper
novelty and not the proposed factor contribution. final_v23 output is not
solver input. Trace remains evaluation-only. Generated data and generated
results are excluded from Git. Clean/noisy provenance must be preserved.

N4H4R1 was the minimal compileable foundation and toy dry-run stage.

N4H4R2 completes the source-backed mathematical port surface inside the
LegSA-owned port target: Earth/Rotation, unit conversion, 7-column IMU loading,
15-column GNSS loading, INS mechanization, GIEngine update flow, EKF
predict/update, state feedback, writers, and synthetic mathematical smoke.
Clean replay parity is still not attempted in R2; N4H4R3 is the first stage
allowed to make an honest clean replay pass/fail decision.
