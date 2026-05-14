# N8E Raw Doppler FGO Caveat

Raw Doppler FGO is active as a solver-visible factor after N8C3.

N8D records low marginal value for Raw Doppler in the current no-feedback FGO
setting. This is a caveat, not an activation failure.

This caveat does not invalidate Raw Doppler EKF front-end evidence. The likely
engineering interpretation is that Raw Doppler is consistent with, or dominated
by, receiver velocity and smoothness in the current no-feedback backend.

The caveat must stay attached to N8E summaries. It must not be rewritten as a
failed Raw Doppler factor and must not be upgraded into a paper performance
claim.
