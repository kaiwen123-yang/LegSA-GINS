# PAPER10G_R3 Current Context

Stage: `PAPER10G_R3_LSE_FIDELITY_UPGRADE_RAW_FK_OFFICIAL_ADAPTERS`

Status: `CONDITIONAL_PASS_URDF_LOCKED_RAW_JOINT_BLOCKED`

## What R3 Upgraded

- The Go2 URDF zip was found, hash-locked, and extracted only in runtime storage.
- The primary Go2 URDF parsed successfully with a fallback XML parser.
- Four Go2 leg chains were locked from base to foot frames:
  FL, FR, RL, and RR each have hip, thigh, calf, and foot fixed-link chain evidence.
- URDF mesh files are not required for FK-chain identity.

## What R3 Could Not Upgrade

- BY2/BY3 raw lowstate joint `motor_state.q/dq` was not proven available.
- Lowstate motor order could not be mapped to the URDF joint order.
- Raw FK provider CSVs were not generated.
- `sportmodestate.foot_position_body` remains a high-level kinematic proxy and must not be called raw joint FK.
- R2A repaired proxy metrics remain the numeric LSE comparison source.

## Official Adapter Status

- LSE01 Hartley official exact remains blocked: official availability does not equal a Go2 official adapter run.
- LSE02/LSE03 can remain formula-level/proxy implementations only until raw FK closes.
- LSE04 remains below full GTSAM/iSAM2 closure because local GTSAM was unavailable and raw FK is blocked.
- LSE05 tracking-camera branch remains blocked because no synchronized tracking-camera/VIO velocity source was proven.

## C1-C9 Claim Repair

- C1 author-official exact: `BLOCKED_WITH_PROOF`.
- C2 raw joint encoder plus URDF FK: `BLOCKED_WITH_PROOF`.
- C3 Hartley official InEKF: `BLOCKED_WITH_PROOF`.
- C4 GTSAM/iSAM2 contact factor graph: `BLOCKED_WITH_PROOF`.
- C5 Teng tracking-camera branch: `BLOCKED_WITH_PROOF`.
- C6 LSE absolute yaw: `REMAINS_FORBIDDEN_BY_PHYSICS_OR_DATA_CONTRACT`.
- C7 LegSA-GINS universal superiority over LSE: `REMAINS_FORBIDDEN_BY_PHYSICS_OR_DATA_CONTRACT`.
- C8 Go2 yaw/position truth: `REMAINS_FORBIDDEN_BY_PHYSICS_OR_DATA_CONTRACT`.
- C9 BY3 ordinary yaw generalization: `REMAINS_FORBIDDEN_BY_PHYSICS_OR_DATA_CONTRACT`.

## Safety Facts

- No Go2 yaw or Go2 position was used as truth.
- No GNSS dual-yaw was input to LSE methods.
- Trace was not used online.
- No final_v23 output or LegSA-GINS output was used as solver input.
- No DA, LC, GINav, MATLAB, RTKLIB, LegSA final matrix, degradation matrix, complete FGO, output substitution, bad-epoch deletion, or per-case tuning was run.
- URDF zip, extracted URDF tree, raw data, figures, and runtime-heavy outputs remain untracked.

## Next Route

- Recommended next stage remains `PAPER10H_XB_PG_QM_BOUNDARY_DIAGNOSTIC`.
- PAPER10H should focus on severe-GNSS source-risk and QM state/action/recovery evidence, not high-precision main-performance or universal-superiority claims.
