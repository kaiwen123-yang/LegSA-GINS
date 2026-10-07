# Independent HV causal-policy replay runner review

Status: **PASS_STATIC_RUNNER_DELTA; REAL_PLAN_AND_LOCAL_COMPLETION_PENDING**. Static review only, no source/provider/native output payload or scientific execution. This document concerns the new runner; production-policy mathematics and local qualifications have separate owners.

Read the 138-line first draft `scripts/paper_rebuild/carrier_phase/hv_causal_policy_replay.py`, the reused registration/launch/seal/manifest/structure helpers, and the final producer's CSV writer and selector. The intended legacy3-before-causal3 order is implemented. It appends exactly one policy line to three copied configs and requires derived size/SHA pins. All existing new-legacy output names, sizes and hashes must match the old TELEMETRY seal; no old payload is read. Causal output keeps NAV time support and input IMU segment identity, and the reused structural helper retains fixed source/lifecycle/prior identity without matrix algebra.

Three concrete pre-registration findings were sent to the root owner:

1. **Inherited registration gates are not called automatically.** The draft calls `h.source_check` but not `replay.register`. Add an explicit new-runner source pin, fixed CODE_ROOT/SCRATCH_ROOT aliases and equality of the 18 unique `(path,sha,size)` provider declarations to the exact three prepared provider/carrier sets. Bind prepared per-run config/events/manifest and loader identities to registered metadata. Counting 18 files and total hash bytes alone does not prove the rehashed files are those actually supplied to native.
2. **Execution seal closure is incomplete.** The draft global seal binds native output payloads but omits invocation/return/access/trace/stdout/stderr evidence, PRE/POST hash receipts, reservation and generated configs. Reuse the established finite execution-evidence pin pattern; no second OUT payload hashing is necessary.
3. **The provisional CSV interface does not match the final producer.** Replace nonexistent age_s/source_generation/source_index/tolerance_s/ledger_time fields with the actual header. Verify present==consumed, accepted implies consumed, absent fields/accepted are empty/false, finite signed ages with their exact trigger/source and state/source definitions, the inherited trigger tolerance, one generation across all rows, strictly increasing reserved timestamps and unique reserved indices. Compare accepted source-bits/index/state triples to the existing ARC ledger. An all-skipped policy result is valid negative evidence and must not fail merely because there are no selected-generation entries.

Clock semantics: the opt-in CSV state clock is `pvacur_.time`; the ledger clock is engine `timestamp_`; trigger is GNSS `update_time`. The registered exact-event real runs should align the actual state/ledger clock and must check it, rather than infer it from the trigger argument. Source must be no later than either trigger or actual state. Only trigger-age inherits the old 0.08 s tolerance; do not silently introduce an additional state-age tolerance into the policy. Generation labels need not equal 1.

The new helper usage reads each new causal conditioning ledger once for structure and once for the CSV/accepted-ledger cross-check, in addition to its output-sealing hash pass. This is bounded new-output field reading, not phase-information computation; document these actual passes instead of claiming one traversal. Full matrices are only decoded/shape/finite checked by the inherited structural helper, with zero covariance algebra. Default/new policy outputs and failed attempts must all be retained.

The initial findings above are retained as review history and superseded by the final delta review below. The reviewer edits only this document and the owned real proposal.


## Final runner delta review

Reviewed the root's 164-line corrected runner, SHA256 `7b3f290548591849b06b330103fe75ca63934affd5b72af614446203f30e11f4`, and checked the exact field names against the production CSV and manifest writers. All three named findings are closed. **No remaining static runner blocker was found within this review scope.** The real plan and local binary result were not yet complete at this check, so this does not authorize or claim any real execution.

The new SCRIPT pin and fixed workspace aliases are explicit. The 18 provider `(path,sha,size)` declarations must equal the three prepared provider/carrier sets. The sealed loader/preparation chain is checked, config/events/manifest pins are checked before and after native, and generated causal configs match registered byte-size/SHA after the one-line append.

The global seal now includes 49 execution evidence pins: four root registration/hash receipts, three generated configs and seven control/evidence files for each of six calls. Native output payloads are not rehashed for this evidence list. The legacy3-before-causal3 and every-file legacy byte gates remain intact.

The causal CSV parser now matches the final producer. It checks finite trigger/state clocks and exact equality specifically for these registered exact-event runs; known-NED/unknown-arrival fields; present==consumed; empty invented-source fields and accepted=false when absent; source no later than either clock; trigger-age within the inherited manifest tolerance; exact age/source-bit formulas; unique reserved indices and strictly increasing timestamps per generation. All rows contribute to the generation set, so an all-skipped negative result is not rejected merely because nothing was selected. Accepted source/index/state tuples must match the existing ARC update ledger in order, and selected/accepted/skip counters match manifest declarations.

The producer's manifest contains the tolerance, old update count and new opt-in counters used by the parser. The generic producer may have different trigger and state clocks, while the registered real exact-event test requires their equality. The real policy still applies the unchanged tolerance to trigger-age only; no new state-age threshold is introduced.

No local running trace, scientific input or native result was inspected for this delta review. No import, build, test or numerical execution was performed by the reviewer. Final real-plan registration remains the root's next gate after local completion.
