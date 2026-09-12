# CLEAN3R2 Counter-Contract Routing Repair Status

## Terminal Identity

- Stage: `CLEAN3R2_MATH_REPAIR_COUNTER_CONTRACT_ROUTING_REPAIR_AND_S3_RESUME`.
- Execution commit: `ed49dfa0d16690ad867535137d5a961d89216234`.
- Code freeze: `8dd620ea6d9645b946a503275ddbf04d66c3baa2`.
- Runner freeze: `5209b6afeeb2b2a0ad99e640ffe50f8dd3b0c909`.
- Terminal: `FAILED_TECHNICAL_SOLVER_MANIFEST_CONTRACT`.
- Formal S3 byte parity: `NOT_EVALUATED`.
- The sole authorized attempt was consumed; `retry_count=0` and no retry is authorized.
- `ready_for_S4=false`; `ready_for_paper_claims=false`.

## Exact Failure

The loader correctly assigned `port_role=clean3_s3_ab0000_parity_solver` for the exact guarded CLEAN3R2 identity. `PortRuntime::runFromConfig`, however, overwrote every formal non-CLEAN2R2A stage with `port_role=clean1_formal_four_method_solver`. The persisted solver manifest therefore contained `clean1_formal_four_method_solver`, and the runner correctly rejected it with `solver manifest mismatch: port_role`.

This is a provenance-routing failure after solver completion, not a counter-contract failure and not an observed parity mismatch. The AB0000 counters closed: position `274`, receiver velocity `274`, dual-yaw attempts `274`, Raw Doppler/source-aware/roll-pitch/horizontal-velocity counters all `0`, and all FGO/QM/QA/contact counters `0`. Covariance health was `PASS` with zero failures and `math_port_completed=true`.

## Evidence Boundary

- The unsealed NAV SHA-256 is `800f0dc12d77fe01ff5262c4261457e1ec178344dba3efb249464ed16696ebc0`.
- The unsealed STD SHA-256 is `04ebff455853a89e3a32ebed5510a5c3b86acfa3b569448acd6c7b29c18a05e2`.
- Those hashes equal the locked anchors, but they are not formal parity evidence: syscall-ledger persistence, manifest post-validation, output sealing, and the runner's stream comparison did not occur.
- The formal syscall ledger, output seal, and outer run manifest are absent. The retained raw syscall trace SHA-256 is `7b1dc64106367279965a8de51988a4ff585b19533311e9c1b90d767e68f74d99`.
- The terminal report SHA-256 is `bf14da4db81cfddd836056de2380078f1d2e77477334633a2198288ff3c024c7`; the runtime manifest SHA-256 is `e51cf3c2be1325d1b43065ec8174b0be2e232fa08c8cb658addc637c0844fb63`.
- All 34 immutable roles were unchanged: 22 raw files, 5 providers, 3 manifests, 2 raw locks, and 2 anchors; `immutable_changed_roles=[]`.
- No evaluator, reference trace, performance metric, S4 action, provider regeneration, rebind, or Canonical-541 execution occurred.

The new attempt remains preserved under `<CLEAN_ROOT>/stages/CLEAN3R2_MATH_REPAIR_COUNTER_CONTRACT_ROUTING_REPAIR_AND_S3_RESUME/`. The old CLEAN3 attempt also remains preserved; its terminal and parity remain `FAILED_TECHNICAL_S3_AB0000_FORMAL_COUNTER_CONTRACT_UNROUTED` and `NOT_EVALUATED`.

## Closed Boundary

CLEAN3R2 is terminal at this gate. Any repair to `port_role` routing or any retry requires separate human approval, a new non-overwriting attempt identity, a reviewed freeze, and a separate execution authorization. A future proposal should repair the provenance routing in `PortRuntime::runFromConfig`; it must not weaken the runner's manifest validation.

The 3641/5951 rebind remains deferred. S4, calibration, the 18-configuration rerun, evaluator use, Canonical-541, merge, tag, and paper claims remain unauthorized.
