# 现有八段数据：最终结果入口

已完成4段NMB的F03/F04真实运行。采用固定数值参数与当前实际IMU间隔实现，统一body有效测量时间前移1.1秒，参考插值门限统一0.15秒。4段XB没有合法双fixed航向，均自然NO_INIT；不制造初始化，也不填写零误差。原V3历史科学结果未修改。

- [最终16组合主表](RESULTS.csv)：8个原生结果、8个未初始化记录，完整原始观测分母与共同支持。
- [结果、输入处理与局限](RESULTS_AND_USE.md)：包含实际公里级漂移、有效位置长间隔、物理点与角定义、全部执行历史。
- [实际输入与模块更新](ACTUAL_INPUT_AND_UPDATE_COUNTS_T03.csv)：双fixed/总配对、163–173秒相邻有效位置间隔、RD/RP/HV真实更新。
- [独立复算](NUMERICAL_CHECK_0P15.json)：T02/T03全部128个OWN/COMMON指标及主表转录核同，最大差1.82e−12。
- [执行计数与身份](EXECUTION.json)、[T03输入计划](RUN_PLAN_T03.json)、[全部原生封存](ALL_NATIVE_SEALED_T03.json)、[最终离线评价](EVALUATION_SUMMARY_T03_0P15.json)。

NMB原生进程正常退出，但四段均有显著轨迹失效。有效对齐降低了航向误差，仍未消除长位置缺测期间的公里级漂移；不据此宣称迁移精度成功。F04较F03更差的序列也照实保留。

时间处理由GNSS/直接IMU及SDK速度的源内事件关系决定，不按参考误差择offset；HV按移后时间重配原A1，使用同一冻结公式。0.15秒门限先由20 Hz接收时间分布确定，不按RMSE选择；见[参考时间间隔](REFERENCE_TIME_INTERVALS.json)。该处理称有效测量对齐，不称硬件时钟校准。

## 保留的历史身份

初始零offset方案见[八段初始计划](EIGHT_SEQUENCE_PLAN.csv)。T01配置block-list与原生inline解析器不兼容，整轮未准入；T02只修正配置序列化后保存零offset结果。T02按统一0.15秒重评的表见[RESULTS_T02_0P15.csv](RESULTS_T02_0P15.csv)，原0.1秒完整主表与复算保留于[historical_0p1](historical_0p1/RESULTS.csv)。初始计划不能替代当前T03的输入和结果身份。

实际原生进程调用T01/T02/T03各8，共24（含T01的4个求解前拒绝）；最终采用8次。离线方法评价T02/0.1、T02/0.15、T03/0.15各8，共24。XB8个方法—序列组合只登记NO_INIT，未启动求解器。每轮原生全部封存后才打开参考，原生reference open均0。

真实运行根：`/mnt/g/LegSA-GINS-project/新数据实验_20261005/STAGE_R5_NMB_XB/`。`ATTEMPT_03/`为最终结果，`ATTEMPT_02/`与根目录T01原文件保留。执行脚本使用本项目实际路径，重放须另建输出身份，不覆盖已封目录。
