# Pilot phase diagnosis audit

Read-only analysis of four saved cases. No reference/raw payload reads, CILS searches, native navigation or threshold changes. Reproduction: python3 review_saved_glrt.py.

The independent implementation assembles five independent 3-D baseline states directly from saved NPZ files, reconstructs physical SD-cycle fault columns from satellite/pivot/arc metadata, uses Cholesky whitening plus QR and independently checks each alternative by augmented least squares. It imports no project estimator/diagnosis functions.

All four decisions are numerically reproduced. Phase values and integer matrix A are in metres and metres/cycle respectively, N is integer cycles; the fault columns are ±wavelength metres/cycle with the pivot affecting every group DD. Retained row sets equal the admission receipts; unknown or unselected phase rows are excluded, never fixed to zero. Cb is full-rank conditional GLS covariance with full within-epoch Q; across-epoch Q is the registered block-diagonal working model.

| Case | Retained rows / df | Residual cost | Tested hypotheses | Holm rejected SD signals |
|---|---:|---:|---:|---|
| partial_0190.00 | 135 / 120 | 87.020608063 | 11 | 2:36:0:0, 3:27:0:0, 3:43:0:0 |
| partial_0196.00 | 110 / 95 | 106.814508049 | 12 | 0:19:0:0, 0:6:3:0, 0:11:3:0 |
| partial_0198.00 | 109 / 94 | 64.708400103 | 12 | 2:36:0:0, 2:10:6:0, 2:36:6:0 |
| full_0198.00 | 134 / 119 | 91.934696788 | 19 | 2:36:0:0, 2:36:6:0 |

The largest discrepancy in residual/GLRT improvements or directly refitted alternative costs is below 1.5e-13; Cb, baseline centres, rows and hypothesis support agree. Full and partial 0198 use exactly the same eight shared integer values. Both reject Galileo SV36 E1 and E5b, so the partial rejection is not explained by changing its shared integers.

| Case | SD signal (GNSS:SV:signal:freq) | Bias cycles | Bias mm | Delta chi-square | Holm p |
|---|---|---:|---:|---:|---:|
| partial_0190.00 | 2:36:0:0 | -0.058065 | -11.049 | 11.999413 | 0.0047895571 |
| partial_0190.00 | 3:27:0:0 | 0.124434 | 23.896 | 20.845644 | 5.4760547e-05 |
| partial_0190.00 | 3:43:0:0 | -0.066254 | -12.723 | 19.128674 | 0.00012219518 |
| partial_0196.00 | 0:19:0:0 | -0.046273 | -8.805 | 11.800017 | 0.005923017 |
| partial_0196.00 | 0:6:3:0 | 0.078065 | 19.064 | 17.452746 | 0.00032399235 |
| partial_0196.00 | 0:11:3:0 | -0.156812 | -38.295 | 21.365245 | 4.5550836e-05 |
| partial_0198.00 | 2:36:0:0 | -0.071755 | -13.654 | 18.634338 | 0.00019001124 |
| partial_0198.00 | 2:10:6:0 | -0.073391 | -18.227 | 12.998586 | 0.0031172632 |
| partial_0198.00 | 2:36:6:0 | 0.068778 | 17.081 | 14.254307 | 0.001756644 |
| full_0198.00 | 2:36:0:0 | -0.073376 | -13.963 | 19.852241 | 0.00015896269 |
| full_0198.00 | 2:36:6:0 | 0.064458 | 16.008 | 18.007209 | 0.00039612594 |

Interpretation: the omnibus residual test passes while one or more persistent scalar phase directions show significant deviations. This is mathematically possible: the directional test can detect a roughly 3–4.6 standard-error component that is diluted by 94–120 residual degrees of freedom. Holm includes all estimable supplied hypotheses, including aliases, and does not reuse unobservable columns as evidence. The registered engineering rejection is implemented as specified; no unit, sign, row assembly, covariance whitening, or multiple-testing implementation defect was found.

This does not certify a physical measurement fault, integer error, unique satellite cause, or receiver side. Correlated templates can simultaneously reject under a single fault. Real temporal correlation, code/carrier modelling errors, receiver-specific effects, wrong integers, or a working Q mismatch remain possible. Five epochs are insufficient to estimate and validate a temporal covariance model from this same window; no covariance was fitted and no threshold was relaxed.

The covariance floor in the final navigation measurement is applied after this diagnostic and cannot explain these pre-output rejections. Baseline conditional standard deviations are recorded in DIAGNOSIS.json; they are conditional precision, not actual position/attitude accuracy.

Provenance: model PLAN SHA256 matches the original frontend contract; all diagnosis-related source pins still match. solver.py has changed since the original cases because a separate performance revision is underway. The audit imports no project solver and performs no search; this difference is recorded rather than used to invalidate the saved-matrix audit. All case and NPZ hashes are preserved in DIAGNOSIS.json.

Recommendation: keep these invalid outputs and continue the already registered unchanged pipeline on its prescribed scope. If future work changes covariance or fault handling, make it a separate predeclared method; do not bypass GLRT to obtain accepted outputs from these four cases.
