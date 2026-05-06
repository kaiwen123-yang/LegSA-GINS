# final_v23 Baseline Wrapper

## Role

final_v23 is used as:

- mature GNSS/INS backbone reference;
- strong baseline;
- evaluator sanity oracle.

It is not the proposed method.

## Separation Rule

final_v23 outputs must be stored under:

results/baselines/final_v23/

Proposed method outputs must be stored under:

results/proposed/

The proposed solver must not read final_v23 trajectory output.

## N1 Scope

N1 creates wrapper scripts, manifests, output contracts, and audit tests.

N1 does not implement LegSA-ESKF, Doppler factors, source-aware weighting, or fixed-lag smoothing.

## Evidence Status

Until real final_v23 output files and dataset paths are connected, N1 is wrapper-only.

Do not claim numerical performance in N1.
