# Dense acquisition scheduling support

The final registered RAWX-rate trial is described in DENSE_SELECTED_LIKELIHOOD_PLAN.md.
This source milestone adds no new real search, navigation or reference evaluation.

The frontend records positive whole-call elapsed time even when a solver raises.
It distinguishes failure before entering CILS and rejects acquisition case IDs
that collide after filename formatting. The serial controller strictly prefers
certificate elapsed time, uses the attempt timer only for invalid no-certificate
attempts, and recognizes explicit invalid preselection failures as zero CILS work.
It separately records registered cost sources, actual simulated CILS starts,
busy drops and serviced no-CILS opportunities. A missing timer for an attempted
search is rejected rather than replaced by zero.

Cadence metadata comes from registered selection-ready timestamps and supports
both the original 2 s and dense 0.2 s spacing. Actual scheduling timestamps are
not rounded. Window width, candidate ownership, permanent release, catch-up,
all numerical models and acceptance thresholds are unchanged.

Validation in Ubuntu 22.04 WSL: 52 controller/review tests passed, plus three
frontend exception-timing/preselection tests passed. These are synthetic tests,
not additional real CILS calls. The source is frozen before the 1191-window run.
