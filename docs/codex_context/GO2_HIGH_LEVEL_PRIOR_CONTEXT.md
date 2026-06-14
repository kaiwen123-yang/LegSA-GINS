# Go2 High-Level Prior Context

PAPER10C establishes the safe Go2 role:

- allowed weak priors: roll/pitch and horizontal velocity;
- diagnostic metadata: mode, gait, contact/support/readiness, and motion-state labels;
- forbidden truth sources: Go2 position and Go2 yaw;
- disabled main constraint: Go2 vertical velocity;
- prohibited framing: full contact-aided InEKF, full leg odometry, support-foot FK, or Go2 replacing dual-antenna GNSS yaw.

The runnable PAPER10C candidate is `G04_GO2_RP_HVEL` under fixed `SA04_N6B_POLICY`.

Current blocked items:

- readiness/motion-state is not first-class LSIM metadata;
- BY3 Go2 prior provider evidence is missing in the current workspace;
- BY3 yaw remains diagnostic-only.

Safe wording:

`Go2 high-level body state provides conservative roll/pitch and horizontal-velocity weak priors for LegSA-GINS under a fixed source-aware policy. BY2 controlled degradation supports bounded auxiliary-prior evidence, while readiness/motion-state quality management and BY3 Go2 runtime remain future work.`
