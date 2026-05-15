# N8I Gate Policy Review

N8I reviews the N8H finding that the default gate accepted all feedback windows
while attitude corrections included spikes above 4 deg.

Reviewed policies:

- default gate;
- attitude max 4 deg;
- attitude max 3 deg;
- combined conservative gate.

The gate decision is allowed to recommend conservative rejection of large
solver-visible correction candidates. It is not allowed to tune from trace or
final_v23 evaluation output.

Output report: `FGO_FEEDBACK_GATE_POLICY_REVIEW_REPORT.json`.
