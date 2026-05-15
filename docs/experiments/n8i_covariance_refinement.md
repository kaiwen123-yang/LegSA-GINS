# N8I Covariance Refinement

N8I reviews conservative feedback covariance inflation after the N8H visual
validation pass.

Reviewed policies:

- inflation x1;
- inflation x2;
- inflation x4;
- auto residual-proxy inflation;
- block-wise velocity x2 and attitude x4;
- diagnostic attitude x6.

The refinement may recommend more conservative covariance. It does not make an
R-shrink claim, does not use trace/final_v23 tuning, and does not claim paper
performance improvement.

Output report: `FGO_FEEDBACK_COVARIANCE_REFINEMENT_REPORT.json`.
