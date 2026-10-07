# 三完整窗侧向投影量测模型消融（已登记，执行前冻结）

本次用户已授权逐步实施。已完成源码静态复核，JSON为REGISTERED_READY；只有登记提交完成后才启动，当前尚未执行loader/native/evaluator。
本试验不是新AR或独立速度试验，不重写原V3，也不重跑Euler控制。

## 唯一改变与身份

复用先前FULL_WINDOW_NAVIGATION_ATTEMPT01三条PVT_CONTROL的配置及二进制：
7f8a8f332fa36b957a88231228ad73c1cab206327e701dc9f98d0abb1da1b0a2。
其执行登记3c81e5b8e4df4bece69c5f4635f0a60bd12c4369，native source属于旧封存PLAN，
不是当前C++，不编译新binary或checker。

三窗BY2[66,340]、BY2H[413,683]、BY2O[3186,3563]，只改
dual_yaw_prediction_model从euler_yaw为lateral_projection。允许其余改动仅stage/protocol/
case/run/run_label身份和outputpath；删除这些改动行后全部配置字节必须相同，
解析后的全部其他科学字段也必须相同。初始化、5原provider、7列IMU、HV、参数、
PVT-priority-control及原carrier旁路均不变。旧binary没有新foot clone功能。

原scalar来自左侧向基线投影+90°；预测与相应三分量Jacobian一起选新模型。
这是一个观测模型选项的完整切换，不声称只改一个浮点数或只改Jacobian。
投影退化导致技术/算法失败均保留，不能换窗口或调噪声。

## 预算与调用顺序

- 3次旧checker loader-only，无编译。
- 3次新native，各最多1200s、无自动重试；旧3Euler NAV/STD及评价直接复用。
- 全部3native和在线访问审计封存后，最多3次相同冻结evaluator。
- 1次派生比较；0整数搜索、0新raw、0父进程reference payload读取。
- 失败bound行保留并不调用evaluator，指标NA；技术失败保留原attempt后停止。

保持旧RUN_MANIFEST计数缺陷原样；新RESULT另从HEADING_SOURCE_EVENTS计算实际
PVT/carrier尝试与接纳，不能修改旧/新原生manifest假装缺陷消失。control必须没有carrier尝试。
输出键不同会报告coverage差异，不截取有利支持。参考是共享GNSS商业参考，非独立真值。

## 入口

脚本：scripts/paper_rebuild/carrier_phase/direction_model_trial.py

全部命令要求 --stage 和 --registration-commit。
prepare另需 --baseline-stage 指旧FULL_WINDOW_NAVIGATION_ATTEMPT01；
native和evaluate使用新PLAN绑定原路径；compare另需 --out（必须在新stage内）。
不会修改导入的旧模块全局IDS/ARMS。新stage不得已存在，禁止覆盖结果。

顺序：prepare → native → evaluate → compare。
prepare不解读新reference路径，仅复制旧封存sequence/evaluator/reference元数据；
reference payload只有原冻结评价子进程在全native封存后读取。
登记门检查当前计划/runner与指定commit字节同一，并检查Python依赖source pins；
不拿当前C++ SHA冒充旧native源码。

## 比较与采用

COMPARISON下输出V3_COMPARISONS.csv、MODEL_DIFFERENCES.csv、COVERAGE.csv和COMPARISON.json。
new LATERAL_PROJECTION与REUSED_EULER_PVT_CONTROL身份明确，原V3单列；
同时计算完整支持和真实error time keys交集，不用summary假造共同支持。
误差事件沿旧阈值/稳定1s确认/右删失，缺测不记0；输出不确定度仍未运输。

H/V/yaw RMSE/P95/P99及coverage非退化容差与原A门不变：至少两窗相对原V3
yaw RMSE降低5%，第三窗不退化。建议模型改变还要求对应两窗相对匹配Euler
在完整及相同完整common keys上有正增量；所有零容差差值、max不利结果全列。
B为NA；不得把量测模型改善归因AR、脚约束或HV独立。
正式V3仍是主比较基线，不用关闭好PVT的弱对照代替；通过只允许人工审核，不自动merge。

当前资格：AST语法及无副作用import已通过；没有loader、native、eval或新compare。
既有模型FD/legacy回归可复用；这不是新实测成功证据。

唯一输出位置：`<SCRATCH_ROOT>/TRUSTED_HEADING_CONTINUATION_20261007/DIRECTION_MODEL_ATTEMPT01`，比较仅允许其`COMPARISON/`。相同登记不得换目录重复科学调用。登记前独立审查发现并补齐这一单次执行约束；算法、窗口和判据未改。
