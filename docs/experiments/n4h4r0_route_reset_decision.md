# N4H4R0 Route Reset Decision

## Decision Summary

The original project target is unchanged: build a final_v23-style mature
GNSS/INS backbone, then add the LegSA nine-factor enhancement system after the
backbone has clean replay parity.

The route changes because the self-written LegSA-v23-core parity attempt failed
real clean replay. The failure is useful evidence, but it is not a stable
backbone for the next factor stages.

## New Route

The next route is a source-backed controlled port of the final_v23/KF-GINS core
flow. The ported backbone is a baseline/backbone implementation, not paper
novelty and not the proposed contribution.

Proposed innovation starts only after port parity is demonstrated. Until then:

- no raw Doppler factor
- no raw pseudorange factor
- no Go2 weak prior
- no LSIM/OIM
- no source-aware weighting
- no FGO
- no performance claim

## Boundary

The final_v23/KF-GINS reference remains a source-backed reference. Its outputs
must not become proposed solver input. Trace remains evaluation-only. Failed
PR #21 evidence must stay visible and must not be rewritten as a pass.

