# Method Section Plan

1. System and source roles: GNSS raw/status data as observations, Go2 body/high-level data as proprioceptive observations, trace as evaluation-only reference, final_v23 as external reference baseline only.
2. Dataset protocol: define BY2, BY3, and XB/PG roles and state which claims each dataset can and cannot support.
3. Quality-aware measurement management: describe the seven recognized QA methods and their shared backend policy without claiming exact external system reproduction.
4. Provider construction: describe raw CSV to UBX/RTCM/RINEX, common epoch/satellite matching, GPS DD/LOS, GPS+BDS provider v3, and provider v4 residual-ready metadata.
5. Literature modules: present Teunissen/Liu/Yang/Wu/Pavlasek/RTKLIB as PDF-grounded native/proxy/backend-level implementations or diagnostics with implementation-level labels.
6. Evaluation and claim boundary: define main_text, appendix, diagnostic_only, blocked, and forbidden claims before showing results.
