# 2026-10-05 author clarification and work contract

This record fixes the scope of the current evidence review. Historical run results and the original V3 matrix remain frozen; later evidence is added with its own provenance. The author requests a complete horizontal-comparison acceptance review and progress toward IEEE TIM. Plot redesign is deferred to a separate conversation at the author's request.

## Author-confirmed facts

- Only BY2 was used for parameter tuning. BY2H and BY2O were not used for development according to the author. The record audit must distinguish numerical parameter tuning, protocol/window selection, and retrospective inspection; it must not silently equate them or invent blinding.
- The Fixposition camera side faces the robot front.
- Event alignment observes **GNSS receiver position/velocity and robot body IMU** after a deliberate kick. It does not use the commercial fused reference trajectory as the alignment signal. The author describes coincident motion onset as the algorithm-start criterion.
- The supplied mechanical designs represent the same installed structure used for collection. Later modification/save dates reflect subsequent saving and organization, not a changed mounting design.

These are author statements, not estimates obtained from the sensor records. Exact per-session offset values, whether BY2/H/O each had a separately selected event, drift, latency, physical survey uncertainty, and installed firmware identity have not been confirmed by these answers.

## Work now authorized

1. Preserve original measurements and V3 results; read existing code, manifests, configurations, and histories to establish what was done.
2. Inspect provided CAD/URDF/manual and eight new logs plus the receiver ZIP. Determine whether the recordings support useful validation before scheduling estimator runs.
3. Accept each horizontal comparison against its actual implementation, inputs, output definition, support and failure accounting, and original-paper differences. Poor performance alone neither invalidates an implementation nor proves general algorithm superiority.
4. Develop the TIM measurement model, uncertainty input ledger, correlation treatment, and source-backed manuscript text. Nominal CAD transforms and illustrative uncertainty values must not be promoted to calibration evidence.
5. Commit and push each completed small evidence block. The root agent exclusively controls Git staging, commits, and pushes.

No new estimator experiment or plot is implied by this document. New analyses must state their input identity and preserve the distinction between archived results, current evidence extraction, and proposed validation.