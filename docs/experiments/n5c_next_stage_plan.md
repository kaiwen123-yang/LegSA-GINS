# N5C Next Stage Plan

N5D is selected from the N5C decision report:

- `ablation_ready`: run raw Doppler visual validation and stress protocol.
- `noise_model_needed`: inspect covariance, residual gating, and robust weighting candidates without source-aware weighting claims.
- `alignment_issue`: repair raw Doppler factor time alignment against the clean replay update schedule.
- `source_integrity_issue`: re-audit RTKLIB helper/provider provenance and forbid copied NAV-PVT or `.gnss` velocity.
- `activation_failed`: return to raw Doppler activation or loader alignment.

N5D must preserve the same boundaries: no paper performance claim, no outperform final_v23 claim, no trace solver input, no final_v23 solver input, no output-only correction, no epoch deletion, and no LSIM/OIM, Go2 prior, source-aware weighting, or FGO.
