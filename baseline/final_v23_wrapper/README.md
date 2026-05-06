# final_v23-style Baseline Wrapper

This directory contains the Stage N1 wrapper skeleton for a final_v23-style mature GNSS/INS baseline.

The wrapper role is limited to:

- mature GNSS/INS backbone reference;
- strong baseline;
- evaluator sanity oracle.

It is not the proposed LegSA-GINS method.

N1 does not implement LegSA-ESKF, raw Doppler factors, source-aware weighting, or fixed-lag smoothing.

Until real final_v23 output files and dataset paths are connected, this wrapper remains:

wrapper_only_until_real_final_v23_output_is_connected
