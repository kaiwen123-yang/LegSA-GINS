# Requirements for the next LC02 paper or clarification

A replacement formal primary should remain solution-level, one-receiver GNSS/INS, and scientifically distinct from Pavlasek LC01. It must publish or attribute an executable algorithm with:

- a source-closed state, frame, sign, mechanization, process-noise, measurement, lever-arm, feedback, and reset contract;
- explicit position-only or position-plus-velocity scope;
- a dimensionally coherent adaptive statistic, normalization, thresholds, factor placement, and posterior covariance;
- an explicit innovation standardizer including numerator, centering, denominator, covariance stage, correlated handling, order, floors, and nonfinite behavior;
- a full robust equivalent-covariance/information matrix rule preserving symmetry/PSD where claimed;
- an exact upper-band rejection operation and all-rejected fallback;
- branch prior sharing, execution ordering, fusion statistic, state/covariance fusion, feedback/reset ordering, and a bounded covariance interpretation;
- attributable primary paper/code provenance sufficient for `FAITHFUL_ALGORITHM_REPRODUCTION`;
- compatible solution-level PDOP/quality/uncertainty inputs without using trace or performance to choose semantics.

Alternatively, an attributable author clarification or exact Yin implementation must answer all failed Y4A gates—not merely confirm the already printed Eq. 13 formula or same-prior relation—before Yin can be reconsidered. It must close `L_k` versus `Z_k`; Eq. 8 `V_hat_k` versus Eq. 9 `bar_V_k`; `bar_A_(Xhat_k)`; Eq. 6 normalization and state stage; the standardized residual; Eq. 11's overloaded base/equivalent information semantics; general matrix assembly; zero operation; and feedback/reset ordering. No derived row omission, `L=Z`, `S_ii`, or `bar_A_equivalent=w(tilde V_i) A_base` policy may be promoted solely because it is conventional; Eq. 11's Latin `w` remains glyph-distinct from Eq. 10 Greek `ω` even though the author response relates their weighting-function semantics.
