# Protocol v2 figure delivery

Status: `PASS_PROTOCOL_V2_FIGURE_PACKAGE_COMPLETE`.

| Item | Verified value |
|---|---|
| Figure root | `<PUBLICATION_ROOT>/figures/v2/` |
| Figure ZIP | `<HANDOFF_ROOT>/figures_v2_handoff.zip` |
| SHA-256 | `d304001f0f77818cef0604b3b790cc414649c06892d1a7963b1c0d7869c52a60` |
| Size (bytes) | 29063129 |
| ZIP members | 156 |
| Figures / exports | 29 / 87 (PNG, PDF, SVG) |
| Edition origin | 8 reissued + 21 new = 29 |
| Publication role | 2 supplementary, overlapping edition origin: SFIG01 reissued; SFIG02 new |
| Main figures | 7 reissued + 16 new matrix + 4 new horizontal = 27 |
| Visual review | 29/29 PASS; every review bound to current PNG SHA-256 |
| Minimum PNG width | 4165 px |
| v1 preserved files | 30 files, including 8 composites / 24 PNG/PDF/SVG exports |
| Data ZIP SHA-256 | `79e75f7d867a4930dc80c0f906173b48aab1bec6a5caac44b63bae993a848dd3` |
| FIGURE_INDEX.md SHA-256 | `af7beee8520e4fdf4e002f1f4df7796569bbf39f581935631246693af85bf684` |
| VISUAL_REVIEW.json SHA-256 | `ab7ec7649cc951447ecb87c82bff97c717b150f4ddc21f6829b353054f510eff` |
| Render parent commit | `1479002a50cfed6c60a15c5b9ba87a0e94f1db37` |

All new ZIPs resolve through `<HANDOFF_ROOT>` on the project G: root. The original v1 registered source remains unchanged; its byte-identical archive copy is `<PUBLICATION_ROOT>/figures/v1_prereg/`. No source/evaluator/solver/541-core aggregate was regenerated or modified for publication.

The primary evaluator is v3 and the manuscript method is F04. FIG01/FIG03/FIG04 are explicitly `NOT_APPLICABLE_NATIVE_DIAGNOSTIC`; their native information-layer, raw-availability and observability results are not renamed as v3 navigation accuracy. FIG02 retains GINav as `Not comparable` where compatible IMU-point NAV is absent. All 379 source references match package identities; all 371 CSV references carry valid source-row selections. SVG forbidden-word count is 0. The full reference terminology and method statement are in [PROTOCOL_V2_METHOD_STATEMENT.md](PROTOCOL_V2_METHOD_STATEMENT.md).

Initial plotting errors and targeted repairs remain in `figures/v2/RENDER_REPAIR_RECORD.json`: NumPy-bool manifest serialization; independently thinned NAV/error-series timestamp handling; canonical centered/clamped windows versus addendum explicit outage endpoints; labels/legends/zero counts and axis alignment. Thirteen initially valid composites retain all 39 export bytes. Their original export-producer hashes and later metadata-reconstruction hashes are recorded separately; the initial full source-content snapshot is explicitly UNAVAILABLE. The final renderer source is delivered by this figure commit. No scientific call was made during these repairs.

MFIG00's unchanged-tolerance consistency gate covers 135 exact common epochs, 4.927% of 2740 NAV display epochs and 4.765% of 2833 retained error samples. It does not assert full-rate identity from two independent thinning grids; no tolerance widening or alignment by error was performed. MFIG09 follows the frozen centered/clamped canonical interval policy. MFIG10/11 use the addendum manifest's exact outage endpoints, while MFIG12 reads full-rate-derived frozen endpoint metrics. MFIG16 shows the declared constant 1.5° sigma and heading presence/absence, not dynamic Source-Aware weights or a complete quality score. Its BY2H 618–621 s and BY2O input-status windows remain explicit.

Validation: 13 focused publication tests PASS; 29 automatic and individual raster checks PASS; an independent reviewer verified all 87 export hashes, source references, index columns, evaluator roles and plot semantics. The root independently inspected 8 final PNGs. The ZIP passed CRC and every member hash/size check. Figure sources, captions, numerical origin, evaluator and F04 role are retained in each FIGURE_MANIFEST.

The following is the original `FIGURE_INDEX.md` text, byte content copied without editorial changes inside the code block. Relative manifest links resolve from the figure root in the handoff package.

```markdown
# Protocol v2 figure index

Proposed method: F04. Primary evaluation point: v3.

| Number | Title | Origin / role | Data source | GPS Solutions section | TIM section | Status |
|---|---|---|---|---|---|---|
| MFIG00 | C00 reference trajectory and attitude | Reissued / Main | C00_NAV_AB1111; PLOT_GEOMETRY_CONTRACT.json; frozen v3 error-series samples; hash-locked Truth trace; [rows/hashes](MFIG00/FIGURE_MANIFEST.json) | Results: nominal sequence | Experimental results: nominal sequence | RENDERED |
| MFIG01 | Canonical-541 matrix overview | Reissued / Main | UNIQUE_EVALUATION_RESULTS; [rows/hashes](MFIG01/FIGURE_MANIFEST.json) | Results: degradation library | Robustness evaluation | RENDERED |
| MFIG02 | A04 versus F03 seed consistency | Reissued / Main | PAIRWISE_CASE_LEVEL; [rows/hashes](MFIG02/FIGURE_MANIFEST.json) | Ablation study | Ablation study | RENDERED |
| MFIG03 | Source-Aware paired tradeoffs | Reissued / Main | PAIRWISE_SUMMARY; UNIQUE_EVALUATION_RESULTS; [rows/hashes](MFIG03/FIGURE_MANIFEST.json) | Robustness: quality weighting | Protective weighting analysis | RENDERED |
| MFIG04 | Five-configuration ablation ladder | Reissued / Main | PAIRWISE_SUMMARY; UNIQUE_EVALUATION_RESULTS; [rows/hashes](MFIG04/FIGURE_MANIFEST.json) | Method ablation | Component verification | RENDERED |
| MFIG05 | Favorable and adverse representative cases | Reissued / Main | PLOT_GEOMETRY_CONTRACT.json; frozen v3 error-series samples; [rows/hashes](MFIG05/FIGURE_MANIFEST.json) | Degradation case study | Failure and recovery cases | RENDERED |
| MFIG06 | Mechanism action counters | Reissued / Main | UNIQUE_EVALUATION_RESULTS; [rows/hashes](MFIG06/FIGURE_MANIFEST.json) | Mechanism evidence | Measurement update diagnostics | RENDERED |
| MFIG07 | Yaw RMSE distributions and worst-five-percent means | New / Main | UNIQUE_EVALUATION_RESULTS; [rows/hashes](MFIG07/FIGURE_MANIFEST.json) | Tail robustness | Tail error assessment | RENDERED |
| MFIG08 | Individual-module yaw tails | New / Main | UNIQUE_EVALUATION_RESULTS; [rows/hashes](MFIG08/FIGURE_MANIFEST.json) | Ablation: tail behavior | Component tail sensitivity | RENDERED |
| MFIG09 | D05 velocity-aid outage trajectories | New / Main | frozen v3 error-series samples; [rows/hashes](MFIG09/FIGURE_MANIFEST.json) | Velocity redundancy | Degradation and redundancy | RENDERED |
| MFIG10 | A1 all-GNSS outage trajectories | New / Main | ADDENDUM_IDENTITY_PROBE.json; frozen v3 error-series samples; [rows/hashes](MFIG10/FIGURE_MANIFEST.json) | Addendum A1 | Complete-GNSS outage study | RENDERED |
| MFIG11 | A2 heading-retained outage trajectories | New / Main | ADDENDUM_IDENTITY_PROBE.json; frozen v3 error-series samples; [rows/hashes](MFIG11/FIGURE_MANIFEST.json) | Addendum A2 | Heading-retained outage study | RENDERED |
| MFIG12 | Outage-end horizontal error versus duration | New / Main | ADDENDUM_IDENTITY_PROBE.json; UNIQUE_EVALUATION_RESULTS; [rows/hashes](MFIG12/FIGURE_MANIFEST.json) | Velocity redundancy addendum | Duration-dependent degradation | RENDERED |
| MFIG13 | Algorithm failures by family | New / Main | ADDENDUM_IDENTITY_PROBE.json; UNIQUE_EVALUATION_RESULTS; [rows/hashes](MFIG13/FIGURE_MANIFEST.json) | Failure-aware results | Failure accounting | RENDERED |
| MFIG14 | All-yaw-rejected timeline and F02 control | New / Main | native yaw-action timelines; [rows/hashes](MFIG14/FIGURE_MANIFEST.json) | Adverse mechanism example | Gating failure diagnostics | RENDERED |
| MFIG15 | Three-sequence five-configuration error histories | New / Main | frozen v3 error-series samples; [rows/hashes](MFIG15/FIGURE_MANIFEST.json) | Real-sequence transfer | Cross-sequence verification | RENDERED |
| MFIG16 | Yaw errors and heading-provider quality | New / Main | BY2; BY2H; BY2O; OCCLUSION_WINDOW.json; frozen v3 error-series samples; [rows/hashes](MFIG16/FIGURE_MANIFEST.json) | Observation quality | Input-quality diagnostics | RENDERED |
| MFIG17 | Error-budget parity steps | New / Main | PARITY_DECOMPOSITION_BY_VERSION; [rows/hashes](MFIG17/FIGURE_MANIFEST.json) | Error budget | Uncertainty and systematic effects | RENDERED |
| MFIG18 | Three-sequence body-frame bias | New / Main | BODY_FRAME_BIAS; [rows/hashes](MFIG18/FIGURE_MANIFEST.json) | Body-frame error analysis | Systematic-error diagnostics | RENDERED |
| MFIG19 | Frozen nine-setting noise sensitivity | New / Main | SENSITIVITY_GRID; [rows/hashes](MFIG19/FIGURE_MANIFEST.json) | Noise-model sensitivity | Sensor model sensitivity | RENDERED |
| MFIG20 | Frozen calibration regression | New / Main | CALIBRATED_PARAMETERS; LAG_VARIANCE_FIT; [rows/hashes](MFIG20/FIGURE_MANIFEST.json) | Sensor-noise calibration | Calibration methodology | RENDERED |
| MFIG21 | Platform and antenna geometry | New / Main | PLOT_GEOMETRY_CONTRACT.json; [rows/hashes](MFIG21/FIGURE_MANIFEST.json) | System setup | Measurement geometry | RENDERED |
| MFIG22 | Protocol v1–v2 comparison and effect scale | New / Main | V1_V2_PAIRWISE_COMPARISON; [rows/hashes](MFIG22/FIGURE_MANIFEST.json) | Protocol comparison | Protocol sensitivity | RENDERED |
| SFIG01 | Type-by-configuration error heatmaps | Reissued / Supplementary | UNIQUE_EVALUATION_RESULTS; [rows/hashes](SFIG01/FIGURE_MANIFEST.json) | Supplement: degradation tables | Supplement: complete robustness grid | RENDERED |
| SFIG02 | External-method v3 point comparability | New / Supplementary | EXTERNAL_BY2_V3_REFERENCE; FINAL_METHOD_REGISTRY_V2; OUTPUT_AND_METRIC_COMPATIBILITY; UNIQUE_EVALUATION_RESULTS; [rows/hashes](SFIG02/FIGURE_MANIFEST.json) | Literature comparison | Benchmark comparability | RENDERED |
| FIG01 | Horizontal comparison information hierarchy | New / Main | FINAL_METHOD_REGISTRY_V2; OUTPUT_AND_METRIC_COMPATIBILITY; [rows/hashes](FIG01/FIGURE_MANIFEST.json) | Comparison information hierarchy | Measurement information hierarchy | RENDERED |
| FIG02 | Formal C00 solution-level navigation comparison | New / Main | EXTERNAL_BY2_V3_REFERENCE; FINAL_METHOD_REGISTRY_V2; UNIQUE_EVALUATION_RESULTS; [rows/hashes](FIG02/FIGURE_MANIFEST.json) | Solution-level comparison | Navigation benchmark | RENDERED |
| FIG03 | Raw dual-antenna BY2 applicability | New / Main | RAW_AVAILABILITY_AND_STATE_SUMMARY; RAW_BASELINE_AND_HEADING_SUMMARY; RAW_PRIMARY_METHOD_C00_SUMMARY; RAW_RUNTIME_AND_FAILURE_SUMMARY; [rows/hashes](FIG03/FIGURE_MANIFEST.json) | Raw-observation method applicability | Raw GNSS method applicability | RENDERED |
| FIG04 | Hartley yaw unobservability | New / Main | HARTLEY_GAUGE_EQUIVALENCE_SUMMARY; HARTLEY_OBSERVABILITY_SUMMARY; OBSERVABILITY_SINGULAR_VALUES_R1; [rows/hashes](FIG04/FIGURE_MANIFEST.json) | Proprioceptive observability | Gauge and observability analysis | RENDERED |
```
