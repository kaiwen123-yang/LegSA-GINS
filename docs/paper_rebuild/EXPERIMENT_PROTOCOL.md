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

## CLEAN1R2R1 final_v23 profiles

- `archived_E001_semisynthetic` is `ARCHIVED_SEMISYNTHETIC_DIAGNOSTIC_REFERENCE_ONLY`. Its `nominal_none` label means no additional degradation case; the base command still injected 1.5 degree Gaussian yaw noise with seed 42 and read trace during provider generation. Its input, output, rows, and metrics cannot enter clean evidence.
- `clean_real_final_v23` is the selected parity/strong-baseline profile. It uses current hash-locked real BY2 raw, GNSS1 position/std, GNSS1 raw NAV-PVT receiver velocity, GNSS1/GNSS2 status A1 yaw, and Go2 body IMU. Yaw measurement std is 1.5 degrees, while yaw noise injection is disabled and trace is excluded from generation.
- E001 may support unaffected static runtime fields only when cross-confirmed by exact tag/source. It is not a byte-parity target and its old input is never solver input.

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

## Retained CLEAN1R1C Kick-Aligned Protocol

This subsection records the superseded CLEAN1R1C contract for provenance only. It is not the current execution authorization and cannot supply CLEAN1R2 active evidence.

- Detect the physical kick only from the initial Go2 IMU/event segment using the frozen robust jerk score and the maintained event-normalized detector cross-check.
- Freeze `fixed_event_alignment_offset_seconds=0.0`; no correlation, trace, output, or metric offset search is permitted.
- Set `t_start` to the first position- and dual-yaw-valid GNSS epoch after the mapped kick.
- Set `t_end=min(propagation_imu_last_valid,core_gnss_last_valid)` and preserve internal dropouts.
- Raw Doppler and Go2 priors are optional at start and activate only when their own epochs become available.
- Freeze `[0.03,0.03,-0.30] m` as the common GNSS measurement lever arm.
- Freeze the evaluator without opening trace. After four outputs are hash-frozen, interpolate reference ECEF and unwrapped ENU yaw at absolute solver time, convert yaw with `wrap360(90-yaw_enu)`, and retain unmatched epochs in coverage.

## Execution Boundary

CLEAN0's independent BY2 smoke remains a runtime-health regression only. CLEAN1R1C and CLEAN1R2 remain historical protocol. The separate tracked CLEAN3R4 authorization now permits only the repaired Canonical-541 route and preserves the required preparation, solver terminalization, output seal, then offline-trace ordering. It does not authorize DA03, DA05, a new case axis, literature comparison, or broad performance conclusions before fresh evidence closure.
