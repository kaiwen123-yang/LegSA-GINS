# N9A Category Coverage

N9A writes `N9A_CATEGORY_COVERAGE_REPORT.json` and
`n9a_by2_category_coverage.md`.

Coverage is evaluated case by case over the unified 01-14 schema. A category is
complete when every expected file exists and is nonempty, or the figure is
explicitly documented not-applicable with a reason.

Important boundaries:

- `02_position_errors` is the core positioning category.
- `01_trajectory` cannot be used alone for precision conclusions.
- `05_consistency` is about confidence/coverage, not accuracy ranking.
- `11_feedback` applies only to feedback-applicable cases by variant semantic
  spec.
- `13_degradation_meta` must mark missing or not-applicable metadata instead of
  inventing degradation inputs.
