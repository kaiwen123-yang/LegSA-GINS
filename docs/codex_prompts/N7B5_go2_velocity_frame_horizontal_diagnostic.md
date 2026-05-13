# N7B5 Go2 Velocity Frame Horizontal Diagnostic Prompt

Task: merge N7B4, tag it, then start N7B5 on a fresh main branch to resolve Go2 velocity frame ambiguity and test horizontal-only diagnostic priors.

Required stage behavior:
- do not merge or close PR #21;
- do not merge or tag the N7B5 PR;
- do not use trace or final_v23 output as solver input, frame selector, or tuning signal;
- do not treat Go2 position or velocity as truth;
- do not enable formal Go2 velocity or yaw prior;
- do not implement FGO or output-only correction;
- do not commit runtime CSVs, NAV/STD/EVAL_NAV outputs, summary files, error series, or figures.

N7B5 deliverables:
- frame equivalence review between full-attitude rotation and yaw-only rotation;
- horizontal-only diagnostic prior builder with vertical disabled;
- frame sensitivity activation variants;
- N7B5 decision report;
- audits, tests, docs, and PR.
