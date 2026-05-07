# Reproduction Runner Contract

Stage N3C provides an external-source wrapper for final_v23/KF-GINS baseline
reproduction connection. The wrapper must not modify, vendor, or silently
rewrite the external source tree.

## External Source

- The external source is probed through `probe_external_source.py`.
- Source status, branch, commit, required files, and observed output filenames
  are recorded as evidence.
- The external source remains read-only from the LegSA-GINS workflow.

## Build And Run

- `build_external_final_v23.py` is dry-run by default.
- A real build requires both `--allow-build` and `--no-dry-run`.
- The build directory must be outside the external source root.
- `run_external_final_v23.py` is dry-run by default.
- A real run requires both `--allow-run` and `--no-dry-run`.
- `RUN_ATTEMPT.json` records dry-run or run status.

## Standardized Outputs

- `standardize_final_v23_outputs.py` writes standardized baseline outputs from
  observed KF-GINS output files.
- `RUN_MANIFEST.json` records the N3C baseline role and all forbidden flags.
- `final_v23_is_proposed: false`
- `proposed_reads_final_v23_output: false`
- `final_v23_output_substitution: false`
- `output_only_correction: false`
- `numerical_claim_without_oracle_pass: false`

## Claims

final_v23 remains a baseline. The proposed solver must not read final_v23
outputs. An oracle pass is required before any numerical reproduction claim.

Real configs and live outputs may remain `evidence_missing` until the local
source, config, and data are available.
