# LC02 formal admission decision

Decision: `NO_GO_LC02_YIN2023_RAEKF_AS_FORMAL_PRIMARY`.

Yin 2023 remains the intended LC02 identity and remains scientifically distinct from LC01, but its RKF and RAEKF branches cannot be admitted as faithful algorithm reproductions. This decision does not authorize an implementation disguised as a diagnostic or policy baseline.

The paper-direct fusion is not the blocker: Eqs. 12–14 uniquely print state fusion, covariance fusion, and the `ϖ` factor, and both branches use the same unmodified prior. Eq. 10 separately closes scalar Greek `ω`; Eq. 11 prints a distinct Latin `w(tilde V_i)` middle multiplier, and the author response says the Eq. 10 weighting function enters Eq. 11 without equating the glyphs. The blocker is the mapping feeding `P_rk`: Eq. 8 `V_hat_k` is never related to Eq. 9 `bar_V_k`; Eq. 9 `bar_A_(Xhat_k)` is undefined; and Eq. 11 overloads the same self-referential `bar_A(tilde V_i)` instead of defining separate base/equivalent information. The adaptive statistic and post-fusion feedback/reset are also unresolved. Missing cross-covariance bounds Eq. 13's interpretation but not its executable formula.

The formal-primary rubric requires all ten hard gates plus `FAITHFUL_ALGORITHM_REPRODUCTION` for RKF and RAEKF. Only four gates pass, and the required branch levels are not met. Accordingly `formal_lc02_admission=false`, `implementation_authorized=false`, `production_solver_authorized=false`, `C00_authorized=false`, `representative_cases_authorized=false`, and `comparison_run_authorized=false`.

If a future study chooses `L=Z`, `S_ii` standardization, Niu-style row deletion, a correlated covariance rule, same-prior parallel branches, and one post-fusion reset, it must be named and claimed as `PAPER_DERIVED_POLICY_BASELINE` unless attributable Yin evidence closes every selection. The audited Yang/Knight/Niu chains supply multiple materially different candidates, so none may be silently selected. The project should instead select a fully source-closed robust/adaptive solution-level paper or obtain an author clarification covering all failed gates.
