# Exact-search covariance cache and cheap-bound preprune

Implemented on 2026-10-06 in Ubuntu-22.04 WSL. No new real-data CILS, evaluator,
reference read, navigation run, or parameter selection was performed by this
implementation task. Real-data timing is reserved for the separately registered
9-problem / 18-call controlled benchmark.

## Scope and unchanged scientific contract

- `horizontal_literature/ext01_clambda.py`: `BaselineSphereMetric` retains the
  existing sphere hard-case / secular-root kernel. It owns read-only covariance
  inverse and eigensystem factors. Centers and lengths are supplied separately
  on every call. Public `constrained_baseline` keeps its validation order and
  signature. Exact minimum-eigenspace equality, signed tiny projections,
  bracket, 300-iteration cap, stopping tolerance and length checks are unchanged.
- `carrier_phase/solver.py`: each solve caches constant conditional leaf metrics
  and lazily caches `(depth, epoch)` relaxed-bound metrics. The full observation
  residual and objective-decomposition check still run for each scored integer.
- Before the existing exact marginal sphere bound, discard a child only when
  `ambiguity_bound + max(cheap_marginal_bounds) > incumbent + tolerance`.
  That same cheap term was already included in the original bound; equality
  does not trigger this early return. No stronger mathematical bound is added.
- All historical ambiguity coordinates, selected-class definitions, objective,
  search budgets, and certificate conditions are retained. No kappa bound or
  reduction of search domain was implemented.
- Whole-solve elapsed time still starts before joint float fitting and includes
  every cache/factor construction. New certificate counters are
  `bound_evaluations`, `cheap_bound_prunes`, `bound_sphere_evaluations`,
  `candidate_sphere_evaluations`, and `sphere_metric_factorizations`. They are
  diagnostics, not a change to acceptance or certificate meaning.

## Verification record

The following commands were actually executed from `<CODE_ROOT>` in WSL with
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src`. This record transcribes
completed tool output; it does not represent another test execution.

1. `python3 -m pytest -q tests/paper_rebuild/test_carrier_solver_review.py tests/paper_rebuild/test_horizontal_ext01_clambda.py`
   returned **19 passed, 7 skipped in 0.35 s**. The seven skips were solely the
   unset `LEGSA_RTKLIB_LAMBDA_BRIDGE` fixture; they were subsequently executed
   using the already available pinned library, below.
2. `python3 -m pytest -q tests/paper_rebuild/test_carrier_solver_performance.py tests/paper_rebuild/test_carrier_temporal.py`
   returned **39 passed in 0.79 s**.
3. With `LEGSA_RTKLIB_LAMBDA_BRIDGE=<EXT_REPRO_BUILD>/lib/librtklib_legsa.so`,
   `python3 -m pytest -q tests/paper_rebuild/test_horizontal_ext01_clambda.py`
   returned **16 passed in 0.22 s**.
4. `python3 -m pytest -q tests/paper_rebuild/test_carrier_search_optimization.py`
   returned **8 passed in 0.13 s**.

There are **73 distinct passing tests, zero remaining skipped tests** across
these five files: new performance regressions 19; temporal 20; independent
solver review 10; existing search optimization 8; public C-LAMBDA 16. Repeated
public tests are not counted twice. Native bridge calls were only existing
synthetic unit tests, with no real RAW / reference input.

Four complete-tree comparisons (two synthetic problems, identity and nontrivial
unimodular transforms) gave exactly equal best/second integer vectors,
baselines, full/reduced objectives, explored nodes/leaves and scientific
certificate fields with versus without cache/preprune. Existing independent
raw-residual exhaustive tests separately verify the global pair and profiling
of historical integers. Cache tests check factor reuse, read-only ownership,
changing centers/radii, zero and tiny signed projections, nearly repeated
eigenvalues, the strict cheap-bound cutoff, and full leaf residual identity.

The new test file uses repository-local independent oracle fixtures; it does
not require a scratch NPZ or real dataset. Cache/prune tests impose no timing
threshold. This record establishes numerical/search equivalence for tested
cases, not a speedup claim or improved integer correctness. Platform floating
point, memory proportional to visited depth/epoch factors, and timeout outcomes
remain practical limits to assess in the controlled benchmark.

Root integration verification: 21 partial-search policy/class-freeze tests also PASS after this optimization (0.59 s). Together with the 73 distinct solver/public-kernel tests this is 94 distinct passing tests. benchmark_exact_search.py --help imports the selected implementation successfully; no real benchmark was included in these checks.
