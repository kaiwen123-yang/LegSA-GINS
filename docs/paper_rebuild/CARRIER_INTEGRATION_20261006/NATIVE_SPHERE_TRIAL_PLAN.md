# Optional native scalar sphere kernel: bounded real-input check

The exact Python sphere solver remains the default. An opt-in C++ scalar secular-root kernel uses the same bracket, hard-case distinction, near-pole delta variable, 300-iteration limit and stopping criteria. Weight eigendecomposition and the final ECEF baseline/objective calculation remain on the Python side. No fast-math or fused contraction is permitted. ABI/kernel version and compiled library SHA identify each result.

The synthetic prototype checks 2100 inputs (2076 matching finite results and 24 shared numerical failures). Its isolated whole-sphere speed measurement is not a whole-CILS or real-time claim.

After the focused opt-in tests pass, run exactly four real CILS calls: Python and native for the original full-nuisance six-class problems at starts 168 and 318 seconds, using REAL_100_340_V2, cap six, 100000 nodes and 30 seconds. Start 168 exercises the slow candidate that expired before completion; 318 was just certified by caching after a prior timeout. This is a selected development performance sample, without reference-based selection.

Use sequential single-thread numerical libraries and alternate backend order between the two problems. Compare both certified full integer vectors, baselines and objective costs at the existing tolerances; retain timeouts as censored. Any certified disagreement stops adoption pending diagnosis. Solver time includes backend loading, hashing and factor setup. All four outputs remain separate from the earlier 18-call caching benchmark.

No admission, tracking, navigation or reference evaluation runs in this bounded backend test. The registered preselected-likelihood trial uses Python and is a separate scientific objective; the native kernel test keeps the original full likelihood and nuisance integers. Default V3 and earlier outputs are preserved.
