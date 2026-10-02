# CLEAN4 / Canonical-541 Plotting Refinement Summary

- Final mode: review, local correction, targeted redraw, and reuse of acceptable figures.
- Scientific reruns: none. No solver, provider, external method, Hartley filter, MATLAB/GINav, evaluator, aggregate, or Canonical runner was executed.
- Concurrency: 16 workers requested/effective/peak; 10-second heartbeat enabled.

## Horizontal full plotting

- Status: `PASS_CLEAN4_HORIZONTAL_FULL_PLOTTING_COMPLETE`
- Checked: 66 / 66 plot families
- Targeted redraw / reuse / failure: 28 / 38 / 0 families
- Outputs: 213 PNG, 198 PDF, 198 SVG, including 15 contact sheets
- Resolution QA: 213 / 213 PNG have a long edge of at least 4096 px
- Main refinements: EXT04 policy diagnostics, LC formal/coverage composites and GINav mechanism views, Hartley structural plots, Internal C00 unit separation, Canonical-541 A04/F04 paired views, and the solution-level cross-layer formal composite
- Formal/diagnostic boundary: formal C00 figures remain separate from the 77-epoch diagnostic-only family
- Catalog / QA / Gallery: `PLOT_CATALOG.csv` (66 families), `PLOT_QA.csv` (213 PNG), `99_GALLERY/PLOT_GALLERY.html` (66 cards)

## Canonical-541 paper-focused plotting

- Status: `PASS_PAPER_FOCUSED_PLOTTING_COMPLETE`
- Checked: 483 / 483 figures
- Targeted redraw / reuse / failure: 143 / 340 / 0 figures
- Outputs: 483 PNG and 18 PDF
- Resolution QA: 483 / 483 PNG have a long edge of at least 3840 px
- Main refinements: direct dual-root error-sidecar resolution, strict NAV/error time alignment, case-specific NAV time axes, shared visible Truth with method-specific frozen errors, wrap-safe yaw display, concise subtitles, 4K normalization, and unified P15-P18 layouts
- Catalog / QA / Gallery: `PLOT_CATALOG.csv` (483 figures), `PLOT_QA.csv` (483 PASS), `PLOT_GALLERY.html` (483 cards)

## Final assessment

- Forbidden in-figure wording: no matches in either final plotting root.
- Scientific blocker: none. The detected issues were plotting logic, labeling, resolution, or layout issues and were repaired locally.
- Manual screening focus: horizontal `09_HARTLEY_OBSERVABILITY`, `11_CANONICAL541`, and `99_GALLERY`; paper-focused `13_SELECTED_TIME_SERIES`, `15_PAPER_CANDIDATES`, and `PLOT_GALLERY.html`.
- The optional `<HISTORICAL_PATH_002>` mirror files named in the task were not present; the current files inside the two authoritative plotting roots were used and updated.
