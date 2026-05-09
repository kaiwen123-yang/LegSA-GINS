# N4H4R0 Source-Backed Port Policy

## Allowed

A source-backed port is allowed when it is controlled, provenance-preserving,
and audited. The goal is to create a mature GNSS/INS backbone that can later
host LegSA factors.

## Required Controls

- Source provenance is required for every ported module.
- License status must be checked before source-backed implementation work.
- A module manifest is required before N4H4R1 implementation.
- Critical C++ functions require Chinese comments.
- final_v23 output must not be used as solver input.
- Trace remains evaluation-only.
- Generated data and generated results are excluded from Git.
- Clean/noisy input provenance must be preserved.
- The ported backbone is not paper novelty.

## Forbidden

- Uncontrolled source copying is forbidden.
- Reference source must not be compiled from `reference/final_v23_repo`.
- final_v23/KF-GINS must not be described as the proposed method.
- PR #21 failure metrics must not be reframed as a pass.
- Diagnostic variants must not be used as formal performance results.

