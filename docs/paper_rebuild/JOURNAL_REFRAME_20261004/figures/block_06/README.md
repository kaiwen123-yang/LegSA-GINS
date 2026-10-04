# READY 06：原始观测横向方法真实大误差与缺测

R13三序列各画三方法全部原native-valid投影航向误差和真实有效时刻；角度wrap跳变与失效历元断线，孤立有效点保留。不画hold替代native，不删接近±180°误差。R14将全部九组合自身支持RMSE和n/N并列，没有择优条件。paired分母BY2/BY2H/BY2O为1370/1350/1885，原无效历元全部在数据副本中保留。

数据严格来自已验收RAW_REPRO_V2_TECH_RETRY_2的ERROR_SERIES/HEADING_METRICS及FINAL_EXECUTION_RECEIPT。该批对应guardless执行快照，后结果竖直保护修复没有回贴旧九成绩；绘图没有原生或评价调用，也没有rawreference读取。

Constrained LAMBDA、constrained WLS、recursive ambiguity filter对应EXT01/02/03，均为原文核心实现及明确工程实例，不代表作者全场地/全程序复现。输出是横向基线水平投影方位＋90°，参考为商业融合Euler yaw且非独立真值。输入、估计分支与物理量差异阻止同输入求解器排名。较高native覆盖不证明整数解正确；EXT01/02没有接受检验，不能冒称通过正确率。

4张300dpi PNG/PDF/SVG，data/保存完整原列副本及原JSON指标转录。BUILD_RECEIPT绑定所有读取前后hash、脚本和输出。最终4PNG实际打开，全部曲线范围、图例、支持、坐标及脚注可读。PDF/SVG同Figure导出，未另渲染PDF。
