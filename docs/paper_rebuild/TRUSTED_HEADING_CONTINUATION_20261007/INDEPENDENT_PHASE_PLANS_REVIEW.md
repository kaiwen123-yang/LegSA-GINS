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
