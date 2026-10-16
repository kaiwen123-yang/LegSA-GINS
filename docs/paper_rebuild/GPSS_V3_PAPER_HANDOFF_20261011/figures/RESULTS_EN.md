> 状态：已完成的五问题英文叙述，尚待按作者选定的六段结果顺序重排；当前组织见 [结果结构](选定科学问题_结果正文结构.md)。

# Results narrative for the five scientific questions

## Proprioceptive observations and absolute heading

Seven runs using the same inertial and contact-kinematic measurements retained their different initial global headings. The estimated trajectories were related by global rotations, while local heading increments agreed. The saved observability analysis identified a four-dimensional nullspace in all five preselected contact intervals: three global translations and one rotation about gravity. Removing the initial rotation gave a maximum position discrepancy of approximately 1.90×10⁻⁷ m. These results establish the role of an external absolute-direction constraint in the evaluated proprioceptive system. Supplementary relative-motion results retain both official contact-aided InEKF parameter conditions and kinematic integration using onboard attitude.

## Availability and consistency of short-baseline heading

For the current 0.35 m installation, continuity and physical consistency provide complementary descriptions of the heading observations. The original RTKLIB configuration produced new fixed headings at 153/1370, 179/1350 and 112/1885 epochs during nominal walking, large body motion and the antenna-obstruction trial, respectively. Among the 153 fixed outputs within the nominal evaluation window, 35 had baseline-length residuals exceeding 0.04 m. The enlarged interval includes a baseline estimate of 0.70775 m. The archived execution records show that these epochs had received a floating-solution length update; returning a fixed status did not guarantee consistency with the declared installation length. All four processing conditions, the three raw dual-antenna implementations, FAR/PAR outcomes and input-quality diagnostics remain available in the supplementary figures and tables. These observations motivate quality-aware use of available direction information in the navigation estimator.

## Navigation accuracy and output continuity

The closest external navigation routes were the two-position IEKF and OiSAM. Natural positioning errors were broadly comparable, whereas heading performance depended on the trial and parameter condition. In nominal walking, the calibrated IEKF achieved a heading RMSE of 1.539°, compared with 1.886° for LegSA-GINS and 2.995° for the literature-parameter IEKF.

At 274 common evaluation epochs and the same physical point, LegSA-GINS and OiSAM achieved horizontal RMSEs of 0.09676 and 0.10595 m and heading RMSEs of 1.778° and 4.659°. In the 54-epoch common initial interval of the antenna-obstruction trial, the horizontal errors were similar and OiSAM had the lower heading RMSE, 0.986° versus 1.211°. Precision is therefore presented together with the complete output timelines. The single-initialization OiSAM protocol stopped at recorded IMU gaps; the separately completed gap-reinitialization protocol provided 275, 267 and 370 dynamic outputs. Its subsequent heading histories are retained in a supplementary comparison.

The external interruption controls connect these system-level comparisons to the aiding experiments. Retaining relative-baseline updates in the IEKF preserved heading performance but did not automatically improve translation: across the 18 registered conditions, its median whole-run horizontal RMSE was 2.786 m, compared with 1.407 m for the original two-position IEKF. LegSA-GINS achieved 0.1767 m on the corresponding set. These are system comparisons with their stated information inputs; the internal single-switch experiments isolate the contribution of the robot-motion observations.

## Contribution of robot-motion information

During 20 s interruptions of translational GNSS observations with heading retained, the median whole-run horizontal RMSE over nine placements decreased from 7.960869 m without body-velocity aiding to 0.240759 m with it. The basic dual-heading GNSS/INS configuration gave 9.746826 m. The complete-GNSS-loss condition produced similar curves for the two velocity-aiding configurations because the evaluated implementation schedules aiding through valid GNSS events. This distinction defines the demonstrated operating condition.

Tilt aiding provided a separate attitude benefit. Roll and pitch RMSEs decreased in all 519 jointly completed core cases, with median reductions of 1.072° and 0.664°. The basic heading comparison is also retained: introducing the specified dual-antenna heading chain reduced the three natural-trial heading RMSEs from 8.090/7.137/5.739° to 1.916/1.941/2.432°.

## Source weighting and the accuracy–robustness trade-off

In the representative GNSS-position-noise case, enabling source weighting reduced heading RMSE from 29.799° to 2.699°, while horizontal RMSE changed from 3.166 to 3.557 m. The archived covariance-scaling histories show different responses for position, heading and body-velocity observations; all six source histories are supplied. Across 541 registered cases, divergence decreased from 19 to 13 and completion increased from 513 to 519. In the 513 jointly completed cases, the median horizontal-RMSE cost was approximately 0.981 mm. Two of the six additional completed cases still had heading RMSEs near 69°, so completion and accuracy are reported separately. The results support heading protection and fewer divergences under selected degraded conditions together with an explicit positioning cost.

The findings collectively support a navigation design built around short-baseline direction admission, conditional body-state aiding and source-dependent weighting in one estimator. Relative observability, observation-generation comparisons and complete navigation comparisons play distinct roles in this argument.
