# LC01 versus Chang scientific complementarity

The methods are structurally complementary. LC01 extracts direct extended-pose information from two receiver positions and their rigid relative vector inside an invariant EKF. Chang uses one GNSS receiver’s solution-level velocity and position in a conventional 15-state error filter, then tries to respond to model mismatch through innovation history, parallel chi-square tests, fuzzy smoothing factors, and strong-tracking covariance inflation.

Shared use of an IMU and GNSS solution data does not make them duplicate method identities. Their receiver count, state representation, measurement dimension, direct geometric attitude information, observability source, adaptation mechanism, and failure modes differ.

This identity decision uses no performance number. `DISTINCT_COMPLEMENTARY_METHOD` does not override Chang’s formal NO-GO: a scientifically distinct candidate may still be unreproducible from its sources.
