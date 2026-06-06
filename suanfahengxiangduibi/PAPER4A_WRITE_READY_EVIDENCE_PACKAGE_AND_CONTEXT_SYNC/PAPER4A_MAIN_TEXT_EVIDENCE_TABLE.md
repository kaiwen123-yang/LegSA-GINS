# PAPER4A Main Text Evidence Table

| Topic | Main-text use | Evidence status | Required boundary |
|---|---|---|---|
| Dataset-role-aware stress protocol | Use BY2 as the full-metric main dataset, BY3 as poor-heading/position-up stress with diagnostic yaw, and XB/PG as poor-GNSS stress/motivation. | `MAIN_TEXT_ALLOWED` | No BY3 yaw-generalization or XB high-precision severe-GNSS claim. |
| BY2 120 canonical degradation families | Describe the canonical BY2 matrix design reused by PAPER2A and PAPER3E/F/G/H. | `MAIN_TEXT_ALLOWED` | Do not imply every external method has full faithful reproduction. |
| PAPER2A QA full matrix | Describe 7 recognized QA methods and completed BY2/BY3/XB coverage; state trace online and receiver-IMU-as-body-IMU were false. | `MAIN_TEXT_ALLOWED` | No exact external QA system or superiority claim. |
| RTKLIB/RINEX reconstruction | Describe raw CSV to UBX/RTCM/RINEX reconstruction, Linux RTKLIB build, common epoch/satellite preflight, and GPS DD/LOS provider construction. | `MAIN_TEXT_ALLOWED` | RTKLIB moving-base remains external software diagnostic. |
| Provider evolution to v4 | Use provider evolution from common-epoch preflight to GPS-only DD/LOS, GPS+BDS v3, and provider v4 residual-ready evidence. | `MAIN_TEXT_ALLOWED` | Galileo/GLONASS/SBAS blockers must be stated. |
| Method/evidence classification matrix | Show methods as main-text classification, not performance superiority. | `MAIN_TEXT_ALLOWED` | External literature modules stay native/proxy/backend-level unless exact reproduction is later proven. |
| Forbidden-claim boundary table | Include a concise table of body-yaw, exact reproduction, superiority, BY3 yaw, XB severe-GNSS, trace-online, and receiver-IMU boundaries. | `MAIN_TEXT_ALLOWED` | Must not be softened into claims. |
| Internal baseline coverage | Mention joinable error-series coverage only as context for blocked same-evaluator figures. | `MAIN_TEXT_ALLOWED_WITH_LIMIT` | No same-evaluator superiority claim. |
