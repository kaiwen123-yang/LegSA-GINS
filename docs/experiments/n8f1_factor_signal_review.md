# N8F1 Factor Signal Review

N8F1 checks whether each newly activated factor has visible engineering signal.

Reviewed signals:

- Contact-aware weighting: R scale varies over time and remains a weighting
  signal, not contact truth.
- Foot kinematic velocity: residual and whitened residual proxies are finite and
  toggles affect solver residual dimensions.
- Yaw-rate between: wrapped between residual proxy is finite and not an absolute
  yaw truth claim.
- Relative odometry between: increment residual proxy is finite and not an
  absolute Go2 position factor.
- Candidate stack: gross degradation flags remain absent.

Signal states are `informative`, `weak_but_active`, `unstable`, or `inactive`.

