# Native scalar sphere kernel: bounded real comparison

All four registered CILS calls completed. The 168-second problem is certified in both backends; whole-solve time changes from 5.774050 to 1.175303 seconds (4.913 times on this one paired run).

The 318-second native solve certifies in 5.450653 seconds. This round's Python solve reaches its 30-second limit without certification, so its completion speedup is censored. The earlier cache benchmark had certified this exact problem in 29.702 seconds; that saved certified result is used only to verify the two integer vectors, baseline and objective, never substituted into the new timing pair.

Both native certificates agree with the available Python-certified integer pairs and objectives. Maximum objective differences are 0 and 0. This is floating-point agreement at registered tolerances, not a bitwise or cross-platform proof. All nuisance integers, likelihood, subset and search limits remain unchanged. Four new searches; no future validation, tracking, native navigation or reference reads.

The optional library uses strict flags and ABI/kernel checks; its SHA is recorded in the CSV and each solver certificate. Default Python behavior remains available. Two selected problems do not establish population runtime, end-to-end availability or real-time qualification.
