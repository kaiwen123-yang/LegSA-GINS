# Clean Rebuild Experiment Protocol

## Evidence Chain

Every formal run follows one chain:

1. Verify an immutable raw file against `<CLEAN_ROOT>/01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK.csv`.
2. Generate inputs and providers from raw sources under `<CLEAN_ROOT>/04_PROVIDER_FREEZE/`.
3. Record source roles, raw hashes, provider hashes, generator commit, and config hash.
4. Run only `src/legsa_gins/paper_rebuild/` through a paper-rebuild entrypoint.
5. Write output only below the configured clean runtime root.
6. Validate the manifest against `configs/paper_rebuild/manifest_schema.yaml`.
7. Audit that no legacy runtime path or payload was read.
8. Evaluate with trace offline only and retain a metric cross-check.

If any link is missing, the run is not active evidence.

## Data Modes

- `real_by2_raw`: freshly derived from hash-locked BY2 raw data.
- `real_by3_raw`: freshly derived from hash-locked BY3 raw data.
- `real_xb_pg_raw`: freshly derived from hash-locked XB/PG raw data.
- `synthetic`: fully synthetic and never eligible for a real-data result table.
- `semisynthetic`: real source plus injected degradation and never mislabeled as raw clean data.

Every manifest must write `data_mode`, `synthetic_data_used`, and `semisynthetic_data_used` explicitly.

## Fixed Safety Invariants

- Trace is evaluation-only and `trace_used_online=false`.
- Receiver IMU cannot substitute for Go2 body IMU.
- final_v23 output and LegSA output cannot enter solver input.
- No per-case tuning or output-only correction.
- No epoch is deleted to improve a metric.
- A clean raw run has `old_runtime_input_count=0`.
- Provider lineage and source hashes are mandatory.
- Reported metrics must be recomputable from the final clean output, not an old aggregate or summary reconstruction.

## Degradation Protocol

The 60-type, 9-seed registry and classic-18 manifest are retained as legacy protocol definitions only. They do not import any legacy providers or results. Degraded data must be regenerated under `<CLEAN_ROOT>` from hash-locked raw inputs. Seed replay uses the fixed seed catalog and PCG64. The clean case is unique and contains no random operation. Module-disable is a method ablation, not a degradation case axis.

## Execution Boundary

CLEAN0 authorizes only the independent BY2 clean smoke required by the stage. It does not authorize DA03, DA05, the 541-case matrix, paper figures, or performance conclusions. Later execution requires its own explicit stage and human gate.
