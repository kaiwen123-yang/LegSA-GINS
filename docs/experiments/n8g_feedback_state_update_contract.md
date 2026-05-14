# N8G Feedback State Update Contract

FGO feedback observations are represented as runtime-only
`FGO_FEEDBACK_OBSERVATIONS.csv` rows.

The C++ port-core loads those rows only when `enable_fgo_feedback=true`.

The update contract is:

- residual is computed from current EKF state minus feedback observation;
- yaw residual is wrapped;
- conservative covariance forms `R`;
- gated rows call `EKFUpdate`;
- the normal `stateFeedback` path applies the accumulated error state;
- no code path assigns FGO output directly to NAV state.
