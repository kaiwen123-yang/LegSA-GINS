# Exact solver cache benchmark

Before new real searches, freeze a paired comparison on the same prepared five-epoch problems: cap=6 at starts 100,110,148,168,182,318,330,336 seconds and cap=8 at 168 seconds. These cover fast cases, the known long-lived but late candidate, and original timeouts. Selection uses saved runtime/availability, never reference error. This is a diagnostic sample, not a population speed estimate.

Baseline source is dbf340a, exported to the WSL scratch benchmark directory. Candidate changes only covariance-factor caching and cheap-bound pruning already justified by the original lower bound. Full objective, original integer nuisance parameters, selected class identity, tolerances and certification requirement remain unchanged.

At most 18 new CILS calls, one baseline and one candidate per problem, sequential with one BLAS/OMP thread. Alternate execution order by case index. Same 100000-node/30-second limit. Preserve timeout outcomes as censored; never divide a timeout threshold by a completed runtime and call that a measured speedup. No future validation, native navigation or reference reads are included.

Compare selected labels, certificate status, both selected integer classes and objective costs (tolerance 2e-6 + 2e-8 times cost scale). Full-vector differences are acceptable only when demonstrated to be equal-cost ties within the same two classes. Any unaccounted certified result disagreement stops adoption. Measure whole solve and reported solver time separately; report per-case results without extrapolating to real-time operation. Mathematical regression tests must pass before this benchmark starts.

This plan changes no prior replay result. A quicker solver is still insufficient for real-time qualification without acquisition scheduling, preparation/validation/tracking cost and actual measurement availability accounting.
