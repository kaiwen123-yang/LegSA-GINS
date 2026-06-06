# PAPER4A Figure And Table Plan

## MAIN_TEXT_CANDIDATE

1. Dataset-role-aware stress protocol overview: BY2 main, BY3 poor-heading/position-up stress with diagnostic yaw, XB/PG poor-GNSS stress and QA motivation.
2. QA behavior and coverage table from PAPER2A: seven recognized QA methods, BY2/BY3/XB row coverage, trace_used_online=false, receiver_imu_data_as_body_imu=false.
3. Provider evolution diagram: raw CSV to UBX/RTCM/RINEX to common epoch/satellite to GPS-only DD/LOS to GPS+BDS provider v3 to provider v4 residual-ready evidence.
4. Method/evidence classification matrix: main_text / appendix / diagnostic_only / blocked / forbidden claim.
5. Forbidden-claim boundary table: body-yaw, exact reproduction, same-evaluator superiority, BY3 yaw, XB severe-GNSS, trace online, receiver IMU.

## APPENDIX

1. Teunissen/Liu/Yang/Wu native/proxy/fullish module metric bars from PAPER3F/G/H/I, labelled as PDF-grounded native/proxy/backend-level implementations.
2. LAMBDA/MLAMBDA helper integration and ambiguity validation summaries.
3. Provider v4 system/frequency coverage table with GPS/BDS rows and non-GPS blockers.
4. Pavlasek IEKF native diagnostic provider and Wu EQKF/PAR/ADOP diagnostic summaries.
5. Internal baseline error-series coverage table for final_v23, single_antenna, and pure_INS, with no superiority claim.
6. RTKLIB moving-base external software diagnostic table.

## DIAGNOSTIC_ONLY

1. Yaw transform sensitivity and frame-gap diagnostics from PAPER3A-R1/PAPER3B/PAPER3I.
2. Baseline-heading diagnostics not converted to body yaw.
3. BY3 yaw diagnostic-only explanation and any BY3 yaw-related plots.
4. XB severe-GNSS/high-precision diagnostic outputs and QA motivation views.
5. Reduced external algorithm rows that are not exact/full faithful reproductions.

## BLOCKED_UNTIL_FRAME_OR_INTERNAL_JOIN

1. Body-yaw RMSE comparison.
2. final_v23 versus external algorithms superiority bar.
3. Same-evaluator trajectory overlays that imply superiority.
4. BY3 yaw-generalization plots.
5. Any Galileo/GLONASS/SBAS full-provider closure plot.
