# N8F Factor Jacobian Contracts

N8F requires each promoted candidate to have a residual/Jacobian/toggle
contract.

Contracts:

- Contact-aware weighting has residual dimension 0 and no state Jacobian.
- Foot kinematic velocity touches `vN/vE`; position and vertical velocity are
  zero in the default Jacobian.
- Yaw-rate between touches `yaw_k/yaw_{k+1}` with `-1/+1` signs.
- Relative odometry between touches `p_k/p_{k+1}` with `-I/+I` signs.

The audit report `FGO_LEGGED_CANDIDATE_FACTOR_CONTRACTS_REPORT.json` must keep:

- `trace_input=false`
- `finalv23_input=false`
- `no_truth_claim=true`
- `paper_performance_claim=false`

