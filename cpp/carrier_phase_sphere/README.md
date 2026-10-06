# Optional scalar sphere kernel

The default carrier solver remains Python. This shared library replaces only
its 3D spectral hard-case and secular-root loop. It does not perform integer
search, create a new objective, change iteration/tolerance limits, or remove
historical ambiguity coordinates.

Build in a fresh Ubuntu-22.04 WSL output directory:

```sh
python3 scripts/paper_rebuild/carrier_phase/build_native_sphere.py --output-dir /absolute/new/build/directory
```

The builder invokes GCC with `-O3 -fno-fast-math -ffp-contract=off`, writes a build
log and `BUILD_MANIFEST.json`, and refuses to overwrite an existing library.
The source also rejects fast-math and finite-math-only compilation. No package
installation or native LegSA-GINS rebuild is needed.

Opt in explicitly with `solve_temporal(..., sphere_library=".../liblegsa_sphere.so")`
or `solve_partial(..., sphere_library="...")`. Default `None` neither loads nor
searches for a shared library. Missing libraries and ABI/kernel mismatch fail
closed; there is no silent Python fallback. Public `constrained_baseline` is
unchanged and always uses Python.

ABI 1 exports `legsa_sphere_abi_version`, `legsa_sphere_kernel_version` and
`legsa_sphere_root3`. Covariance validation, inverse/eigendecomposition, spectral
projection, baseline reconstruction, full objective and length checks remain
in Python. Finite-output checks also reject malformed native results. Native
and Python operations need not be bit-identical; certified search outcomes must
be compared on predeclared problems before production use.

Execution provenance must retain the requested absolute library path, runtime
configuration, scientific source commit, and this build manifest (compiler,
flags, source and binary hashes). Each temporal certificate records backend,
ABI/kernel version and loaded-file SHA-256. Whole-solve elapsed time includes
backend load/hash and factor setup. A filename or ABI number alone does not
prove source identity. The file must remain immutable while a run uses it.

The initial scratch prototype tested 2,100 synthetic sphere problems: 2,076
successful pairs and 24 matching numerical failures, with no mismatch in that
domain. Its 13.55x median paired cached-sphere speedup includes ctypes overhead
but is not an AR end-to-end latency result. No real-data performance or integer
correctness claim follows from a faster scalar kernel.

## Focused implementation verification

Executed in Ubuntu-22.04 WSL with `OPENBLAS_NUM_THREADS=1`,
`OMP_NUM_THREADS=1`, `PYTHONPATH=src`:

```sh
python3 -m pytest -q tests/paper_rebuild/test_carrier_native_sphere.py tests/paper_rebuild/test_carrier_partial.py tests/paper_rebuild/test_carrier_solver_performance.py tests/paper_rebuild/test_carrier_solver_review.py tests/paper_rebuild/test_carrier_search_optimization.py
```

Result: **87 passed in 1.28 s, zero skipped**. A fresh scratch pytest temporary
root was supplied on that execution. Native tests compile this small optional
library once with the registered builder; no third-party package is installed.
The numerical workload is synthetic only. No new real CILS/navigation/reference
run was performed during implementation.

Coverage includes 128 predetermined random SPD metrics with three centers each;
exact hard cases and signed near-pole cases; retention of the original 300-step
failure; ABI/kernel and missing-symbol/library rejection; finite-output checks;
explicit errors instead of fallback; default Python no-load behavior; common
native use by both bound and leaf caches; whole-search candidate/objective
agreement; independent exhaustive selected-class correctness; and partial-search
argument forwarding without deleting nuisance integers. Numerical comparisons
use explicit tolerances and do not claim cross-platform bitwise equivalence.
