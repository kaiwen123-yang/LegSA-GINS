# 选择记录、共享参考与上轮未闭合项

本节仅查当前tracked协议/合约、Git身份和代码；没有执行旧评价、读取旧runtime/trace或把旧误差数值当本轮性能证据。选择参与是可追溯事实，不能自动推成秘密调参，也不能把明示后验修订改称完全盲测。

## BY2O参与选择的证据

|事项|真实路径/行号|Git与裁定|
|---|---|---|
|A04/F04论文角色规则|`docs/paper_rebuild/A04_F04_ROLE_DECISION_RULE.md:3–20,27–38,60–75`|BY2H/BY2O作为同日同路新序列进入方法角色决策。规则提交b9f9a44（2026-09-05 14:47+08），结果追加d3800cc（09-08 20:47）。角色决策用过这些序列，不应日后称从未看过。|
|遮挡/窗口来源|`configs/paper_rebuild/clean5/CLEAN5_BY2O_SEQUENCE_CONTRACT.yaml:178–287,1105–1145`|遮挡段来自status；起止窗依据event-onset/kick/输入缺口作pre-unblinding修订（d9c2139于09-07；7a5b48f于09-08 19:30）。没有证据把该初始窗选择定为RMSE挑窗。|
|传感器噪声来源|`docs/paper_rebuild/CLEAN5_SENSOR_CALIBRATION_RECORD.md:5–11`|s/vrw/abstd从BY2确定，规则写BY2H/O不再标定；73d71c于09-09 20:20。这支持固定BY2参数迁移，不支持“BY2O从未被检查”。|
|HV/RP/heading数据检查|`docs/paper_rebuild/PROTOCOL_V2_METHOD_STATEMENT.md:63–73`；`docs/paper_rebuild/HV_FRAME_AUDIT.md:69–76,231–258`|k/std、heading2.933193为BY2值，但BY2O heading proxy、三序列RP静止残差、HV坐标假设/尺度残差均曾查看。校准来源与是否查看数据必须分开。|
|v3航向validity|`docs/paper_rebuild/v3/PROTOCOL_V3_PREREG.md:55–70`|使用BY2O既有主段F04-R5/R5F的yaw比较来选BOTH_FIXED；7d43b9af于09-19 16:45+08。选择发生在已见该段结果之后；不能称该项对BY2O完全盲测。|
|LC01主行|`configs/paper_rebuild/hext/H_EXT_CONTRACT_V1.yaml:314–318,335–340`；`docs/paper_rebuild/hext/H_EXT_04L_RECORD.md:7`|明确`amended_after_results_seen=true`，三序列（点名BY2O）结果后将主行由S改为文献配置；f7bf0193于09-18 16:25+08。历史修订标记保留，不能改写成预先选择。|

这些证据只证明列出的选择/检查，不证明逐case噪声秘密寻优；旧实验数量、具体性能影响本轮未重新计算。XB四段本身已有Excel/导出脚本处理痕迹，是否参与更早参数/几何选择仍UNKNOWN，所以也不能直接给盲测标签。

## 为什么共用reference不保证排名抵消

在同一时间支撑与同一权重下，令真值t、估计a/b、参考r，并记eA=a−t、eB=b−t、eR=r−t，则

`MSE(a,r)−MSE(b,r) = MSE(a,t)−MSE(b,t) − 2 mean[(eA−eB)^T eR]`。

相同参考的平方项抵消，但交叉项一般不抵消。若参考也用GNSS等共享信息，交叉项可依方法而变。最小确定反例：t=0、r=1、a=0、b=1；对真值a优，对参考b优。不同输出支撑时连参考平方项的均值也不必相同；RMSE取平方根后更不能按差直接抵消。局部角差可作同类近似，大角须使用圆周或旋转定义。

因此目前应称“对商业融合reference的一致性比较”，不称独立真值排序已验证。此推导不是说参考毫无用途，也不提供未知eR的修正值；不允许拟合时延、偏置、yaw或删除高误差点把比较调好。

## 上轮第11项：v3新航向、旧HV与std

当前真实F04是scalar v3，B3仍是独立候选。`protocol_v3/providers.py:118–303`严格字节门只替换主GNSS provider的yaw/valid；RP/HV及非heading列hash保留。`clean6_sensor_v21/providers.py` 的HV仍把Go2体速度用旧status yaw转NED；新的raw HPPOSECEF主航向不反向重建HV，原2.933193° std也不由新pAcc计算。故“主航向源已换raw”成立，“所有用到航向的信息已独立换源”不成立。不同有效支撑、共享源及误差相关属于已确认数据流上的条件性风险；本轮没有重新算旧性能，不能据此宣称V3一定更好/更差。

## 上轮第13项：候选异常与正常回归

隔离数值补丁只修Matrix二维边界和Rotation有界/有限wrap；正常范围20,001个角度回归点和六个完整toy模式的18个输出文件与旧实现一致。这不是20,001次独立科学实验，也不是全部输入等价证明。

实际`hext/t5bc_runtime.py:455–506::classify_heading_failure`以完整synthetic loop/update/provider证据测试：已知裸contract错误与精确`legsa_v23_port_core_demo failed: `前缀均识别；`AUDIT_NONFINITE_ANGLE`、`AUDIT_MATRIX_INDEX_OUT_OF_RANGE`和任意额外前缀不冒充无航向算法失败，保持UNAVAILABLE。`protocol_v3/runtime.py:166–172`会对其hard-stop，而不是吞掉异常当成功。6项函数测试通过；没有运行“候选异常进程→正式历史controller”的完整端到端注入，候选尚不能直接接替正式runner。

测试开发前两次各2 failed/4 passed：fixture把同频IMU/GNSS端点的2条更新计成2，而当前严格stale刷新回放实际只消费1条；不是通过改旧实现让断言变绿。最终测试用每个IMU区间内部.05/.15秒观测，完整计数一致后单独验证错误前缀。两次失败及修正原因写入TEST_RECEIPTS.json；不抹去失败。

这一开发反例也明确了实际调度限制：port_runtime.cpp:1473只在旧GNSS time < previous IMU time时刷新；GNSS/IMU同频且精确端点相等会延后一轮，末尾记录可能未消费。正式高频IMU/低频GNSS的触发量需按实际时间记录统计，不能把本人工同频反例的丢样率当旧实验事实。
