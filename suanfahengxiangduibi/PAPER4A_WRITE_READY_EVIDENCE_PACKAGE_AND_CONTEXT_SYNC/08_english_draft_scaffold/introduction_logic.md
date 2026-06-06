# Introduction Logic

1. Legged robots need GNSS/INS fusion that can handle intermittent GNSS, degraded position quality, and proprioceptive observation limits.
2. A single dataset cannot support all claims, so the paper uses a dataset-role-aware stress protocol: BY2 for full-metric matrix evidence, BY3 for poor-heading/position-up stress, and XB/PG for severe poor-GNSS boundary analysis.
3. The paper should present quality-aware measurement management behavior through recognized GNSS/INS QA modules rather than claiming exact external system reproduction.
4. Dual-antenna literature evidence should be framed as PDF-grounded native/proxy/backend-level implementations and DD/LOS-backed literature module diagnostics.
5. The provider chain is a contribution to reproducible evidence: raw receiver logs to RINEX, common epoch/satellite checks, DD/LOS providers, covariance/residual metadata, and explicit non-GPS blockers.
6. The limitations should be explicit: physical body-yaw frame closure, exact external reproduction, same-evaluator superiority, BY3 yaw generalization, and XB severe-GNSS high-precision proof are not closed.
