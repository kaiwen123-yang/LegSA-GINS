# Chang 2021 full method card

- Candidate identity: `LC02_CHANG2021_FSTCKF`
- Paper: Yuanzhi Chang, Yongqing Wang, Yuyao Shen, and Chunguo Ji, “A new fuzzy strong tracking cubature Kalman filter for INS/GNSS,” *GPS Solutions* 25:120 (2021), DOI `10.1007/s10291-021-01148-5`.
- Binary: 9,843,279 bytes; 15 pages; SHA-256 `8c9b65fe3842f9580b69ffd02f728412861c932c166d1cb4fc9950fa0aaf1da7`.
- Rights: copyright the authors under exclusive licence to Springer-Verlag GmbH Germany, part of Springer Nature, 2021. This is not a CC BY source and is not copied into Git or the stage.
- Review proof: all 15 rendered pages were visually inspected, including Eqs. 1–30; method Figs. 1–5; experiment Figs. 6–14; Tables 1–7; conclusion; references; and the data-availability statement.
- Data statement: datasets are available from the corresponding author on reasonable request. No paper code statement or source repository was found.
- Conditional-stage record: only R0, R1, and R2 executed. Outcome B stopped the transaction before conditional R3 implementation and R4 synthetic validation; neither stage executed and no implementation or synthetic-validation payload was created.
- Figure/table evidence roles: Figs. 1–5 are method-contract or method-parameter evidence; Figs. 6–14 are paper-claim context only. Tables 1–3 are paper-parameter provenance only, while Tables 4–7 are paper-claim context only. Every row is `PAPER_DIRECT`; none is active comparison-performance evidence.

The paper defines a 15-state INS error vector, a six-component INS-minus-GNSS velocity/position residual, a strong-tracking covariance inflation, two velocity/position chi-square statistics, and two fuzzy smoothing factors. The printed “CKF” recursion in Eqs. 5–9 is a conventional linear KF recursion over the linear Eq. 4 model; no cubature points or nonlinear cubature transform appear.

The candidate is not source-closed for formal reproduction. Eq. 12 applies ordinary inverse notation to a 6-by-15 matrix, the two beta factors are not mapped uniquely to all 15 fading coefficients, and the plotted memberships plus local T-S consequents do not specify firing, normalization, aggregation, overlap, or output clipping. The R0–R2 audit therefore reached Outcome B (`NO_GO`); conditional R3–R4 did not execute.
