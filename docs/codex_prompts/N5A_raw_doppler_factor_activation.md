# Codex Prompt: N5A Raw Doppler Factor Activation

Goal: implement the first proposed factor after source-backed backbone parity, `raw_doppler_auxiliary_factor`.

Strict boundary:

- NAV-PVT velocity is not raw Doppler.
- `.gnss vn/ve/vd` remains baseline receiver-native velocity.
- RAWX `doMes` plus satellite-state provider is required.
- RTKLIB is runtime-only mature tooling; do not commit raw data, RTKLIB files, ephemeris, generated NAV/STD/figures, or local paths.
- If provider is missing, mark a blocker and do not claim the factor was applied.
- No trace solver input.
- No final_v23 output solver input.
- No output-only correction, tuning, epoch deletion, LSIM/OIM, Go2 prior, or FGO.
- No paper performance claim and no outperform final_v23 claim.
