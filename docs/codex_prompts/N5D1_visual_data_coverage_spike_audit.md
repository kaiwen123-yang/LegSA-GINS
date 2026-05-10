# N5D1 Visual Data Coverage and Raw Doppler Spike Audit Prompt

Stage goal: repair N5D visual validation by requiring plotted sample coverage,
regenerating non-empty clean ablation figures, auditing raw Doppler velocity
spikes epoch-by-epoch, fixing raw-vs-receiver velocity semantics, de-duplicating
stress evidence pairs, and producing N5D1 decision reports.

Hard boundaries:

- Do not merge PR #30.
- Do not create any N5D or N5D1 tag.
- Do not enter N6A implementation.
- Do not modify filter math, tune gates, delete epochs, or apply output-only
  correction.
- Do not treat NAV-PVT velocity or `.gnss` velocity as raw Doppler.
- Do not use RTKLIB position solutions as solver input.
- Do not implement LSIM/OIM, Go2 prior, source-aware weighting, or FGO.
- Do not make a paper performance claim or outperform-final-v23 claim.

Required outputs:

- N5D1 modules for plot-data coverage, clean ablation plot repair, spike audit,
  plot semantics audit, and decision logic.
- Runtime-only N5D1 reports and figures.
- Audits and tests that fail when mandatory figures have no plotted data.
