# 相位下一轮两方案：独立交叉评审

状态：PLAN_REVIEW_ONLY，未执行测试/真实数据/科学函数，尚未审实现。所读admission计划md hash为ed1815968eca9b3407bebe2d9952dc886f4ea4040cec27d87410d82997de366b；information计划md为9521029548e8e852e5f0420998456fb9665be546d16382c2b5da3c119c184fbb。两个JSON当前均为待登记/未执行状态。

## 核心判断

admission的两个Markov门数学成立：若残差r=w+eta、E[wwᵀ]⪯S且||eta||≤epsilon，反三角不等式给max(0,||S^(-1/2)r||−epsilon/sqrt(lambda_min(S)))≤||S^(-1/2)w||，故平方统计超过m/alpha的概率至多alpha。投影到L后同理使用nu维；prior门不减姿态参数数目。两门用union bound不需独立。nu=0、奇异支持、真实来源缺证分别保留未定/未知，条件可用不等于fault-free，物理模板与注入truth分离、一次统计永久消费和晚到撤销符合研究边界。

登记前需明确概率前提相对固定条件信息集I：E[wwᵀ|I]⪯S(I)，J/S/L/alpha/epsilon不由待检残差选择；有限remainder若只在局部状态误差域成立，应声明该域确定有效，或另计越域概率预算。当前固定exact-linear合成例可直接满足，不能由此迁移成真实全域保证。数值LᵀJ leakage非零时用完整LᵀSL保住二阶矩门，但不能再声称与精确free-nuisance消元完全等价。余项Euclidean球在一般非正交测量变换下不是同一球；单位/坐标不变性必须同步转换真实余项集合或限制为旋转及一致尺度变换。

information的完整cross innovation、K与相关Joseph公式和现attitude_clone.update_measurement oracle符号一致。C=−PHᵀ的取消反例、P01不可默认零、proper prior与真实不适定gauge分列、H基线轴零空间与静态公共旋转极限、正小P模态/大W反例均必要且已列入12个固定items。UNKNOWN分支没有执行独立Kalman再重命名，Young连续条件只报告存在性，不冒充找到最优点。

## Native提案的关键正确点与后续实现门

现foot clone不能直接当0.8秒ARC被动日志。两臂同一ARC时间表/同一增广、24维更新及reset，才可用NULL/TELEMETRY字节身份门解释日志；旧PVT_CONTROL必须另列。方案目前仅提案6个native，未授权或登记真实执行，本评审不改变这一状态。

END P24包含整个区间普通观测条件化，因此必须与END修正后的clone C0及END当前C1配对，不能搭配未修正START nominal。读过stateFeedback实际左乘clone/current校正且reset后均值归零；P24→P6映射包括current位置引起的ECEF/NED frame误差，不能只抽两个PHI块。后续实现必须在END full feedback后的BLH/Cbn计算J1，并记录两端nominal/协方差与同一条件信息集、源消费清单。清单标同源可能性，不凭它造数值state/phase cross。

现计划符合12items/1pytest/60秒、28cases/1pytest/120秒的有限合成阶段方向；完成前提澄清及登记后可推进实现。局部资格不替代实际arrival、源误差界、故障检测功效或导航收益。

## Information initial implementation static review

Read all 266 source lines at SHA12bd8a3f6407bdecd9e5aa2c34f84da2426d1b8665b1b8a349c1ec06e83ba0fd and 193 test lines at SHA13be018f518758c64939244797453d20a77d71a39cde0b2712a8f74b53a38fe7, without import or execution. Twelve fixed functions cover the registered scopes, including scalar/original-oracle checks, positive/negative dense cross, exact cancellation, sixteen fixed latent examples of the Young bound, singular prior/innovation, small-positive-P weight mass and coordinate changes. No source/test formula mismatch found.

Before registration, requested finite-intermediate guards: finite H/P can still overflow HPHᵀ; a Cholesky solve with infinite coefficient can yield a finite zero gain, so checking only solve output does not prevent CONDITIONAL output with infinite spectrum. Require finite normalized matrices, solve inputs/RHS, whitened matrix/eigenvalues, and final scores/traces; unknown bound score must not be negative. Add a finite-input-overflow refusal assertion inside test12 without increasing function budget. Subsequent repaired identity remains to be checked; this review did not run tests or numerical examples.

Information repair delta verified: source6f14db775227afddd05b75b47c8cd98d5743dd1dd10466d322987012765e1c3a and test3c014f1e90e1e5d178cd0ad2d7faf83dead5146adf0e60aec5ed042aad953e26 now guard public geometry/diagnose arithmetic, normalized/solve inputs and RHS, HPHT/whitening/spectrum, objectives/projected traces, and negative Young objective. Item12 includes finite-but-overflow rejection in both zero-cross and unknown-cross modes; still twelve test functions. Static blocker resolved; source can be frozen for the registered local execution. No import or test by reviewer.


## Admission implementation final static review

Read the complete initial 509-line implementation and 440-line test source, then every repair delta to the final 524-line source and 464-line test. Final source SHA256: e8b683d6992ed56a988e9db0651bc562d13ac49ba079e020077cc4d9dbb5cdcf. Final test SHA256: e7a026d7bd926c52ce1d200c9ead3b21bfa33ce4e9d47338fa8b9c3cb889df34. Review is static only: no import, pytest, numerical example, real data, native solver or evaluation was executed by this reviewer.

No remaining static blocker to freezing this implementation for the registered single 28-case local run. The complete joint second-moment construction, FULL cross terms, UNKNOWN-cross Young bound, prior m-dimensional and projected nu-dimensional Markov gates follow the conditional model in the plan. Positive small variance is retained, singular support is not artificially floored, and finite arithmetic failures after reservation return UNRESOLVED without refunding consumed endpoints. UNKNOWN qualifications return before residual statistics and endpoint reservation. Canonical physical endpoints cannot be reused through renaming or pivot changes. Active dependencies include only physical sources with nonzero coefficients, allowing genuinely fresh survivor support after retirement. No external navigation state rollback is represented as implemented.

Three pre-execution repairs were checked. (1) Retirement is independent of the explicit evidence interval: an ACTIVE factor ending at or after retire_from_s is revoked even when a later evidence interval does not overlap it. Case26 contains the [100,100.8] factor / interval102 / retirement100.4 / notice103 counterexample and checks no endpoint refund. (2) Both state arrival times and the current combined contrast/geometry availability must be no later than the fixed information-set freeze; being available by the eventual decision is insufficient. Case10 checks late-state and late-geometry UNKNOWN outcomes with no residual and zero consumption. Under the current typed API, None-to-UNKNOWN applies to geometry/specification/bound availability fields that permit None; PhaseAttitudeState requires a finite arrival time at construction, so a None-valued state does not reach this gate. (3) Case02 now includes nonzero-remainder hand calculations (5,1,2 gives9; 1,1,2 gives0) and exact finite-support perturbations verifying the one-sided statistic bound, still within 28 test functions.

The tests explicitly retain a hidden physical fault in the nuisance column space: broad prior uncertainty can let both gates pass, whereas a tighter prior may reject it. This is the correct conditional consistency claim, not a fault-free certificate or a universal detector. Numeric leakage uses the full projected second moment; a nonzero computed leakage does not establish exact free-nuisance elimination. The caller must still justify the conditional source moments, the almost-sure remainder domain, the fixed information set and actual arrival records. Local synthetic qualification does not establish real source error bounds, trusted-heading coverage, slip detection power or navigation benefit.


## Native telemetry proposal review (plan only)

Read all 128 lines of ARC_NATIVE_TELEMETRY_PLAN.md, SHA256 8b5cad819b1f7f084922e8d5d5ea68b817716f10a943d18e990bc1d2efa3999a, and re-read the existing augmentationJacobian, ordinaryUpdate, reset, stateFeedback and exact event-loop sections. No source was modified or executed. This is a proposal review; it does not authorize C++ implementation, build, local tests or six native executions. Those remain subject to the root's subsequent stage decision and registration.

No proposal-level mathematical blocker found. Under the existing engine conventions, position feedback is minus DRi times position error while NED attitude correction left-multiplies Exp(phi). Thus the current ECEF attitude error is minus nedFrameConnection times position error plus cne times phi. J1=[-connection,0,cne,0,...] has the correct sign, matches the existing augmentationJacobian, and must be recomputed at END after the final ordinary feedback using END BLH. With clone error first in the two-pose target, B=[[0,Iclone],[J1,0]] and P6=B P24 B^T retain the position-frame and current/clone cross terms. The corrected END clone nominal must accompany END P24; START nominal and START P21/J0 are separate provenance, not substitutes. This remains a linearized working covariance, not proof of calibrated physical moments or known state/phase error cross.

The proposed IMU-end deferral is necessary: the current exact event loop applies body-HV after queued observations and their feedback, so taking END inside that queue would omit a same-timestamp conditioning update. Deferring only ARC actions until after body-HV preserves the intended END information set. Between IMU ends, use the original GNSS/auxiliary feedback before ARC. An implementation must still prove this dispatch order and zero error mean at capture, complete monotone update/reset ledger prefixes, and correct uncovered-start/end handling without synthesizing or snapping an endpoint.

Trajectory identity is appropriately scoped to the new NULL and TELEMETRY pair. Both have the same scientific config, binary, exact schedule, 24-dimensional updates and full reset, and both compute the same snapshots; only final matrix serialization differs. New splitting and full-reset paths can change the older PVT_CONTROL trajectory, so equality to that historical run is not an appropriate identity claim. NAV/STD, original heading events, ARC lifecycle and conditioning bytes must match between the paired new arms before any scientific P interpretation; a mismatch stops the trial rather than becoming a tolerated diagnostic effect.

The budget and boundaries are finite: original 921 blocks/1842 endpoints including all 61 missing endpoint-model blocks; prepare3/real native6/retry0/eval0/phase-information-readout0, preceded by separately registered local qualification. The final field-only aggregation may check identities and dimensions, but must not quietly evaluate covariance PSD or phase information. Missing timing provenance stops preparation, uncovered blocks remain in the full denominator, and actual availability and state/phase cross remain NA/UNKNOWN. Saved baseline length or a synthetic 0.28m example is not a physical installation calibration. No claim of 860 available joint priors, real phase admission, fault detection, trusted heading or navigation improvement follows from this proposal.
