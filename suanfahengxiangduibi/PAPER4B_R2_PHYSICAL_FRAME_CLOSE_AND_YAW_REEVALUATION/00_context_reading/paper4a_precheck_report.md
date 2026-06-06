# PAPER4A Precheck Report

PAPER4A is treated as the write-ready evidence package. It does not authorize body-yaw RMSE, yaw superiority, exact reproduction, or same-evaluator superiority claims. PAPER4B_R2 does not rewrite PAPER4A's boundary; it only adds new physical-frame evidence and offline yaw reevaluation under a fixed physical transform.

PAPER4B_R2 allowed scope:

- Accept user-confirmed GNSS1/GNSS2 physical order and official extrinsics as frame evidence.
- Recompute derived body-yaw offline metrics from historical baseline-heading diagnostics where native yaw semantics are closed.
- Preserve trace as offline evaluator only.
- Keep exact/full faithful external reproduction and final_v23/LegSA_QA superiority claims forbidden.
