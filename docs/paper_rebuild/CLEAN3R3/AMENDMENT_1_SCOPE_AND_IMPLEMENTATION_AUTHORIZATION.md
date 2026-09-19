# CLEAN3R3 Amendment 1 Scope and Implementation Authorization

## Human decisions

- F1: delete the formal `PortRuntime::runFromConfig` `port_role` override. Do not add an empty-value fallback. The loader remains the sole formal role resolver.
- F2: extend the guarded whitelist only for the exact CLEAN3R3 S3 tuple. Do not add S7 or Canonical-541 identities.
- S7: defer identity definition to an S6.5 micro-freeze after earlier gates. No S7 tuple is authorized now.
- T5 proof kind: `STATIC_PLUS_ZERO_DATA_LOADER`. It proves source composition plus loader-only resolution; it makes no dynamic `runFromConfig` claim.
- T6-T9: implement the bounded governance regressions frozen by the human prompt.
- G-C2: `REPORTING_ONLY` for the governance preflight.
- G-C3: unchanged hard gate.

## Authorized topology and scope

A0 records this amendment and the byte-identical S-1 inventory. C1 may change only the runtime formal-role override, the two guarded CLEAN3 S3 recognizers, and the new T5-T9 test. C2 may change only the CLEAN3 runner module, its CLI script, and the existing S3 parity-runner test.

Implementation is authorized for A0/C1/C2 only. Formal solver execution remains false until a separately reviewed freeze and authorization exist, G-C3 passes unchanged, and a sealed governance preflight reports `PREFLIGHT_OK` with exact hashes/topology.

- `implementation_authorized=true`
- `formal_solver_authorized=false`
- `S3_authorized=false`
- `S7_authorized=false`
- `Canonical_541_authorized=false`

No provider, raw input, reference trace, evaluator, solver, external stage root, performance metric, push, merge, or tag is authorized.
