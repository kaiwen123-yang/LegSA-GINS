# Prior Yin-code provenance

The bounded search covered the current tracked repository, current Git history, current project documentation, the existing CLEAN4 comparison stage, explicitly identified older paper-comparison archive names, and the historical report supplied in the task. Search tokens were `Yin2023`, `YIN2023`, `RAEKF`, `RAKF`, `Robust Adaptive Extended Kalman Filter`, `PDOP`, `measurement factor Q`, `IGGIII`, `Huber`, `LC07`, `PAPER9C`, `120/120`, and `rs15174125`. It did not scan unrelated disks and did not execute old code.

Commit `62976baa` contains the legacy alias `qa11g_yin2023_improved_R_rakf_EKF`. Its declared family is generic `covariance_matching`, with `k0=1.0`, `k1=4.0`, `gain=1.0`, and `exact_reproduction=false`. The shared rule scales covariance quadratically after a threshold. It does not implement Yin's 21-state EKF/AKF/RKF/RAEKF branches, `PDOP^2 Q r^2`, IGGIII thresholds `1.15/4.45`, or the printed state and covariance fusion.

The legacy configuration also sets `source_aware_trace_enabled=true` and is therefore trace-capable. This is an online-boundary incompatibility with the clean LC02 contract; it is not evidence that any historical runtime actually opened trace. Its provider also permits position, velocity, and yaw sources rather than the single-receiver, position-only contract closed here.

Decision: the prior project code is `PAPER_DERIVED_SIMPLIFICATION_NOT_FULL_REPRODUCTION`. It is not an active reusable LC02 implementation. A small static utility could be recovered only after a fresh equation-to-code audit, but no prior online provider, branch implementation, or runtime output is admitted.

Provenance labels: historical code observations are `PRIOR_PROJECT_CODE`; the non-reuse decision is `PAPER_DERIVED`.
