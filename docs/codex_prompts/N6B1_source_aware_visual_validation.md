# Codex Prompt: N6B1 Source-Aware Visual Validation

Task: run N6B1 as a post-N6B source-aware LSIM/OIM visual validation and
plotted-data coverage audit.

Boundaries:

- keep PR #32 open and unmerged;
- keep PR #21 open and unmerged;
- branch from `main`, not from N7A;
- do not modify solver math;
- do not tune from trace or final_v23 output;
- do not delete epochs;
- do not apply output-only correction;
- do not add Go2 prior or FGO;
- do not commit runtime reports or generated figures;
- do not make paper performance or outperform-final_v23 claims.

Deliverables:

- N6B1 loader, plot generator, coverage checker, sanity checker, decision
  module;
- runner `scripts/experiments/run_n6b1_source_aware_visual_validation.py`;
- audits for N6B1 visual validation and required-figure nonempty gates;
- docs, tests, real runtime reports, and an open PR.
