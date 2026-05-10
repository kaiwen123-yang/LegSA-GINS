# N5D Decision

N5D decides whether raw Doppler has enough visual and stress-protocol evidence
to be treated as a candidate source for the next source-aware weighting stage.

Decision outcomes:
- source/time issue -> N5E_source_or_time_alignment_fix;
- clean gross degradation -> N5E_noise_or_gating_fix;
- clean neutral or improved plus stress benefit -> N6A_source_aware_LSIM_OIM_weighting_foundation;
- clean neutral or improved plus weak stress evidence -> N6A_source_aware_weighting_with_raw_doppler_as_candidate_source;
- consistent degradation -> N5E_raw_doppler_noise_gating_fix.

Boundary:
- Receiver velocity stress variants are diagnostic-only.
- R-scale and STD-scale screens are not tuning claims.
- No LSIM/OIM, Go2 prior, or FGO is implemented by N5D.
- No paper performance claim.
- No outperform final_v23 claim.
