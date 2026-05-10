# Codex Prompt: N5B RTKLIB Doppler Provider Activation

N5B follows N5A, where raw Doppler activation path code existed but real activation was blocked by missing satellite-state or Doppler velocity export.

The task is to build a runtime-only RTKLIB Doppler velocity provider, generate `RAW_DOPPLER_VELOCITY_FACTORS.csv`, feed it into the source-backed EKF as a real auxiliary velocity factor, and report either `completed_enabled` with `raw_doppler_update_count > 0` or a precise blocker with helper compile/run logs.

Boundaries:

- RTKLIB position solution is not LegSA solver input.
- NAV-PVT velocity is not raw Doppler.
- `.gnss` velocity is not raw Doppler.
- final_v23 output and trace are not solver input.
- No LSIM/OIM, Go2 prior, FGO, source-aware weighting, output-only correction, tuning, epoch deletion, paper performance claim, or outperform-final-v23 claim.
