
# Hartley claim boundary

Scientific terminal: `PASS_LSE01_COMPLETE_WITH_REFERENCE_EXTRINSIC_LIMITATION`.

## What is complete

- IJRR 2020 reported backend reproduction on 63,277 real BY2 native state rows; 63,276/63,276 propagation and Eq. 61 calls.
- Seven-member yaw-gauge ensemble (reference + six non-zero offsets). All six comparisons pass at full precision. Maximum matched-contact position residual across runs ranges from 3.9206810879312983e-08 to 1.8977692824628012e-07 m.
- Five numerical-observability windows. Ideal 4-contact windows have rank/nullity 17/4 in dimension 21; ideal 2-contact windows have 11/4 in dimension 15. Bias-augmented 4-contact windows have 23/4 in dimension 27; bias-augmented 2-contact windows have 17/4 in dimension 21. Rank/nullity is stable at 0.1×/1×/10× threshold.
- The structural nullspace is exactly four dimensions: three global translations plus one gravity-axis yaw.
- 24 topology-conditioned NIS groups are preserved; 63,177/63,177 update factorizations succeed. NIS is not collapsed across contact count, exact contact set, dynamic/static, and no-update topology.

## What this proves

Hartley provides `global translation gauge`, `global yaw gauge`, `real-data gauge equivalence`, and `numerical observability` evidence. It demonstrates why global yaw and translation are unobservable without external anchoring; it does not demonstrate poor performance by a large yaw RMSE.

## What cannot be compared

`absolute_position_RMSE = null` and `absolute_yaw_RMSE = null`. The Go2 body-IMU to Fixposition POI/BODY fixed extrinsic and the reference attitude framework are not closed. The H7/H7C lineage state `BLOCKED_LSE01_H7C_REFERENCE_LINEAGE_CONTRADICTED` is retained as a reference-extrinsic limitation archive, not an active algorithm blocker and not a reason to mark the reproduction incomplete. Hartley cannot enter an absolute position/yaw flat ranking against LC or internal methods.
