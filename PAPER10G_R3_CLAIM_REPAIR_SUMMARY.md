# PAPER10G_R3 Claim Repair Summary

| claim_id | status | reason |
| --- | --- | --- |
| C1 | BLOCKED_WITH_PROOF | official exact code not run for all methods; Hartley official example is Matlab/Simulink and MATLAB is forbidden; other official adapters not locked |
| C2 | BLOCKED_WITH_PROOF | URDF parsed and FK chains locked, but BY2/BY3 raw lowstate motor q/dq not found |
| C3 | BLOCKED_WITH_PROOF | official code found online but sample/adapter not run; MATLAB forbidden and raw FK blocked |
| C4 | BLOCKED_WITH_PROOF | local GTSAM missing and raw FK blocked |
| C5 | BLOCKED_WITH_PROOF | no tracking-camera/VIO velocity input found |
| C6 | REMAINS_FORBIDDEN_BY_PHYSICS_OR_DATA_CONTRACT | no global heading reference in LSE inputs; yaw about gravity remains unobservable |
| C7 | REMAINS_FORBIDDEN_BY_PHYSICS_OR_DATA_CONTRACT | task mismatch: LegSA-GINS is global GNSS/INS PNT with dual-yaw, LSE is local proprioceptive odometry |
| C8 | REMAINS_FORBIDDEN_BY_PHYSICS_OR_DATA_CONTRACT | Go2 yaw/position are diagnostic-only |
| C9 | REMAINS_FORBIDDEN_BY_PHYSICS_OR_DATA_CONTRACT | BY3 yaw remains diagnostic-only without new ordinary-yaw reference evidence |
