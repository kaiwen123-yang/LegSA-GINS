# P-09c explicit restart authorization, 2026-09-12

Human starting commit: `1a1ee3f1783f59bc7daf3c7adcb1711d1356e196`.
Preregistered amendment commit: `dae932e43275ad3698f437bfdcce7959b3b5e009`.
The original stopped attempt remains recorded in
`CLEAN6_CANONICAL541_V2_PILOT_STOP.md`; it is not rewritten as a successful attempt.

## Authorized repair and reuse

- Explicit sequence transport `runtime_role` is
  `clean2r2a_formal_clean_ablation_solver`. P-06 wrapper manifests pin their native
  manifests by SHA-256; the role is read from those pinned native `port_role`
  fields. The wrapper itself has no direct runtime-role field.
- Missing identity keys produce `FAIL_NATIVE_IDENTITY_MISSING_CONFIG_KEYS`.
- Preserve all 33 original native outputs, original configuration/terminal/seal
  bytes and original native execution commit. Verify their complete seals, then
  revalidate the 22 original metadata failures using separate derived configs.
- New evidence belongs in
  `<CANONICAL541_V2_ROOT>/RESTARTS/RESTART_20260912/`; record native, validation
  and continuation code identities separately. The original scratch binding is
  exact. No original native run is relaunched.
- The first batch reuses those 33 records and launches only its remaining 223
  runs after the complete 33-run sequence/C00 gate passes.
- Original science, binary, evaluator, model, injection mappings, v1 main chain,
  Outcome and decision-rule bytes remain frozen.

## Resource amendment

- Solver/provider pool: `min(nproc - 2, 22)`; the old 64/128 policy is void.
- Six already-registered evaluations (one run per BY2/BY2H/BY2O, v3 and v2)
  measure RSS serially inside the first batch. They are never repeated.
- Each evaluator slot reserves 1.25 times maximum measured evaluator RSS.
  Solver phase process-tree peak plus evaluator reservations must fit 75% of
  current available memory; record and recheck each evaluation wave.
- GNU time measures native process RSS and duration inside each isolated
  strace. The phase monitor records controller/descendant RSS, CPU, available
  memory and filesystem growth. Known monitor failure blocks phase transitions
  and cleanup.
- Batch size remains 256; solve/seal/evaluate/reduce/archive/verify/ledger-cleanup
  ordering and the pilot projected-peak limit of 250 GB are unchanged.
- Preserve the new validation sidecars and their hashes in permanent archives.
  Final handoff must include the active restart gate/freeze and explicitly label
  original failed gate/stop records as pre-restart history.

## Implementation validation before execution

- Focused repair/resource/runtime/evaluation/aggregation and affected shared
  regression: **243 passed, 3 skipped**. The three optional archived-evaluator
  synthetic tests were not run and are not real-data evidence.
- The required real-manifest regression actually ran without skipping:
  **P-06 15/15 + retained sequence 22/22 = 37/37 PASS**.
- A broader run including historical sequence-contract tests returned
  **268 passed, 9 skipped, 2 failed**. Both failures are the historical
  `test_tracked_source_hashes_and_evaluator_identity_are_frozen` AGENTS pins for
  BY2H/BY2O: expected
  `2e4c87023454b2f7be1be05a4da17e94a7fe6dd633775d3d3138f8619d4a2142`, actual
  `7c6bfb3193965a4734e305fa2a3131f0e6cf6ef28052bfebac3f8c3158b44d7d`.
  AGENTS and both historical contracts were byte-identical to starting commit
  `1a1ee3f`; these failures predate this repair. They are retained, not repaired
  by changing frozen historical contracts. The required real37 test was then
  explicitly executed with its local fixture configuration and passed.
- Read-only reviewer: no known launch blocker after scoped repairs.
- These checks authorize no completion claim. Formal revalidation, the sequence
  gate, the full first batch and subsequent stages require their actual terminal
  evidence.
