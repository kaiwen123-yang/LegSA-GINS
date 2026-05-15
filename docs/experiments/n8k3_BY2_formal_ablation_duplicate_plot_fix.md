# N8K3 BY2 Formal Ablation Duplicate Plot Fix

N8K3 continues PR #48 without entering N9A. It fixes same-category exact duplicate plots that N8K2 did not detect after replacing the original placeholder-like panels.

The focus categories are:
- `01_trajectory`;
- `04_attitude`;
- `07_compare`;
- `11_feedback`.

Duplicate hashes across different figure names in the same category are blockers unless the figure is a documented not-applicable panel or has an allowed reason. Derived `derived_from_n8k_metrics_and_baseline_nav` plots are surrogate visualizations for audit materialization only, not complete runtime variant NAV evidence and not performance claims.

N8K3 does not change algorithms, does not tune feedback policy, does not run the degradation matrix, and makes no paper performance claim.
