# CLEAN2 execution status

## Current decision

- Stage: `CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18`
- State:
  `PASS_CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18_FRESH_EVIDENCE_READY_FOR_HUMAN_REVIEW`
- CLEAN1 PR #59: guarded merge commit complete at
  `eddc536b36d87c760bd7c6a3184f2ff724a8ea78`.
- CLEAN1 milestone tag:
  `CLEAN1R2R1-v1.0-final-v23-parity-four-method`.
- CLEAN2 branch: `stage/clean2-by2-ablation-classic18`.
- CLEAN2 code-freeze commit:
  `8b592681de3aef97e33e86e1092664950d8db114`.
- Post-freeze validation: `333` paper-rebuild tests, C++ build, `compileall`,
  `git diff --check`, and read-only review all pass.
- Raw integrity: `22/22` at pre-provider, post-provider, and post-run; mutation
  count `0`.
- Fresh base-provider parity: all five frozen IMU/GNSS/Raw-Doppler/Go2 hashes
  match.
- Fresh formal solver process count: `110/110`; attempts `110`; technical
  retries `0`; metric-driven retries `0`.
- C00 structural gate: single/basic/strong/full NAV, STD, timestamps, and
  counters are byte-identical to the CLEAN1R2R1 references.
- Output seal: `110` formal wrappers and `1,143` artifacts sealed before trace;
  online trace count `0`.
- Offline evaluation: `110/110` finite; `56,642` matched and `0` unmatched
  epochs per run; coverage `1.0`.
- Invariants: single C00..C17 bit identity, position/velocity source isolation,
  basic C00/C10/C14 fixed-std identity, strong/full C00 aliases, aggregate
  crosscheck, and all forbidden counters pass.
- Diagnostics: `18` PNG plus `18` PDF figures pass render QA and remain
  diagnostic-only.
- Terminal gate:
  `<CLEAN2_STAGE>/14_FINAL_EVIDENCE/CLEAN2_TERMINAL_GATE.json`.
- CLEAN2 publication remains Draft-only. This status does not authorize PR
  merge or a CLEAN2 release tag.

Two earlier CLEAN2 attempts remain preserved under failure-qualified stage
aliases. Neither their provider payloads nor their outputs, evaluation, or
metrics are current evidence or current solver input.

## Descriptive result ceiling

- C00 supports the frozen `2^4` descriptive RD/SA/RP/HV factorial on the
  strong/final_v23 backbone. Effects and all six two-way interactions per
  metric are recorded without p-values or significance claims.
- C01..C17 support only descriptive comparison under the specified controlled
  current-A1 dual-yaw perturbations. C02/C03 are current-provider no-op cases
  and are not downsample-robustness evidence.
- Six sentinel cases support descriptive leave-one-module-out marginal losses.
  Helpful/harmful labels remain metric- and case-specific; several effects are
  very small and no practical-neutral threshold was frozen.

## Claim ceiling

Classic-18 is a real-data-based controlled dual-yaw degradation pilot, not 18
real scenarios and not pure module ablation. Even a terminal PASS will not
establish universal superiority. BY3/XB and the 60x9 matrix remain unexecuted.
