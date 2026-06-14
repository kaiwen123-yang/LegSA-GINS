# Runner Provider Lineage

## Scope

This document records runner and provider boundaries for future PAPER10 stages. PAPER10X itself does not run any runner, solver, evaluator, provider generation, or degradation generation.

## Formal Runner Boundary

Formal execution remains tied to the accepted LegSA-GINS runner chain from prior reviewed stages. Diagnostic commands are not paper evidence unless a later stage explicitly promotes them after source and output validation.

Any future runner use must prove:

- planned row identity;
- method identity;
- dataset identity;
- source inputs;
- output directory;
- no overwrite of completed rows unless explicitly authorized;
- trace is evaluation-only;
- feedback provenance is same-case and not trace-derived.

## Provider Boundary

Provider generation must not use trace online. Trace can only enter official evaluation or post-run diagnostics.

Providers that require future evidence freeze include:

- Go2 roll/pitch weak prior;
- Go2 horizontal velocity weak prior;
- selected feedback generation and usage;
- quality-state logging if PAPER10B2 is approved;
- active FGO backend only if a later stage reopens complete-FGO work.

## Runtime Outputs

The following remain runtime-only and untracked:

- NAV / STD / EVAL_NAV;
- RUN_MANIFEST;
- FGO feedback, smoothed NAV, and factor-table CSVs;
- generated degradation CSVs and summaries;
- generated figures;
- raw data and local path manifests;
- conda installers, package caches, archives, and core dumps.

PAPER10X may summarize these materials, but it must not stage the payloads.
