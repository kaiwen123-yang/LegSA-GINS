# CLEAN3R2 Supervisor Final Report

## Decision

`CLEAN3R2_MATH_REPAIR_COUNTER_CONTRACT_ROUTING_REPAIR_AND_S3_RESUME` terminates as `FAILED_TECHNICAL_SOLVER_MANIFEST_CONTRACT`.

- Formal S3 byte parity: `NOT_EVALUATED`.
- `ready_for_S4=false`.
- `ready_for_paper_claims=false`.
- Exactly one solver attempt was made; the authorization is consumed and `retry_count=0`.
- No evaluator, reference trace, performance metric, S4 action, provider regeneration, rebind, or Canonical-541 execution occurred.

## Provenance

- Amendment parent: `9d51794d5c031cd0331d1fd8fe66d42c0fb690ed`.
- CLEAN3R2 code freeze: `8dd620ea6d9645b946a503275ddbf04d66c3baa2`.
- CLEAN3R2 runner freeze: `5209b6afeeb2b2a0ad99e640ffe50f8dd3b0c909`.
- Authorization/execution commit: `ed49dfa0d16690ad867535137d5a961d89216234`.
- Final C++ tree: `72db2c7cc86e92df5f9a475536faa67719c6e61a`.
- Authorization document SHA-256: `eb267045d32af7ae407129b8b53fb6f4c8ed8a6dd75b7889a5a0fb53c3223237`.
- Execution-freeze SHA-256: `779b3bf388f8d52e5d2baa14833220ff4ca56d45b81067347382ff862575e910`.

## Attempt Result

The loader assigned `clean3_s3_ab0000_parity_solver`. During `PortRuntime::runFromConfig`, the formal-stage role routing recognized only CLEAN2R2A specially and overwrote every other formal stage with `clean1_formal_four_method_solver`. The solver completed and wrote a manifest carrying that overwritten role. The runner's exact manifest contract then rejected it with `solver manifest mismatch: port_role`.

The runner behaved correctly. Manifest validation must not be weakened to accept the wrong provenance role. The appropriate subject of any separately approved future repair is the role routing in `PortRuntime::runFromConfig`.

## Counter and Safety Result

- Position updates: `274`.
- Receiver-velocity updates: `274`.
- Dual-yaw attempts/accepted: `274` / `268`.
- Raw Doppler, source-aware evaluation/change, Go2 roll-pitch, and Go2 horizontal-velocity updates: all `0`.
- Selected FGO, nine-factor FGO, multi-state QM, QA fallback, and contact/FK: all `0`.
- Covariance health: `PASS`; failure count `0`; `math_port_completed=true`.
- Synthetic and semisynthetic flags: `false`.
- Old/legacy runtime, provider, row, and aggregate input counts: all `0`.
- Performance and paper-claim flags: `false`.

All 34 immutable roles matched before and after the attempt: 22 raw files, 5 providers, 3 inherited manifests, 2 raw locks, and 2 anchors. `immutable_changed_roles=[]`.

## Artifact Status

All paths below are relative to `<CLEAN_ROOT>`.

- Terminal report: `stages/CLEAN3R2_MATH_REPAIR_COUNTER_CONTRACT_ROUTING_REPAIR_AND_S3_RESUME/04_REPORT/CLEAN3_S3_AB0000_PARITY_REPORT.json`; SHA-256 `bf14da4db81cfddd836056de2380078f1d2e77477334633a2198288ff3c024c7`.
- Runtime manifest: `stages/CLEAN3R2_MATH_REPAIR_COUNTER_CONTRACT_ROUTING_REPAIR_AND_S3_RESUME/02_AB0000_RUNTIME/RUN_MANIFEST.json`; SHA-256 `e51cf3c2be1325d1b43065ec8174b0be2e232fa08c8cb658addc637c0844fb63`.
- Retained raw syscall trace: `stages/CLEAN3R2_MATH_REPAIR_COUNTER_CONTRACT_ROUTING_REPAIR_AND_S3_RESUME/02_AB0000_RUNTIME/logs/SOLVER_FILE_OPEN_TRACE.raw`; SHA-256 `7b1dc64106367279965a8de51988a4ff585b19533311e9c1b90d767e68f74d99`.
- Formal syscall ledger: absent.
- Output seal: absent.
- Outer run manifest: absent.

The unsealed NAV and STD hashes are respectively `800f0dc12d77fe01ff5262c4261457e1ec178344dba3efb249464ed16696ebc0` and `04ebff455853a89e3a32ebed5510a5c3b86acfa3b569448acd6c7b29c18a05e2`, equal to the locked anchor hashes. This observation is not formal parity evidence: ledger persistence, post-validation, sealing, and stream comparison never occurred. Formal parity therefore remains `NOT_EVALUATED`.

## Preservation and Next Boundary

The old CLEAN3 attempt remains immutable. Its report SHA-256 is `382e35f400bd09112ef90463b69b179e0c9529c20bb3d51cda467f4c2df515b5`; its solver-stderr SHA-256 is `3fe5a472efbbeb1e7aab0479d45d5599608e5f92e033e8f4afd53eafcca4a4d4`. Its terminal and parity remain `FAILED_TECHNICAL_S3_AB0000_FORMAL_COUNTER_CONTRACT_UNROUTED` and `NOT_EVALUATED`.

No retry is authorized. Any future `port_role` repair requires a separate human-approved proposal, a new non-overwriting identity, a reviewed freeze, and a separate execution authorization. The 3641/5951 rebind remains deferred, and all later CLEAN3 stages remain closed.
