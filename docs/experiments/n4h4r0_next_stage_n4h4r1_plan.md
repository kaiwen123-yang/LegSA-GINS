# N4H4R1 Controlled Source-Backed Port Plan

## Scope

N4H4R1 will create `cpp/legsa_v23_port_core` as a controlled source-backed
port target. It will not extend the solver with LegSA factors.

## First Implementation Target

- Earth
- Rotation
- core types
- config loading
- readers
- INSMech
- GIEngine
- writers

## Second Target

- build integration
- toy run
- contract manifest
- no reference source compilation

## Third Target

- clean replay parity run
- fresh evaluation against the agreed reference
- gap report if parity fails

Every ported function must carry provenance tags and Chinese comments. N4H4R1
does not implement raw Doppler, Go2 priors, LSIM/OIM, source-aware weighting, or
FGO.

