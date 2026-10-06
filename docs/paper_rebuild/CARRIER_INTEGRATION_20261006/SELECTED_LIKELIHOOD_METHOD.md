# Selected-observation likelihood: mathematical and implementation boundary

This is an independent experimental acquisition method implemented in `src/legsa_gins/paper_rebuild/carrier_phase/selected_likelihood.py`. It changes the observation likelihood used for integer search. It is not a faster implementation of the original full-likelihood selected-class problem, and it is not a claim of a novel ambiguity-resolution method.

## Observation restriction

For one selection epoch, write the existing model as

    y = A_S n_S + A_U n_U + B b + e,    e ~ N(0, Q),    ||b|| = L.

S is chosen by the existing `preselect_partial_labels` rule from exactly the registered selection epochs. The default new policy uses five epochs, minimum four ambiguities, maximum six, and phase-geometry rank three at every epoch. Geometry, Q, explicit arc identity and deterministic label tie-breaking drive selection; observed y, solved integers, residuals and future validation outcomes do not enter that rule.

Keep the original row indices R for which every entry of A_U is exactly zero. Native code rows are retained, as are phase rows involving only selected labels. A phase row mixing selected and unselected integers is withheld. Construct

    y_R = y[R]
    A_R = A[R, selected source columns]
    B_R = B[R, :]
    Q_R = Q[R, R].

Q_R is the principal marginal covariance of retained observations. Shared-pivot, cross-frequency and code/phase correlations among retained rows are preserved. It is neither the covariance diagonal nor the Schur conditional covariance obtained by conditioning on discarded measurements. No discarded residual is used to adjust retained y. Columns follow the selected-label order; rows retain their original order.

Across epochs, the new method shares n_S and gives every epoch an independent b_k constrained by its original length L. Epoch covariances remain block diagonal, as required by the existing exact sphere search. The objective is

    J_selected(n_S) = min_{||b_k||=L} sum_k
        (y_Rk - A_Rk n_S - B_Rk b_k)' Q_Rk^(-1)
        (y_Rk - A_Rk n_S - B_Rk b_k).

The original partial method instead minimizes the full observation objective over both all unselected INTEGER nuisance coordinates and every b_k, for each fixed selected class. Discarding observations is not that integer profiling operation, and no unselected integer is set to zero. Rankings, likelihood gaps and absolute objective scales can change. When all source labels are continuous and selected, all rows return and the original likelihood is recovered up to ambiguity-column permutation.

There is less observation information to search and no unselected integer dimension in the reduced problem. Neither faster certification nor better acceptance is guaranteed. A reduced-likelihood global certificate proves only the best and second integer classes of this new objective; it does not certify the original full-data profile objective or integer truth.

## API and identity

`prepare_selected_likelihood(models, length_m=..., policy=...)` returns `SelectedLikelihoodPlan` with `selection`, `search_plan`, `epochs`, and `supports`. A ready plan contains a new `PartialSearchPlan`; an unavailable subset has `search_plan=None` and cannot be solved. Supports record original row indices, withheld indices, source-column mapping, and code/phase/source counts. All reduced numerical arrays are copied. `problem` and `fingerprint` refer to the actual reduced solver input.

`solve_selected_likelihood(plan, lambda_library, ...)` returns `SelectedLikelihoodResult`. Its `result` is the existing `TemporalResult`; its likelihood kind and reduced-problem fingerprint distinguish the result from a full-likelihood search. It requests an actual new exact search with the selected labels, not projection of any old top-two list. The default sphere backend is Python; an explicitly supplied `sphere_library` may be forwarded, but the registered 120-case experiment specifies Python.

`freeze_selected_likelihood_candidates(plan, wrapped_result, source_id=...)` requires the matching wrapper, matching numerical fingerprint and an existing exact selected-class certificate. A changed plan, unrelated full result, unavailable subset or uncertified search cannot be frozen. It reuses the existing candidate-freeze logic and prefixes source identity with

    SELECTED_OBSERVATION_MARGINAL_Q_V1:<reduced-plan fingerprint>:<caller source>.

The original integer-selection time is preserved. Integration must also record the selected likelihood in its input contract and must not reuse old full-likelihood cases. Original future models, strict full-subset arc continuity, code-plus-fixed-phase row support, existing covariance principal submatrices and all existing admission/diagnostic gates remain unchanged. This module does not choose rows using future outcomes or provide a fallback to the original objective.

## Completed synthetic verification

Ubuntu 22.04 WSL: six new focused tests and 21 existing partial-method tests passed, **27 total**. No real-data search or frontend run was performed by this implementation task.

- An independently indexed native multi-frequency model confirms selected y/A/B rows and principal Q, including nonzero shared-pivot/cross-group/code-phase correlations. The principal covariance is explicitly shown to differ from the conditional Schur covariance.
- A general mixed-dependency design confirms that even a row involving selected integers is withheld when it also depends on an unselected integer. Original row order and selected-label column alignment are retained.
- Permuted source columns, missing/reset labels and input-copy isolation are checked. Rank-deficient selection produces no search problem.
- Selecting all continuous source labels restores original y/B/Q/times/lengths and the same A up to column permutation.
- A moving-baseline, known-integer, two-epoch/four-selected-integer problem agrees with an independent dense GLS plus secular-sphere oracle over 81 enumerated integer vectors, for both best and second candidates. The exact search certifies the global problem; the finite enumeration is a numerical cross-check, not an independent proof of the search certificate.
- Adding 1e6 metres only to discarded phase y leaves selection, reduced numerical fingerprint, best and second candidates unchanged. Passing an unwrapped old result or mutating the reduced problem after solving prevents candidate freezing.

These tests establish the intended transformation and certificate boundary. They provide no real-data accuracy, availability, false-fix probability or real-time performance claim. The new registered comparison must retain original and selected-observation likelihood results as different methods.
