# PAPER4A Diagnostic-Only Table

| Evidence | Diagnostic use | Reason |
|---|---|---|
| PAPER1F dual-antenna heading-aided adapters | Historical adapter coverage and blocked-row explanation. | Not five faithful external literature reproductions. |
| PAPER3A raw common-epoch provider | Provider evolution start point. | No LOS/DD design matrix or ambiguity backend. |
| PAPER3A-R1 yaw frame sensitivity | Explains why yaw metrics are blocked. | Frame transform not physically closed. |
| RTKLIB moving-base outputs | External software baseline diagnostics. | No yaw/baseline-vector field for body attitude claim and not a literature reproduction. |
| Baseline-heading degrees in PAPER3E/F/G/H | Frame-sensitivity diagnostics. | Baseline heading is not accepted body yaw. |
| PAPER3I Pavlasek native diagnostic provider | IEKF boundary evidence. | Full IEKF blocked by physical extrinsics and time alignment. |
| PAPER3I Wu EQKF/misalignment rows | EQKF/PAR/ADOP diagnostic evidence. | Full misalignment/body-yaw closure disabled. |
| BY3 yaw outputs | Stress-dataset diagnostic narrative only. | BY3 yaw remains diagnostic-only. |
| XB/PG severe-GNSS outputs | Stress and QA motivation. | No high-precision severe-GNSS proof. |
