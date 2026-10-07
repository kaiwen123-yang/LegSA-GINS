# 用户提供的 Go2 高层接口：来源语义更新

2026-10-07。来源为用户提供全文，已原字节保存并绑定 SHA256：5b1126a133960dcc86728c4df7295d90d013e5f0ebc14843f0814db2d7f5cf1a。原文为 sources/GO2_HIGH_LEVEL_INTERFACE_USER_EXCERPT_20261007.txt；未给官方 URL、文档版本、实际固件或旧采集器身份。本记录只解释该文本，不把它未经核实地推广到所有 Go2 版本。

## 已能明确的内容

|条目|原文直接支持|对本项目的用途/限制|
|---|---|---|
|高层状态主题|rt/sportmodestate，类型 SportModeState_|支持新采集的消息/topic身份记录；尚不能证明旧文件来自同一固件/schema|
|状态 error_code|原文362、375–401行说明它反馈运动状态机；例如100灵动、1001阻尼、1002站立锁定、1013平衡站立|此文档语义下不能用非零直接判源故障；0也没有被此表定义成正常模式|
|控制函数返回码|返回0是调用成功；4201动作超时、4205状态机未初始化、3104 DDS超时等|与消息内state.error_code分域记录，不能混用；调用成功不证明实际跟踪成功|
|Move(vx,vy,vyaw)|设定速度采用机体坐标系；vyaw rad/s；最新命令维持1s，运控不对该命令滤波|明确的是命令坐标，不是反馈velocity()坐标或独立腿速度；记录命令发送/返回/接收时刻|
|Euler(roll,pitch,yaw)|输入rad；机体相对轴、z-y-x顺序；支持平衡站立/移动姿态设置|可用于未来roll/pitch/yaw激励；命令值不能当独立姿态真值，也不能自动替代反馈rpy的具体世界系定义|
|IMU字段|quaternion顺序w,x,y,z；gyro rad/s；rpy rad；accelerometer m/s²|与现有解析单位/顺序相容；没有解释内部融合、是否去重力或各字段物理采样/延迟|
|stamp与示例dt|TimeSpec stamp；示例dt=0.01是命令循环步长|没有说明芯片采样时刻、SDK发布/到达延迟、时钟映射；不能据示例推反馈100Hz或字段独立带宽|

## 对现有质量门的直接影响

foot_pair_provider.py 的历史173行要求 error_code==0，否则 SOURCE_ERROR_CODE；body proxy审计也把它作历史源门。该策略不能作为上述新文档版本的通用SDK质量门。新接口模式码应按明确schema解释，已识别的非零运动模式本身不是错误；动作模式也不能认证无滑移、接触或源数据质量。

已封存三窗的先前完整源审计在本次范围内报告 error_code均0且没有该门拒绝。因此新增文档不构成旧2510个SKIP由非零模式被误删的证据；这些SKIP的P/H/R诊断和NAV身份结果保持。另一方面，此文本没有给0定义、且旧collector/firmware未知，所以旧0值也不能再由字段名推为已验证“硬件健康/无故障”。历史门是当时固定的工程规则。

进一步静态检索（仅当前Git跟踪的scripts/src/tests）还发现同一历史约束在四处出现：

|当前代码位置|旧规则|本次处置|
|---|---|---|
|scripts/paper_rebuild/carrier_phase/foot_pair_provider.py:173|error_code==0，否则SOURCE_ERROR_CODE|记录新schema适配缺口，旧运行不重写|
|scripts/paper_rebuild/carrier_phase/trusted_heading_body_proxy_audit.py:447|非零增加SOURCE_ERROR_CODE|报告该统计的历史语义限制|
|src/legsa_gins/paper_rebuild/body_velocity.py:61|非零标样本invalid|不能原样用作本文档模式字段的通用读取器|
|scripts/paper_rebuild/research_audit_20261006/pilot.py:144|断言error_code==0|历史BY2试验假设，不能当新固件通则|

上述静态检索不是旧全库原始数据重新审计；旧0值与模式表不同这一事实尚需实际collector/firmware或对应IDL记录解释。已登记的历史比较身份仍可保留，但其“SDK无故障”解释不能据此升级。

本轮不修改旧provider、旧CSV、已封存运行或其参数。需要新采集使用者显式登记schema、topic、固件与原始字段；未知版本返回UNKNOWN而非默认正常/错误。若未来重处理旧数据，应另行登记为输入语义变更，不能改写旧结果身份。

## 仍未解决的物理来源

这份文本未说明 foot_position_body/foot_speed_body 的内部生成链，也未提供原始关节q/dq、SDK body原点与IMU外参、状态velocity()世界/机体系细节、物理同步、统计cross或噪声二阶矩。Move命令的body frame不传递给state.velocity()，高层接口能控制姿态不证明foot数据独立于IMU。现有足端仍是SDK报告代理，不能改称已确认的编码器FK。

## 采集准备的具体修订

新日志至少分开保存：command_name、command_arguments、command_send/return_time、command_return_code；state_topic、state_stamp、host_receive_time、error_code_raw、status_schema_id、interpreted_motion_mode。保留实际反馈/外部参考、全部未知值和丢帧，不用命令覆盖测量。

转动场景可把BalanceStand+Euler作为可重复姿态激励的候选接口，行走/转向可用Move命令序列；先按实际机器人/场地及参考能力冻结小幅动作。接口上限不是本实验推荐操作点；此记录没有发送任何机器人命令、设置模式或安排动作。支撑模式用于场景标签，与每足接触/无滑移证据分开。

## 接口如何服务三个研究场景

|研究场景|可用的接口线索|需要单独记录的事实|
|---|---|---|
|机体转动|BalanceStand 与 Euler 可构造站立多轴姿态激励；Move 的 vyaw 可构造行走转向|命令姿态、实际姿态、独立参考及两者时间分别保存；Euler 的 yaw 目标不是外部世界绝对航向标签|
|支撑变化|Move 的起停、行走和转向可诱发常规支撑切换；运动状态码可作高层场景标签|每足接触/力、关节/FK与可能滑移仍需低层测量；高层“站立/行走”不能替代每足的无滑移接触资格|
|载波中断与恢复|高层接口帮助重复相同动作脚本，配合独立遮挡事件时间|接口不提供GNSS断弧、周跳、真实到达或恢复标志；仍由接收机原始流及独立事件记录判断|

文档提示 Move 最新命令维持1s且不自动滤波，因此未来脚本需要显式记录命令保持及发送间隔，不能把发送时刻等同于运动开始。StopMove 会将内部运动参数恢复默认，不能在对照实验中当作完全不改变其余参数的纯暂停；恢复后姿态/档位等配置须重新记录。这里仅修订实验设计，尚未生成或发送实机控制程序。
