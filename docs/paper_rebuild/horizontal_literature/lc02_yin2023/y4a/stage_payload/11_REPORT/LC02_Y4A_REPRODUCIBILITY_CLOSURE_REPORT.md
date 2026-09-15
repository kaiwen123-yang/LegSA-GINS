# LC02 Yin 2023 Y4A reproducibility closure

Terminal status: `NO_GO_LC02_YIN2023_RAEKF_AS_FORMAL_PRIMARY`.

This is a completed source/contract audit. It preserves the Y0–Y3 audit-closure PASS, LC01/LC02 non-duplication decision, and BY2 input-availability result. It answers the narrower formal-admission question and stops before implementation, production solver work, C00, representative cases, or comparison.

## Source evidence

The official 28-page VOR (4,550,872 bytes, SHA-256 `b67f07908671bbda54ffd8a3981f7e365ff97f387698d2b558305044f11eec04`) and official 24-page v2 (21,097,265 bytes, SHA-256 `198da0283cabddc97446bf9cf9138d8b7ee0b1d1a78f9bdbbe8265c711302f0c`) are CC BY 4.0. Their Eqs. 6–14 have identical semantics; the update did not repair the unresolved definitions. The official article HTML was also captured as a 104,971-byte Jina UTF-8 Markdown transport (SHA-256 `26784270d28e208184610db5bfcb1dadae4c810885c7f5d52f5240e5acb73426`). That hash identifies transport bytes, not a paper binary.

The supplement search is deliberately bounded: the official notes page lists only HTML/XML/PDF, the full official HTML has no `Supplementary Materials` section, and conventional `s001.pdf` and `s001.zip` endpoints returned HTTP 404. The conclusion is `NO_ATTRIBUTABLE_SUPPLEMENT_FOUND`, not a claim about unpublished material. The paper's data/code statement and focused author, SDUST, GitHub, and GitLab searches produced no attributable Yin implementation.

The official Susy author-response endpoint returned HTTP 403. Its full 11-page text was retrieved through the exact Jina transport URL and retained as 18,305 UTF-8 Markdown bytes, SHA-256 `46c6bd33f49aab98ea0b9333f1ddce3298991ae55422ed440806a7d2dca313ce`; again this is a transport-byte hash, not the original PDF. The authors confirm Eq. 6 `bar_V_k=H_k Xhat_k-Z_k` is a residual, call `L_k` the observation vector without equating it to `Z_k`, call the overloaded `bar_A(tilde V_i)` the equivalent weight, say the Eq. 10 weighting function enters Eq. 11's Latin `w(tilde V_i)` multiplier, and identify inverse equivalent weight as observation covariance. This closes a semantic relation but does not equate the distinct Greek-omega and Latin-w glyphs. They do not relate Eq. 8 `V_hat_k` to Eq. 9 `bar_V_k`, define `bar_A_(Xhat_k)`, distinguish Eq. 11 base/equivalent information symbols, or close the standardizer/general matrix/zero operation.

The cited chain was audited without treating a plausible convention as unique Yin semantics. Four public author-upload full texts were inspected—Knight 2009 and Yang 1999/2001/2002—while Yang 1994 was request-only metadata, not inspected full text:

- Yang, Ren, and Xu 2013 has the official title *Main Progress of Adaptively Robust Filter with Applications in Navigation*, DOI `10.16547/j.cnki.10-1096.2013.01.006`, seven pages. The official journal endpoint exposes metadata/abstract, has null `pdfUrl` and `previewPdfUrl`, and CNKI full text was not accessed. The author response says “Main Process”; official metadata controls.
- Jiang 2020, DOI `10.11947/j.AGCS.2020.20190429`, is exactly a one-page 49(10):1376–1376 dissertation synopsis; no attributable full dissertation was accessed. Jiang et al. 2021, DOI `10.1007/s10291-021-01165-4`, is an 11-page subscription article under an exclusive Springer license; official Springer and NCWU metadata do not expose its equations.
- Knight and Wang 2009, DOI `10.1017/S0373463309990142`, was checked at the exact Cambridge record, UNSW metadata, and a public author-attributable ResearchGate upload whose reuse license is unstated. Knight is Yin's inline Eq. 10 citation and points to Yang et al. 1999, but the accessible material does not uniquely define Yin's Kalman standardizer or zero operation.
- Yang et al. 1999, DOI `10.1007/s001900050252`, is the direct Knight IGGIII source. Its attributable author upload uses `v_i/sigma_i`, MAD robust scale, a zero static weight, and middle exponent two—materially different from Yin's printed exponent three.
- Yang, He, and Xu 2001, DOI `10.1007/s001900000157`, uses `V_i/r_i` and a dependent max-based mapping. Yang, Song, and Xu 2002, DOI `10.1007/s00190-002-0256-7`, uses symmetric bifactor `sqrt(c_ii c_jj)` handling and a zero factor that eliminates a static observation. Yang 1994, DOI `10.1007/BF03655325`, was subscription/request-only, so its exact dependent-observation equations were not inspected. These are distinct candidate completions, not a unique Yin selection.
- Niu et al. 2022 was inspected from its official 34-page CC BY PDF (13,374,059 bytes, SHA-256 `96b953d6ebd819a620948767c90cc78ad544efe8b00a5bf9ab9ae328bcdec487`) and attributable TCRTKINS commit `13e8fa1a988f673c43af70746de1bcbeb1ec2ea3`, tree OID `00159f613872e6e9286ddfb5bead2c11b8d6c82f`. Niu supplies one candidate: `s_i/sqrt(S_ii)`, correlated covariance inflation, and upper-band row deletion. Yin cites Niu for a standalone RKF experiment, cites Knight inline for Eq. 10, changes the middle exponent and thresholds, and therefore does not uniquely adopt that implementation.

The post-publication SDUST patent CN117647251A (21 pages, 1,146,875 bytes, SHA-256 `83069a9fa7441468ade83c9295e8ab440b0942506229dfbbfc22382e76934edd`) is author/institution attributable but not the 2023 algorithm: it uses a 4D position-plus-heading measurement, 0.8/0.2 fusion, exponent two, and different improved-R powers. Its measurement-vector covariance wording competes with Yin's state-covariance wording, so it strengthens non-uniqueness.

The acknowledged KF-GINS source is pinned separately: `src/kf-gins/gi_engine.cpp` at commit `08f9fce66028c65727b3f3c53f34f7dfd5a3c1c3`, SHA-256 `f6295267e0d1a48d41284c4fe7ea25cba7225367c4fd2e03f65e5e334ded4260`, closes the base F/G/update; the frozen Y0–Y3 `src/kf-gins/insmech.cpp` source is a separate provenance identity. Neither supplies Yin's adaptive/robust branches.

## Mathematical closure

Closed: the base 21-state ESKF; position-only 3D measurement; improved `PDOP^2 Q r_i^2`; scalar AKF gain/update/covariance equations and `k=1`; scalar Eq. 10 IGGIII thresholds `k0=1.15`, `k1=4.45` and exponent-three factor; identical unmodified priors and separate branch results; Eq. 12 state fusion; Eq. 13 convex covariance fusion; and Eq. 14 threshold `c=1` with branch factors 0.85/0.15.

The paper glyphs are frozen exactly. Eq. 10 uses Greek `ω` (U+03C9 omega) for the component IGGIII weight; Eq. 11 prints Latin `w(tilde V_i)` as its middle multiplier; and Eqs. 12–14 use `ϖ` (U+03D6 varpi) for fusion. The author response connects the Eq. 10 weighting function to Eq. 11 without erasing the glyph distinction. Legacy `v/omega` is compatibility notation only and must not relabel the fusion glyph. The explicit compatibility/errata rows map `V_k` to `bar_V_k`—not `V_hat_k`—`A_k` to `bar_A_k`, and `A(e_V_i)` to `bar_A(tilde_V_i)`; none is paper-direct. Eqs. 7 and 14 retain the printed absolute values: `|Delta_X_tilde_k|<=k`, `k/|Delta_X_tilde_k|`, and `|Delta_X_tilde_k|<=c`. The fact that the printed square root would be nonnegative when defined is only a derived equivalence.

Eq. 6 is transcribed exactly as `bar_V_k=H_k Xhat_k-Z_k`, `Delta_X_tilde_k=sqrt(bar_V_k^T bar_V_k/tr(P_(bar_V_k)))`, and `P_(bar_V_k)=Phi_k P_(Xhat_(k-1)) Phi^T+Q_k`, with no explicit index on the right `Phi`. A `Phi_(k-1) P_(k-1)^plus Phi_(k-1)^T` mapping is only an unselected `PAPER_DERIVED` candidate.

Not uniquely closed: the Eq. 6 state stage/dimensional normalization; `L_k=Z_k`; Eq. 8 `V_hat_k` versus Eq. 9 `bar_V_k`; undefined Eq. 9 `bar_A_(Xhat_k)`; standardized-residual numerator/centering/denominator/covariance stage; Eq. 11's overloaded self-reference; general correlated matrix construction; the zero-information operation; and fusion-before-feedback/reset orchestration. Eq. 9 exactly prints `Omega=bar_V_k^T bar_A_k bar_V_k+alpha_k bar_V_k^T bar_A_(Xhat_k) bar_V_k=min`. Eq. 11 uses the same `bar_A(tilde V_i)` on the left and low/middle right branches, with Latin `w(tilde V_i)` additionally multiplying the middle RHS, while prose equates the overloaded `bar_A` symbol to `R_i^-1`. The author response says the Eq. 10 weighting function enters Eq. 11, but `bar_A_equivalent=w(tilde V_i) A_base`, `A_base=R_i^-1` remains only a derived conventional split. The printed high branch is strict `|tilde V_i|>k1`, but the inclusive middle expression reaches zero at equality. One non-executable printed singular path and at least two executable unselected completions—row omission and a positive infinite-variance limit—remain. Cross-covariance is an Eq. 13 interpretation limitation, not ambiguity in the executable convex equation.

Twenty-eight deterministic standalone linear-algebra oracles pass. They compute and verify the 1D and 3D EKF identities; AKF `alpha=1`; the Eq. 10 inlier/middle factor; inlier nominal information only under the explicitly declared `PAPER_DERIVED` conventional Eq. 11 split; the one-singular-plus-two-unselected zero-policy boundary; exact Eq. 12/13 fusion; N/E/D permutation equivariance; and the unit exponent `2*0 + 0 + 2*1 = 2`. They cannot select the missing Eq. 11 semantic.

## Admission decision

The base model, measurement scope, improved R, and no-performance-completion gates pass. Six semantics gates fail. Branch levels remain:

- `YIN2023_EKF`: `FAITHFUL_ALGORITHM_REPRODUCTION`.
- `YIN2023_AKF`: `FAITHFUL_MODULE_REPRODUCTION`.
- `YIN2023_RKF`: `PAPER_DERIVED_POLICY_BASELINE`.
- `YIN2023_RAEKF`: `PAPER_DERIVED_POLICY_BASELINE`.

`formal_lc02_admission=false`, `implementation_authorized=false`, `production_solver_authorized=false`, `C00_authorized=false`, `representative_cases_authorized=false`, and `comparison_run_authorized=false`.

The frozen Y0–Y3 manifest contains exactly 47 files and has SHA-256 `2a20c89f0fec71c241cc736680f78991e1fff9cc086c17e5fb644fab2e2e239f`. The 32-file history is initial draft `4798a559ccf95dd357fe4eb37f7610069e2576c3a864c926b5be2cd74203891a`, first correction `2f0cd31647f83bc11ff5810ef7927cea9cd9704ef4d7195d67efa773e35ca1a8`, second correction `bbc2b34d2f31767e778b00dea6f8ab4e491ab3cbc98dec5354ce79dadb4031b3`, third correction `f073ed1d1964814683d10cf4a761a88b97408496109664adbbd9d566b8067ee6`, then this final two-blocker correction. Its final aggregate is emitted by the guarded repair result rather than embedded here because this report is part of that aggregate. This remains an uncommitted-draft correction, not first-write publication.

## Access and execution boundary

Administrative validation content-read all 47 original files for integrity hashing, parsed 36 original structured JSON/YAML/CSV files, semantically checked one Y0 status document's terminal/authorization gates for preservation, and parsed 22 Y4A structured files; the augmented validator therefore traverses 58 structured files. The two Canonical files were hash-read only.

The C00 forecast reuses exactly four user-accepted frozen input-contract facts: 1,510/1,510 epochs with `Q=1`, PDOP minimum 1.13, PDOP maximum 1.74, and per-axis covariance variation. That authorized reuse required zero new Y0–Y3 scientific content opens and is distinct from old performance/runtime/trace reuse, which remained zero. New BY2/raw, trace, reference, native-output, prior-runtime, and internal comparison-method scientific opens were zero. Niu/TCRTKINS and Yang/Knight were allowed cited-source evidence only. No LC01 or Canonical scientific execution/content use occurred; all run counters remain zero.

## Durable validation

- Scoped exact command: `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src python3 -m pytest -q tests/paper_rebuild/test_lc02_yin2023_y4a.py` — return code 0; 16 passed, 0 failed, 0 skipped.
- Combined exact command: `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src python3 -m pytest -q tests/paper_rebuild/test_lc02_yin2023_y0_y3.py tests/paper_rebuild/test_lc02_yin2023_y4a.py` — return code 0; 36 passed, 0 failed, 0 skipped.
- Full exact command: `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src python3 -m pytest -q tests/paper_rebuild` — return code 1; 1,082 passed, 2 failed, 20 skipped, 0 new failures. The exact unchanged failures are `tests/paper_rebuild/test_horizontal_phase4_c00.py::test_preflight_hash_only_collision_and_paper_closure_when_available` and `tests/paper_rebuild/test_horizontal_phase5_c00.py::test_dirty_untracked_source_snapshot_is_hash_complete_and_explicit`.

Both LC02 validators, all structured JSON/YAML/CSV parsing, Python compile/import, exact 79-file union/parity, special-entry/PDF/ZIP rejection, original-47 immutability, Canonical preservation hashes, and `git diff --check` are required to pass. These results validate only the audit package and authorize no subsequent implementation or execution.
