# Independent arc phase static review

Reviewer: independent research-map agent. Status: STATIC_REVIEW_ONLY; no tests, saved-model qualification, raw data, reference, solver or navigation execution by this reviewer.

## Read scope and source identity

- src/legsa_gins/paper_rebuild/carrier_phase/arc_phase_difference.py: SHA256 3898eb95f2621f483c80ecd0d67b9fd6dcf27135673a755b11f8650a7d66ef12
- scripts/paper_rebuild/carrier_phase/arc_phase_saved_model_qualification.py: SHA256 8eb23c992ba37861adf5f662417c17690a3955d8fd61675f37905a760a351e73

No new mathematical/source blocker found in these read versions. Future small plan/budget binding edits require their own identity check; this review does not certify unreviewed changes or actual 921-block execution. At the review snapshot, this reviewer had no 921-block completion evidence.

## Findings

Physical ambiguity columns bind receiver-pair SD arc tokens and wavelength. Endpoint maps F0 and F1 must produce exactly identical physical integer coefficients; a changed pivot can cancel algebraically without inheriting a changed physical arc. Both endpoint geometries are retained: z predicts G1 b1 minus G0 b0, with corresponding two-pose left-perturbation Jacobian. Integer cancellation does not erase geometry, anchor, lever-arm, bias, timing or state/measurement-correlation error.

The saved-model runner examines the full interval of per-receiver ARC_EVENTS, including intermediate events without paired model rows. Equal endpoint tokens alone do not suffice. However, legal continuity here is conditional on saved receiver metadata and model conventions. It cannot certify that no physical cycle slip occurred or supply integer truth.

Unknown cross-time error is not replaced by zero. The geometry-only path reports separate endpoint Q contributions and the conditional second-moment bound 2(Q0+Q1). This bound requires valid endpoint second-moment upper bounds; RAWX working sigmas do not establish that premise. It is not calibrated covariance and does not bound state/measurement or between-factor dependencies.

Real availability, latency, attitude rank, direction point and joint covariance remain NA; navigation admission remains false. Geometry rank concerns the unconstrained two-baseline algebra, not absolute heading observability. The future factor interface requires declared availability and explicit covariance policy, but still does not implement admission or endpoint-consumption bookkeeping.

The fixed denominator is the original three windows, 921 disjoint five-epoch blocks with endpoints 0 and 4; previous singleton valid flags are only cross-tabulated, not used to select blocks or tune anything. No physical independence is inferred from endpoint nonreuse. Local PSD/rank checks are floating-point algebraic qualifications, not strict numerical certificates or physical sensor qualification.
