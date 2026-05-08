# N4H4D LegSA-v23 Clean Replay Parity

N4H4D is the first real clean status-yaw replay for the LegSA-owned
`legsa_v23_core` filter. The stage runs process-data-compatible clean `.imu`
and `.gnss` inputs through the self-owned v23-core runtime, then evaluates the
result against the dual_final_v23 official reference.

This is engineering baseline parity only. It is not a proposed factor result,
not a final paper performance claim, and not final_v23 output substitution.

Allowed evidence:

- LegSA-v23-core `--config` clean replay outputs.
- Fresh evaluation against the dual official reference.
- Comparison to external KF-GINS clean replay summary.
- Gap-screen diagnosis when parity fails.

Forbidden actions:

- trace as solver input;
- final_v23 outputs as proposed solver input;
- output-only correction;
- bad epoch deletion;
- tuning to trace;
- raw Doppler, raw pseudorange, Go2 priors, LSIM/OIM, source-aware weighting,
  FGO, FGO feedback, or Neural Gate.

If N4H4D fails parity, the correct outcome is an explicit gap classification
and recommended next debugging stage. Visual validation is reserved for the
later stage if parity passes.
