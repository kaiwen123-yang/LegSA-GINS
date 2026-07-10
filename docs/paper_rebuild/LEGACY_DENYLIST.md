# Legacy Evidence Denylist

## Denied As Active Input Or Evidence

The clean rebuild must not read or cite as active performance evidence:

- legacy experiment and stage runtime trees;
- old reports, exports, AI-context packages, maintenance archives, and literature-comparison outputs;
- old plotting batches and generated figures;
- old provider payloads or provider-ready directories;
- old NAV, STD, EVAL_NAV, epoch output, feedback observations, or factor tables;
- old run manifests when used to reconstruct a result;
- old aggregate tables, text summaries, or summary-reconstructed rows;
- prepare-only, blocked-only, frame-unsafe, yaw-invalid, superseded, or quarantined outputs;
- legacy archive binaries;
- performance material under `<LEGACY_FREEZE_ROOT>`.

## Denied Dependencies

- hard-coded legacy runtime paths;
- automatic discovery under old experiment or stage roots;
- old runner side effects or implicit provider fallback;
- `src/legsa_gins/reporting/by2_algorithm_runner.py`, which is retained as a legacy runner but is forbidden to the clean rebuild;
- status fallback presented as a full Raw Doppler or carrier/DD backend;
- final_v23, LegSA, benchmark, external-method, or trace output as solver input;
- receiver IMU presented as Go2 body IMU;
- synthetic or semi-synthetic rows presented as real raw results.

## Allowed Historical Use

The following may be used only for provenance and protocol reconstruction:

- verified Git history and bundle;
- archived PR metadata and patches;
- selected 60-type/9-seed and classic-18 specifications;
- fixed physical yaw/frame rules;
- data-role, trust/denylist, and claim-boundary lessons;
- unique source candidates held for human review.

Historical material never becomes active performance evidence by being copied, summarized, zipped, or renamed.
