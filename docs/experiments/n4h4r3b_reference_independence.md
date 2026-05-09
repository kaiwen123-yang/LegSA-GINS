# N4H4R3B Reference Independence

The source-backed port solver may read clean IMU and clean GNSS input. DUAL_FINAL_V23_REFERENCE and reconstructed reference files are evaluation-only.

The reference-independence audit fails if final_v23 NAV/STD, trace output, or a reference reconstructed from port output enters the solver. Clean GNSS must not be used as evaluation truth for the R3B metric screen.

The expected contract is:

- clean GNSS as solver measurement: allowed
- DUAL_FINAL_V23_REFERENCE as evaluation reference: allowed
- final_v23 output as solver input: forbidden
- trace solver input: forbidden
- reference built from port output: forbidden

No paper performance claim is made.
