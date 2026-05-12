# N6B1 Source-Aware Visual Validation

N6B1 is a post-N6B visual validation stage for the refined source-aware
LSIM/OIM policy.

N6B table diagnostics passed, but table summaries alone cannot expose local
curve breakage, source-specific R-scale behavior, spike-response visibility, or
empty figures. N6B1 therefore checks clean curves, weight traces, spike zooms,
stress variants, and plotted-data coverage.

N6B1 does not modify solver math, tune thresholds, delete epochs, apply
output-only correction, add Go2 priors, add FGO, or make paper performance
claims.

Runtime paths are supplied only by command-line role aliases. Tracked docs,
configs, and scripts must not hardcode local absolute runtime paths.
