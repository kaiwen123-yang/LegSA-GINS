# N4H4R1 Source-Backed Port Foundation

N4H4R1 adds `cpp/legsa_v23_port_core` as a controlled source-backed port-core
foundation from the final_v23/KF-GINS reference.

R1 is not solver novelty. It is a backbone implementation foundation with
provenance headers, manifest flags, CMake targets, a toy dry-run, audits, and
tests. It does not run real clean replay parity and does not make a paper
performance claim.

The old `cpp/legsa_v23_core` remains a diagnostic/self-written attempt. It is
not deleted, and it is not treated as the final backbone.

R2/R3 will handle mathematical completion and clean replay parity. Only after
backbone parity can factor work begin.

R1 does not implement:

- raw Doppler
- raw pseudorange
- Go2 priors
- LSIM/OIM
- source-aware weighting
- FGO

