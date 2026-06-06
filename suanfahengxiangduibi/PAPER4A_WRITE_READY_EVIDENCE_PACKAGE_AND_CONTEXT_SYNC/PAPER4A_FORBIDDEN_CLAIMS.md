# PAPER4A Forbidden Claims

These claims remain forbidden after PAPER4A unless a later explicitly reviewed report closes the relevant evidence gap.

| Claim | Status | Current proof boundary |
|---|---|---|
| Body-yaw RMSE from external methods | `FORBIDDEN_CLAIM` | Physical body-yaw frame remains blocked through PAPER3I. |
| Yaw superiority | `FORBIDDEN_CLAIM` | Yaw metric validity is false for PAPER3E/F/G/H and user evidence is required in PAPER3I. |
| final_v23, LegSA_QA, or LegSA_full superiority in a same evaluator | `FORBIDDEN_CLAIM` | PAPER3I internal baseline join is summary/diagnostic only; LegSA_full and LegSA_QA provenance is blocked. |
| Exact reproduction of external algorithms | `FORBIDDEN_CLAIM` | PAPER3A/F/G/H/I use module, proxy, native diagnostic, or backend-level evidence only. |
| Five full faithful external dual-antenna algorithms | `FORBIDDEN_CLAIM` | PAPER3A reports exact faithful reproductions=0; later stages still preserve boundaries. |
| BY3 ordinary yaw generalization | `FORBIDDEN_CLAIM` | BY3 yaw is diagnostic-only. |
| XB severe-GNSS high-precision proof | `FORBIDDEN_CLAIM` | XB/PG are stress/QA-motivation datasets, not proof of high-precision performance. |
| RTKLIB moving-base equals Teunissen/Yang/Liu/Wu reproduction | `FORBIDDEN_CLAIM` | RTKLIB moving-base is external software diagnostic. |
| Trace used online | `FORBIDDEN_CLAIM` | Trace remains evaluation-only; PAPER2A reports trace_used_online=false. |
| Receiver imu-data.csv used as Go2 body IMU | `FORBIDDEN_CLAIM` | Receiver IMU remains diagnostic-only; PAPER2A reports receiver_imu_data_as_body_imu=false. |
| Full contact-aided or joint-foot kinematic constraint claim | `FORBIDDEN_CLAIM` | Full backend and ablation proof remain outside PAPER4A. |
| Full Galileo/GLONASS/SBAS provider closure | `FORBIDDEN_CLAIM` | PAPER3I records Galileo NAV, GLONASS FDMA/satpos, and SBAS model blockers. |
