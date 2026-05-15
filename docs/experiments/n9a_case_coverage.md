# N9A Case Coverage

N9A writes `N9A_CASE_COVERAGE_REPORT.json` and
`n9a_by2_case_coverage.md`.

Every discovered BY2 formal-ablation case receives:

- a 01-14 figure directory tree;
- a case-level review under `09_case_review`;
- a runtime case review under `<N9A_CASE_REVIEW_DIR>`;
- a case-level `14_audit_sanity` panel set.

Case states are:

- `complete`: all expected files exist and any unavailable source is documented
  not-applicable;
- `partial`: at least one file is missing or lacks a documented reason;
- `missing`: required case not discovered.

N9A does not delete epochs or bad data to improve a case state.
