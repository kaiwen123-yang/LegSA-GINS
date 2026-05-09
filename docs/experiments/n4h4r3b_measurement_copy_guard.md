# N4H4R3B Measurement-Copy Guard

NAV and EVAL_NAV must be written from the port filter state. They must not be copied from clean GNSS measurements, DUAL_FINAL_V23_REFERENCE, trace output, or any final_v23 output.

The guard aligns NAV/EVAL_NAV with clean GNSS only to detect exact-copy behavior. Close-to-measurement output is not automatically valid, and exact or near-zero residual across nearly all GNSS epochs is suspicious.

This is a diagnostic check only: no output substitution, no output-only correction, no tuning, no epoch deletion, and no performance claim.
