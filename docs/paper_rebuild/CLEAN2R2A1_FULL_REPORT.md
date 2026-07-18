# CLEAN2R2A1 BY2 clean module-ablation closeout

Terminal status: `PASS_CLEAN2R2A1_BY2_CLEAN_MODULE_ABLATION_FRESH_EVIDENCE_READY_FOR_HUMAN_REVIEW`.

## Execution and provenance

CLEAN2R2A1 executed only the fresh BY2 clean ablation authorized for this stage. The common executable SHA-256 was `a31dccbff427debc5f66e6f8ac9b291f6d5fe0c97b1098e79acedfeb77cc5875`. The registry contained 18 unique effective configurations: the single-antenna and basic dual-yaw structural methods plus all 16 `RD,SA,RP,HV` factorial variants. Every process passed, every numerical output was finite, and no technical retry occurred.

The active provider passed `PASS_CLEAN2R2A1_MINIMUM_SUFFICIENT_PROVIDER_PARITY`. Raw Doppler numerical/actionable identity was bound by semantic SHA-256 `235694534abfe2fa15b5469cebbeda220469a0d3da7318fdbbdc39b07548fa33`; the actual fresh file was separately recorded as `847d6c0ed6c28c59c661b07d59707faf76c3a5adb2b45fac9802a190b8b00fc4`. Exactly three audit-only provenance columns were excluded from the semantic hash. Static source inspection found zero numerical uses of them in the Raw Doppler factor or navigation engine.

All 332 formal output files were sealed under output-manifest SHA-256 `dbf0b2913eabc9ac1f8fec0f1a32b05e172d2fcec70666fbfe9a5a4ccd91e333` before trace access. The exact evaluator SHA-256 was `aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da`; every method matched 56,642 rows. Trace was evaluation-only, from the same Fixposition source, and is not independent ground truth.

## Factorial results

Effects are `on - off`; positive is harmful because all listed metrics are lower-is-better.

| Metric | RD | SA | RP | HV |
|---|---:|---:|---:|---:|
| Horizontal RMSE (m) | -0.000126 | +0.002380 | +0.000116 | +0.000033 |
| Up RMSE (m) | -0.000125 | +0.038050 | -0.000036 | -0.0000003 |
| 3D RMSE (m) | -0.000164 | +0.035973 | +0.000013 | +0.000013 |
| Roll RMSE (deg) | -0.000430 | +0.001227 | -0.005497 | -0.000013 |
| Pitch RMSE (deg) | -0.000199 | -0.000461 | -0.000977 | -0.000035 |
| Yaw RMSE (deg) | -0.000057 | +0.019019 | -0.018735 | -0.000270 |

RD was near-neutral to mildly helpful across the six clean metrics. SA imposed the largest clean position/Up/3D penalty and slightly worsened roll/yaw while slightly helping pitch. RP primarily improved roll and yaw while remaining nearly neutral for position. HV was nearly neutral.

The largest absolute two-way interactions were:

| Metric | Interaction | Effect | Direction |
|---|---|---:|---|
| Yaw RMSE | RD:SA | +0.000712 deg | harmful |
| Roll RMSE | SA:RP | +0.000419 deg | harmful |
| Yaw RMSE | RD:RP | -0.000241 deg | helpful |
| Roll RMSE | RD:RP | +0.000145 deg | harmful |
| Yaw RMSE | SA:RP | -0.000120 deg | helpful |
| Pitch RMSE | RD:RP | +0.000080 deg | harmful |

All pairwise effects were small relative to the dominant SA position/Up penalty and the opposing SA/RP yaw main effects. The analysis is descriptive and does not make a statistical-significance or universal-causality claim.

## Full versus strong

| Metric | Strong `AB0000` | Full `AB1111` | Full - strong | Interpretation |
|---|---:|---:|---:|---|
| Horizontal RMSE (m) | 0.352517 | 0.354921 | +0.002404 | harmful |
| Up RMSE (m) | 0.817842 | 0.855731 | +0.037889 | harmful |
| 3D RMSE (m) | 0.890581 | 0.926415 | +0.035834 | harmful |
| Roll RMSE (deg) | 1.024453 | 1.019724 | -0.004729 | helpful |
| Pitch RMSE (deg) | 1.523895 | 1.522217 | -0.001678 | helpful |
| Yaw RMSE (deg) | 1.962413 | 1.962342 | -0.000072 | nearly neutral/helpful |

The clean evidence is honestly mixed: full LegSA is not superior to strong on position, Up, or 3D, and its attitude improvements are small. No parameter, threshold, provider value, epoch, or result was altered in response.

## Mechanism evidence

All strong-backbone factorial variants attempted 274 yaw updates. `AB1111` accepted 268, with 121 normal, 147 downweighted, and 6 rejected yaw updates. It also performed 223 Raw Doppler updates, 1,587 source-aware evaluations with 1,337 changed weights, 274 Go2 roll/pitch updates, and 274 Go2 horizontal-velocity updates. Source-aware rejected zero observations in this clean run; it changed scales rather than acting as a multi-state QM mechanism. Raw Doppler, SA, RP, and HV counters changed exactly with the frozen bits.

FGO, multi-state QM, QA fallback, and contact/FK counts were zero for every configuration. `trace_used_online=false`, `old_provider_solver_input=false`, `synthetic_data_used=false`, and `semisynthetic_data_used=false`.

## Figures and evidence package

Fifteen diagnostic figure groups were rendered as PNG and PDF. Machine render QA and explicit per-figure visual review passed. Legends are outside data regions, dense comparisons have delta panels, source-aware actions use a separate panel, and coincident activation-count series use distinct markers and line styles. Failed rendering attempts were retained separately and caused no solver rerun or metric change.

The finalized evidence contains 253 manifest-listed payloads plus `EVIDENCE_MANIFEST.csv` and `EVIDENCE_MANIFEST.sha256`. The manifest SHA-256 is `10ee04d62a78160ff66aaa8b036f18c50fbf1e1b07e6cd322eea578cdf996a4d`. The only final archive contains 255 entries, is 105,844,254 bytes, and has SHA-256 `1dbdd6cdd1a4c7b6ac13356ea6acb3ef6cc22958469d203a674f099e85e3eed8`. Stage sidecar verification, ZIP integrity, ZIP manifest closure, ZIP embedded-sidecar verification, and stage/ZIP manifest identity all passed.

## Claim boundary

This stage completed only a BY2 real-clean descriptive module ablation. It did not read, audit, construct, or execute D01-D60; both `D01_D60_audit_count` and `degradation_run_count` are zero. It does not establish controlled-degradation robustness, universal superiority, independent ground-truth accuracy, BY3/XB generalization, or final-paper readiness.
