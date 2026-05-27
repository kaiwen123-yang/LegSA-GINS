# Historical Blocker: N8K Placeholder Plots

This blocker is historical and resolved by N8K2-N8K6. It remains documented because stale prompt text may still refer to it.

## Original Blocker

N8K initial formal ablation plotting produced many figures, but manual review found that some `applicable=True` outputs were not credible figures:

- placeholder plots.
- low-information outputs.
- duplicate templates.
- semantic filename/content mismatch.
- same-variant cross-category duplicates.
- feedback applicability errors.

## Resolution Chain

- N8K2 removed applicable placeholders.
- N8K3 fixed same-category duplicate semantic plots.
- N8K4 fixed semantic filename alignment.
- N8K5 fixed same-variant cross-category duplicate outputs.
- N8K6 fixed A0 feedback applicability blocker.

## Current State

- This file is historical provenance only and is superseded for current operations by `current_state.md`, `PROJECT_CONTEXT.md`, `PLANS.md`, `AGENTS.md`, and `N9G1A_CONTEXT_LOCK_REPORT.md`.
- PR #48 is merged.
- N8K final merge review passed.
- Tag `N8K-v0.1-BY2-formal-ablation-plot-audit` exists.

## Remaining Lesson For N9A

N9A must not repeat the same failure mode. A figure existing on disk is not sufficient. Each figure needs source role, real data availability, frame/time alignment, metric sanity, semantic sanity, and plot permission.
