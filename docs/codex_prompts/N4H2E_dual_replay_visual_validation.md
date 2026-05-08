# N4H2E dual_final_v23-only visual validation prompt

Goal: generate a dual_final_v23-only visual validation bundle for the fresh replay parity result.

Rules:

- Use role aliases for runtime artifact roots.
- Do not commit raw data, official artifacts, replay artifacts, generated figures, or generated large reports.
- Do not draw pure INS, single antenna, or multi-line comparison figures.
- Do not modify solver output.
- Keep trace evaluation-only.
- Keep manual_visual_review_required=true.
- Do not make a formal paper performance claim.
- Report roll/pitch relaxed status separately from strict status.
- Keep yaw gate strict at <=2.0 deg.

