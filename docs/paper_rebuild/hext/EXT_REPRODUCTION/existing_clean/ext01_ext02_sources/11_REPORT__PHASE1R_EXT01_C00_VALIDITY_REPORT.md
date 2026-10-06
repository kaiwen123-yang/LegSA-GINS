# Phase 1R EXT01 C00 validity report

Terminal status: `BLOCKED_PHASE1R_SEARCH_OBJECTIVE_CROSSCHECK_FAILED`

The previous Phase-1 engineering output under `02_EXT01_CLAMBDA/C00/` was
hash-checked before and after this run and was not overwritten.  This validated
run consumed true hash-locked RXM-RAWX bytes and RTKLIB broadcast satellite
states.  Trace was first opened only after the six native outputs were frozen
and revalidated, solely for descriptive same-source metrics.

## Root cause and repairs

The 432 false zeros were a reporting-order defect: the old runner initialized
the common-raw count to zero and computed it only after SPP and DD construction.
Phase-1R computes provider-independent raw/validity stages first and preserves
them on every later failure.  Tracking events are now separated from the
method's intentional per-epoch ambiguity reinitialization.  `cpMes` is used as
reported; `subHalfCyc` means that the receiver already applied the half-cycle
subtraction, so no second +/-0.5-cycle shift is made.

## Native result

- paired/native rows: 1509/1509
- integer solutions returned and globally certified: 1077
- no native integer result: 432
- ambiguity acceptance test defined: false
- failures: INSUFFICIENT_CP_VALID=11, INSUFFICIENT_DD_DIMENSION=1, INSUFFICIENT_HALF_CYCLE_VALID=374, INSUFFICIENT_SATELLITE_STATES=46
- availability: 0.713717694

The fixed 0.350 m constraint makes successful baseline lengths exactly 0.350 m;
that fact is not used as a stochastic-model validation.

## Scientific audit boundary

The strict search uses RTKLIB decorrelation/seeds only as incumbents, then a
mathematically complete best-first C-LAMBDA branch-and-bound.  A row is called
globally certified only when the remaining frontier lower bound cannot beat the
second-best full constrained objective.  No candidate cap is applied.  No
accepted-fix rate is reported because BY2 supplies no independent true integer
ambiguity vector and no untuned ambiguity acceptance test was defined.

NAV-HPPOSECEF and RTKLIB relative positioning are diagnostic-only.  Neither was
used by the solver, sign selection, time selection, parameter selection, or
output correction.  The post-native trace comparison is same-source and is not
independent truth.

## Reproduction

```bash
cd <AUDIT_SOURCE_WORKTREE>
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
python3 scripts/paper_rebuild/run_horizontal_literature_phase1r.py \
  --paths-config configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml \
  --method-id EXT01_CLAMBDA --case-id C00_VALIDATED \
  --trace-mode post-native-descriptive --workers 16 --resume
```
