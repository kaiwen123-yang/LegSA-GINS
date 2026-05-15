# N8I Feedback Ablation Gate/Covariance Prompt

Task: refine FGO feedback EKF policy after N8H visual validation.

Required actions:

- build the N8I policy grid;
- run gate, covariance, window, mode, and attitude-spike reviews;
- generate runtime-only reports and figures;
- keep FGO feedback as EKF update, not output substitution;
- use solver-visible diagnostics only;
- keep trace/final_v23 out of tuning;
- keep primary position feedback disabled except diagnostic PVA;
- make no paper performance claim.

Do not commit runtime artifacts or generated figures.

Do not merge the N8I PR or create an N8I tag.
