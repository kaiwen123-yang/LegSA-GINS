# LegSA-GINS Clean Paper Rebuild

LegSA-GINS is rebuilding its paper evidence from immutable raw data. All pre-202607 experiment results, figures, provider payloads, exports, aggregates, and runtime packages have exited active evidence.

## Active Identity

- Git line: `paper-rebuild/202607`
- Active implementation: `src/legsa_gins/paper_rebuild/`
- Active entrypoints: `scripts/paper_rebuild/`
- Active configuration: `configs/paper_rebuild/`
- Active context: `docs/paper_rebuild/ACTIVE_CONTEXT.md`
- Raw inputs: `<RAW_ROOT>`
- Clean generated assets: `<CLEAN_ROOT>`
- Historical freeze: `<LEGACY_FREEZE_ROOT>`

Local absolute paths belong only in the ignored `configs/paper_rebuild/DATA_PATHS.local.yaml`. Tracked files use aliases.

## Paper Method

`LegSA_Paper_V1` is a source-backed EKF with lateral short-baseline dual-antenna body yaw, Raw Doppler auxiliary velocity, source-aware measurement weighting, and weak Go2 roll/pitch plus horizontal-velocity priors. selected feedback, active nine-factor FGO, QA fallback, and multi-state QM as a main innovation are outside this method.

## Evidence Rules

- Every result starts from a raw hash lock and freshly generated providers.
- Trace is evaluation-only.
- final_v23 and LegSA outputs are not solver inputs.
- Go2 observations are not truth.
- No per-case tuning, output-only correction, or metric-driven epoch deletion.
- Synthetic and semi-synthetic results never enter real-data result tables.
- Old results cannot be restored as active evidence by copying or summarizing them.

Read [the clean active context](docs/paper_rebuild/ACTIVE_CONTEXT.md) before any work. Pre-clean history is summarized under `docs/legacy/202607/` and is history only.
