# N8J Feedback Final Validation Prompt

Task: validate the N8I selected FGO feedback EKF policy.

Required actions:

- merge N8I to main and tag N8I before starting N8J;
- create `stage/N8J-feedback-final-validation` from latest main;
- lock the N8I selected policy;
- run fixed final variants and generate runtime-only outputs;
- generate final reports and required figures;
- audit no output substitution, no future data, no trace/final_v23 tuning, and
  no paper performance claim.

Do not tune gate or covariance in N8J.

Do not commit runtime artifacts or generated figures.

Do not merge the N8J PR or create an N8J tag.
