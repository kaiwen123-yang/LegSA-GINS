# N6B Source-Aware Policy Refinement Prompt

Goal: refine source-aware LSIM/OIM policy on the existing PR #31 branch.

Scope:
- keep PR #31 open and unmerged;
- do not create tags or a new PR;
- keep final_v23 reference untouched;
- no Go2 prior, no FGO, no paper performance claim;
- keep source-aware weighting inside `R_scaled -> EKFUpdate`;
- use OIM innovation covariance `S=HPH^T+R`;
- keep LSIM metadata-only;
- keep N5D1 spike times as after-run sentinels only;
- output runtime N6B reports and figures outside Git.

Runtime paths are supplied as command-line role aliases and must not be written
into tracked docs, configs, or scripts.
