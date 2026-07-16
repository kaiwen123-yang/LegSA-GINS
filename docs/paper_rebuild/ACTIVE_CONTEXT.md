# LegSA-GINS Clean Rebuild Active Context

## Identity

- Active program: `STAGE_ID=CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18`.
- Parent milestone: `CLEAN1R2R1_CLEAN_REAL_FINAL_V23_PARITY_AND_FOUR_METHOD_EXECUTION`.
- Active dataset: `BY2`; clean case `C00_clean_normal`; controlled cases `C01..C17`.
- Active protocol: `CLEAN_PROTOCOL=CLEAN_REAL_DATA_FINAL_V23`.
- Active Git line: `stage/clean2-by2-ablation-classic18`.
- Active worktree: `worktree://clean2-by2-ablation-classic18`.
- CLEAN1 merge anchor: `eddc536b36d87c760bd7c6a3184f2ff724a8ea78`.
- CLEAN1 code freeze: `5c807633f699238aa2244a0496881dff71550273`.
- CLEAN1 report commit: `a3909830288b29a8576626408c0eea700abea5ef`.
- CLEAN1 milestone tag: `CLEAN1R2R1-v1.0-final-v23-parity-four-method`.
- Active implementation namespace: `src/legsa_gins/paper_rebuild/`.
- Active runner entrypoints: `scripts/paper_rebuild/` only.
- Active raw source: `<RAW_ROOT>`; raw files are immutable.
- Active generated-asset root: `<CLEAN_ROOT>`.
- Historical freeze root: `<LEGACY_FREEZE_ROOT>`; it is provenance/reference material, not active performance evidence.

## Mandatory Reading Order

1. This file.
2. `DATA_ROLES.md`.
3. `METHOD_SCOPE.md`.
4. `EXPERIMENT_PROTOCOL.md`.
5. `LEGACY_DENYLIST.md`.
6. `CLAIM_BOUNDARY.md`.
7. `NEXT_ACTIONS.md`.

## Clean Active Allowlist

Tracked protocol and implementation material may come only from:

- `docs/paper_rebuild/`;
- `configs/paper_rebuild/`, excluding the ignored local path file from Git;
- `scripts/paper_rebuild/`;
- `tests/paper_rebuild/`;
- `src/legsa_gins/paper_rebuild/`;
- maintained shared source explicitly imported by the paper-rebuild runner and recorded by commit SHA.

Active runtime evidence may come only from `<CLEAN_ROOT>` and only when its manifest passes the clean dependency audit. Raw data under `<RAW_ROOT>` are inputs, not algorithm results. Selected specifications and lessons under `<LEGACY_FREEZE_ROOT>` may explain provenance, but no legacy metric, row result, provider payload, NAV, STD, EVAL_NAV, figure, aggregate, or reconstructed summary is active evidence.

## Hard Rules

- Every formal result starts from hash-locked raw data and freshly generated providers.
- Trace is evaluation-only; it cannot select sign, offset, provider, method, threshold, or tuning.
- The lateral antenna vector is GNSS2 minus GNSS1. Baseline heading is not body yaw; the fixed physical transform is applied before wrap-safe residual evaluation.
- Receiver IMU is not Go2 body IMU.
- Go2 position, velocity, yaw, contact, and metadata are not truth. Approved Go2 inputs are weak priors or diagnostic metadata only.
- final_v23 and LegSA outputs are never solver inputs.
- No per-case tuning, output-only correction, or metric-driven epoch deletion is allowed.
- Synthetic and semi-synthetic results must never enter a real-data result table.
- Every runtime manifest records source hashes, provider hashes, provider-generator commit/config hash, data mode, synthetic flags, forbidden-input flags, clean code commit, clean-worktree state, and runtime config hash.
- Old runners may remain for historical reproducibility, but the clean rebuild must not call them.
- There is no active complete nine-factor FGO claim.

## Current Gate

The human authorized one bounded CLEAN2 chain with two scientifically distinct
namespaces:

1. `BY2_REAL_CLEAN_MODULE_ABLATION`: C00 only, strong/final_v23 backbone, all
   16 frozen RD/SA/RP/HV feature combinations;
2. `BY2_CONTROLLED_DUAL_YAW_DEGRADATION`: C01..C17, real BY2 base with only the
   current A1 dual-yaw value/validity/std perturbed, canonical four methods, plus
   four leave-one-module-out configurations on six frozen sentinel cases.

Classic-18 is a real-data-based controlled dual-yaw degradation pilot. It is
not 18 real environments, not an independent-truth study, and not a pure module
ablation. Controlled cases use `data_mode=real_base_controlled_degradation`,
`synthetic_data_used=false`, and `semisynthetic_data_used=true`; they remain
separate from the clean-real C00 table.

Execution is fail-closed in this order: implementation and tests; code-freeze
commit; raw pre-check 22/22; fresh base-provider generation and exact five-hash
parity; raw post-provider 22/22; deterministic 18-case provider freeze; 110-run
registry proof; C00 four-role structural gate without trace or metrics; the
remaining 106 runs; complete output hash seal; raw post-run 22/22; unified
offline trace evaluation; frozen descriptive analysis; diagnostic render QA;
read-only review; Draft PR; and one terminal export ZIP.

The exact formal process count is 110: 2 C00 canonical single/basic processes,
16 C00 factorial processes (AB0000 and AB1111 alias canonical strong/full), 68
C01..C17 canonical processes, and 24 sentinel LOO processes. Duplicate effective
configurations are forbidden.

The trace embargo remains absolute until all 110 outputs are terminal and hash
sealed. Any code, tracked config, executable, or provider change invalidates the
formal set and requires restart from the C00 structural gate. Metric-driven
rerun, per-case tuning, output correction, and metric-driven epoch deletion are
forbidden.

CLEAN2 does not authorize D01-D60, the 60x9 matrix, BY3, XB, PG, DA03, DA05,
selected/no-feedback FGO, active nine-factor FGO, QM, QA, contact/FK factors,
final paper figures, automatic CLEAN2 merge, a CLEAN2 tag, force push, or any
deletion of CLEAN1 evidence, raw data, legacy freeze, or failed attempts.

## Retained CLEAN1R2R1 closure

The human authorized the bounded CLEAN1R2R1 chain in this exact fail-closed order:

1. reuse the already verified unique final_v23 static source, runtime configuration, input-generation contract, and evaluator identity without repeating the 18 GB archive inventory;
2. generate clean-real final_v23 input freshly from the current hash-locked BY2 raw sources, with status A1 yaw, no random injection, and no provider-generation trace read;
3. fresh-build `final-v23-freeze@a906c3a2e704eddbd15ceb3f98f1ba8de85dc410` and run one exact-source clean-real parity anchor with every additional paper module disabled;
4. make the active paper-rebuild port pass the same final_v23 parity contract;
5. complete tests/build/review and freeze the parity-restored code commit;
6. regenerate the provider at that code freeze and run the four methods under one common recovered contract, in order: `single_antenna_EKF`, `basic_dual_yaw_EKF`, `strong_dual_yaw_EKF`, and `LegSA_Paper_V1`;
7. open trace only for offline evaluation after all four fresh outputs are sealed and hashed.

The four-method execution is forbidden until both the exact-source clean-real run and active-port parity gates pass. Historical archive inputs and outputs are reference material only and can never become current solver input or current performance evidence. Raw 22/22 integrity, fresh provider lineage, forbidden-input flags, method-effective counters, and evaluator identity remain fail-closed gates.

Archive recovery closed the static tag source, runtime fields, input-builder
behavior, and evaluator identity. It also proved that archived E001
`nominal_none` is semisynthetic: `nominal_none` means no additional degradation
case, while the base command still injects 1.5 degree Gaussian yaw noise with
seed 42 and reads trace during provider generation. E001 is now
`ARCHIVED_SEMISYNTHETIC_DIAGNOSTIC_REFERENCE_ONLY`; it is not the clean input
parity anchor and cannot be solver input or current metric evidence.

The human decision resolves that profile-selection blocker. The current clean
profile keeps the recovered unaffected static fields—time window `66..340 s`,
initialization, covariance/noise, antlever, IMU installation, 21/18 state/noise
dimensions, update order, scheme-C, writer, and evaluator—but rebuilds input
from current raw with `yaw_measurement_std_deg=1.5`, noise injection disabled,
status A1 yaw, and trace excluded from generation. `CURRENT_ACTIVE_EVIDENCE_CONTAMINATED=false` because CLEAN1R2 launched no solver and read no current trace.

The predecessor authorization did not itself authorize CLEAN2. The current
human CLEAN2 authorization above is the sole expansion and does not relax any
data-role, provenance, trace, tuning, correction, or claim boundary.
