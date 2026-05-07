# Manifest Contract

## RUN_MANIFEST

RUN_MANIFEST must record:

- phase
- algorithm_role
- algorithm_name
- dataset_name
- output_dir
- forbidden claim flags
- evidence_status

algorithm_role must be one of baseline, proposed, diagnostic, or infrastructure.

raw_data_committed must be false.

Forbidden claims must be false.

If evidence is missing, evidence_status must be:

evidence_missing

## SOURCE_MANIFEST

SOURCE_MANIFEST must record:

- sensor metadata
- time base metadata
- frame declarations
- extrinsics placeholders
- reference placeholders
- raw_data_policy

raw_data_policy must record raw_data_committed, large_files_committed, and external_data_required.

SOURCE_MANIFEST must not invent real sensor paths when the evidence is not available.
