# N4H2G prompt snapshot

Task: generate and replay a clean status-yaw no-noise/no-outlier/no-outage
process_data-compatible input variant, evaluate it against the dual official
reference, compare it with noisy historical dual_final_v23 evidence, and record
clean/noisy provenance.

Hard boundaries:

- no solver modification;
- no trace solver input;
- no output-only correction;
- no bad-epoch deletion;
- no raw data or generated replay artifacts committed;
- no formal paper performance claim;
- noisy historical artifact must not be called clean nominal.
