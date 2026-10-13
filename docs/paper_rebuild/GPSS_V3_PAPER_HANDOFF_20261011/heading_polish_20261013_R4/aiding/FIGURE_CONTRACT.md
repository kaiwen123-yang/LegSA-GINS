# Figure 8 R4 contract

Question: When a navigation observation becomes inconsistent with its reported quality, how can source-dependent covariance adjustment limit the resulting heading deviation?

One-sentence claim: Source-dependent weighting gives a conditional robustness benefit under some degraded-observation conditions; it does not improve typical heading RMSE uniformly.

Why R3 was unclear: The position-noise and mixed-conflict examples have almost identical yaw and covariance histories because both are dominated by the shared position corruption. The heading-uncertainty example has a small improvement. Repeating those traces and all nine outcomes at equal visual weight hides what the weighting actually does. In 513 joint completions, 190 yaw RMSEs decrease and 323 increase; the median reduction is -0.000258 degree, with a worst increase about1.1505deg. Large positive tail benefits cannot be described as universal precision improvement.

Selected design A: One existing representative replay, selected unchanged from previous versions, forms a three-panel mechanism chain. Panel a shows the recorded GNSS-position-versus-prediction mismatch and the unchanged nominal position uncertainty. Panel b summarises the actual source covariance multipliers over the same0–120s with medians and interquartile ranges, replacing dense high-frequency multiplier traces. Panel c is the visually dominant heading-error time history for weighting off versus full. A short numerical note retains the positioning cost. Full histories, all source traces, both other conditions, all nine variants and all541 outcomes remain as supplements/source tables.

Rejected design B: Only paired-RMSE summaries plus a representative time history would be compact, but would still not explain what changes when weighting is enabled.

Archetype: quantitative grid with a full-width heading hero and two subordinate diagnostic panels. Backend: Python/matplotlib only. Export:174mm width, height<=234mm, min8pt, vector PDF/SVG plus600dpi PNG/TIFF and>=2560px preview. No whole-figure title inside artwork.

Interpretation limits: Position mismatch is the norm of the recorded innovation in the full run, not truth-referenced position error. Reported std norm is sqrt(trace(base_R)); it is not an independent error bound. A larger covariance multiplier reduces relative influence but is not numerically equal to the inverse Kalman gain. The contrast removes the combined source-weighting policy, so the result is not attributable to the position multiplier alone. Position RMSE3.166→3.557m remains visible. No solver/provider/evaluator is run.
