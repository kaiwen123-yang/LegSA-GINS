# LC01–LC02 scientific complementarity

The identities are `DISTINCT_COMPLEMENTARY_METHOD`. LC01 exploits two simultaneous receiver positions and the full rigid relative-position vector in an invariant-filter geometry. LC02 consumes one receiver's solution-level position plus its quality metadata; it has no direct baseline-vector heading and instead changes the conventional error-state EKF's measurement covariance and innovation treatment.

Both are loosely coupled and both output navigation states, but that shared layer is not duplication. Their receiver count, information topology, attitude observability source, state/error representation, measurement dimension, quality inputs, and principal failure modes differ. Performance numbers were deliberately excluded from this decision.

This identity finding does not override the reproduction gate: LC02 is scientifically complementary, but the Yin RAEKF branch is not formally admitted until its robust covariance chain is source-closed.
