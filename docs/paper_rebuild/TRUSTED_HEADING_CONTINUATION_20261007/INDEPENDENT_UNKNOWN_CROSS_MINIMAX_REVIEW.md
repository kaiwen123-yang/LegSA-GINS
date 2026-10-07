# Unknown-cross cancellation witness: independent mathematical review

Status: PURE_MATHEMATICAL_REVIEW_ONLY. No data, sealed dump, solver or scientific readout executed by this reviewer for this proposition.

## Proposition and proof

Fix the declared prior information set and all model choices. Let e be the centered estimation error, r=He+n the centered innovation, P=E[eeᵀ], R=E[nnᵀ], P⪰0, and let the uncertainty set permit every cross second moment C for which [[P,C],[Cᵀ,R]] is PSD. Let W⪰0 be a fixed full-state scoring matrix. If V=R−HPHᵀ⪰0, choose a zero-mean v independent of e with E[vvᵀ]=V, and set n=−He+v. Then C*=−PHᵀ and

    [[P,C*],[C*ᵀ,R]] = [[I,0],[-H,I]] diag(P,V) [[I,-Hᵀ],[0,I]] ⪰ 0.

The innovation is exactly r=v and has zero cross moment with e. For any fixed linear correction K, the posterior error e−Kr has second moment

    P_K(C*) = P + K V Kᵀ.

Thus tr(W P_K(C*))≥tr(WP)=T. K=0 produces T for every allowed C, so

    inf_K sup_C tr(W P_K(C)) = T,

and K=0 is minimax over this uncertainty set. This is stronger than failure of a particular Young grid or Young continuous family: no fixed linear correction guarantees strict weighted-trace improvement over all permitted cross moments. It does not imply that every actual C is unhelpful.

## Essential boundaries

- Center e and innovation around the same available prior mean. Native stored dx is a mean, not an additional covariance term. If uncentered second moments/bias are used instead, their mean restrictions must admit the witness; do not label a second-moment result covariance while ignoring a known bias constraint.
- No P inverse is needed; deterministic singular clones are allowed. Use the complete declared state P and H. The original current21 score can be embedded in full24 W with zero clone weights.
- W or V may be semidefinite. K=0 is minimax but need not be unique. No claim that every nonzero K strictly worsens every metric follows.
- The displayed proof treats K fixed conditional on the declared information/model. A residual-selected K is a nonlinear/selection rule and requires a separately stated argument, not silent reuse of the displayed constant-K covariance formula.
- The uncertainty set must genuinely contain C*. Known source structure, independence of an actual error component or other constraints may exclude it. This is a worst-case working-model witness, not evidence that SDK physics realizes cancellation.
- When P/R are only upper bounds, a class allowing all joint moments up to those bounds includes the saturated construction. The minimax conclusion still requires that exact class; it cannot be transferred to a smaller physically justified class without checking feasibility.
- V not PSD only means this sufficient witness is unavailable. It does not prove that a beneficial robust correction exists. Boundary numerical uncertainty must remain UNRESOLVED.

## Bounded verification is worthwhile

A separately registered single pass over all 2510 already sealed full P/H/R records, with 0 native/evaluator/raw/reference calls, would distinguish the large unknown-cross class from the former Young-family-only conclusion. Compute the 3×3 V directly; preserve symmetry residual, scale, minimum eigenvalue/margin and three-way status. No loading, clipping, tolerance search, K search or epsilon scan. Prior numerical PSD qualification remains an explicit premise; tiny floating negative P modes prevent describing ordinary floating checks as exact interval certification.

Six small synthetic boundaries suffice before the real saved-record diagnostic: strict scalar V>0 (including a C=0 improvement that fails under C*), V=0 nonuniqueness, V not PSD/condition inapplicable, singular cloned P without P inversion, non-diagonal R and consistent coordinate/unit changes, and mean-centering plus near-boundary numerical unresolved behavior. They should verify the construction and trace inequality, not tune the data to make the theorem qualify.

## Initial implementation static review (before local execution)

Read script SHA03517da2e9a51b432bea9f56c96a4983851236cdf2f9d002384ccf8b193bc774 and ten-function test SHA23fefe387005a13e41226aa1778526f654d50024f2f47f31fdf217d9a65c38e0. Direct full-P D/V/C arithmetic, normalized input qualification, strict-negative versus unresolved PSD-boundary and exact-zero remainder handling implement the intended working-matrix distinction. No tests executed by reviewer.

Required output correction: skip_is_unique=false is not equivalent to not claiming uniqueness. Scalar W>0,V>0 has unique minimax K=0, while semidefinite cases may not. Use a not-analyzed/no-uniqueness-claim field unless uniqueness is actually established.

Before real CLI registration, bind exact sequence/count tuple to BY2/687, BY2H/666, BY2O/1157 and bind each registered dump hash to the pinned old native seal.files entry, not just independent plan hashes. Guard finite T/C/normalized values so extreme unit inputs cannot emit Infinity as a scientific result. These are static review requests; subsequent source identity and repairs must be verified separately.

Repair recheck: current script SHA0a5acd445edb917a370feceacef68b3cd42428d68e9896d2c9f1345f3880ff35 and test SHA812fdf0e3f0da7d2f56393c5f158ebbf039f66cbcdfed78010489d9fdd333d30 now use skip_uniqueness_established=false, enforce the exact three-sequence/count tuple, bind each dump digest to old native seal.files, and reject nonfinite normalized matrices/spectra and direct T/D/V/C arithmetic. These requested repairs were verified by source reads only; no test or real diagnostic was executed by this reviewer.
