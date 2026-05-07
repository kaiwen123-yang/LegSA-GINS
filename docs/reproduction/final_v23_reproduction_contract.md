# final_v23 Reproduction Contract

## N3C Goal

N3C will connect final_v23-style baseline reproduction without treating final_v23 as proposed.

## N3C Rules

1. Do not modify final_v23 source.
2. Build or run final_v23 baseline through a wrapper.
3. Standardize final_v23 outputs into LegSA-compatible baseline NAV / STD / EVAL_NAV.
4. Record RUN_MANIFEST.
5. Record SOURCE_MANIFEST if dataset metadata is available.
6. Do not let proposed solver read final_v23 output.
7. Do not perform output-only correction.
8. Do not perform trace tuning.
9. Do not make numerical performance claim before oracle pass.
10. Do not commit raw data.

## N3C Inputs

- final_v23 source path
- final_v23 build command
- final_v23 runtime command
- dataset config path
- expected output mapping
- reference/evaluator config if available

## N3C Outputs

- final_v23 baseline NAV
- final_v23 baseline STD
- final_v23 baseline EVAL_NAV
- RUN_MANIFEST
- source audit report
- oracle check report

## Forbidden

- final_v23_as_proposed
- final_v23_output_substitution
- proposed_reads_final_v23_output
- trace_tuning
- output_only_correction
- raw_data_commit
- numerical_claim_without_oracle_pass

## Success Criteria

N3C succeeds only when:

- final_v23 baseline can be built or executed;
- output mapping is documented;
- standardized NAV / STD / EVAL_NAV are produced;
- RUN_MANIFEST records algorithm_role=baseline;
- oracle/evaluator checks pass or explicitly report evidence_missing.
