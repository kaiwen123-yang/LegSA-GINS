# Receiver-Native Update Contract

N4 implements receiver-native position, velocity, and heading updates as the
baseline backbone of the LegSA-GINS C++ filter core.

## Included In N4

- Receiver-native position update.
- Receiver-native velocity update.
- Receiver-native heading update.
- Error-state feedback and reset for the updated diagonal slots.
- Toy-run output through NAV / STD / EVAL_NAV / RUN_MANIFEST.

## Not Included In N4

- Receiver-native heading is not self raw heading.
- Raw Doppler is deferred to N5.
- Go2 weak priors, support/contact features, LSIM/OIM, and source-aware
  weighting are deferred to N6.
- FGO and smoothing are deferred to N7.
- trace remains evaluation-only and is not solver input.
- final_v23 output remains baseline evidence and is not proposed solver input.
