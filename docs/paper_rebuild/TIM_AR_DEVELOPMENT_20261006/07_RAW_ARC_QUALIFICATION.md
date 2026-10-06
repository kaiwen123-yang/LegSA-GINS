# 固定 BY2 80–82 s 的 raw 元数据资格审计

按冻结提交 8d4dc0166c7ea98cea78ad1b44bc98ead5bae3f1 的 [RAW_ARC_80_82_CONTRACT.md](RAW_ARC_80_82_CONTRACT.md) 完成。只读两接收机原 hash 锁 RAW CSV 及其既有 UBX 重建字节流；UBX校验和和来源 hashes 通过，独立按原始 GPS week/tow 配对。没有使用缓存强制统一的时间作为配对证明。

**该固定窗具有一个覆盖全部 10 个配对历元、含 4 个连续公共 GPS L1 信号的元数据候选弧。可以继续设计有限时间弧研究，但几何与整数资格尚未通过，也未新增任何 solver。**

## 时间与连续性

- 两端分别 10 个窗内 RAWX；10 个 exact unique pairs；无重复时间或未配对记录。
- 实际支持 80.197999954–81.997999907 s，10 点，跨度约 1.8 s；没有在 80.0 s 插值补点。
- 全窗严格有效且接收机两端 arc token 均保持不变的 GPS L1：SV6、SV11、SV17、SV19；每个完整 identity 为 gnss_id=0、sig_id=0、freq_id=0。
- 全窗这 4 个信号满足 code/phase 有效、resolved half-cycle、原严格 CNO/不确定度/正 locktime 条件；其余信号发生事件不被当成全窗连续支持。
- 元数据候选固定 pivot 为按 identity 文本排序的 0:11:0:0，仅是稳定信号存在性说明；未作最高仰角选择、卫星几何检查或 DD 求解。
- 窗口首样本左删失：之前是否连续、是否有未揭示相位偏差仍未知。

全部窗内 GPS L1 跟踪记录累计 lock reset 3、half-cycle 状态转换 3、CP-valid 转换 17；这些计数可重叠。继承规则的 cycle_slip_detected 计数为 20，是跟踪事件标志，不代表经独立确认的 20 个物理整周跳变。clock reset、时间逆序、>0.21 s gap 事件均为 0。

## 同窗全部信号库存

下列均为每原始 gnss_id/sig_id/freq_id 分组的公共信号数量范围，不是独立卫星总数或已建模 AR 能力。列出的这些键均覆盖全部 10 个配对时刻。

| 原始键 gnss/sig/freq | common | 双端 CP valid | CP valid 且 half resolved |
|---|---:|---:|---:|
| 0/0/0 | 7–9 | 4–7 | 4–5 |
| 0/3/0 | 6–7 | 3–4 | 3–4 |
| 1/0/0 | 1 | 1 | 1 |
| 2/0/0 | 4–5 | 4 | 4 |
| 2/6/0 | 5 | 4 | 4 |
| 3/0/0 | 11–12 | 9–10 | 6–9 |
| 3/2/0 | 3 | 3 | 3 |
| 5/0/0 | 3 | 3 | 3 |
| 5/5/0 | 3 | 3 | 3 |

gnss_id=6 的不同 sig/freq 通道也全部保留在小表中；不能将其跨频率/星座相加后直接声称 GPS L1 DD 可用星数增加。不同 constellations、波长、系统间偏差、相位语义、星历和随机模型还需单独核查。当前 A 的 GPS L1 限制不是原数据仅有 GPS L1 的证据。

[RAW_ARC_ALL_SIGNAL_SUMMARY.csv](RAW_ARC_ALL_SIGNAL_SUMMARY.csv) 的 min/max 在该原始键出现的历元计算，同时列出 paired_epochs_present；例如只出现 7 点的键，不得将其条件 min 推广到全部 10 点，缺席点计数应为 0。逐历元表保留实际出现记录。

## 对下一步的具体含义

元数据支持在既定 10 个历元内预登记 5 点生成块+5 点延迟检查块，无需先按航向误差再选窗。但 4 星 GPS L1 仍是低冗余；时间近邻的共同误差未建模，不能把两个块当作独立证据，也不能预先断言多历元会解决 D 的错候选。

接下来需先核真实卫星几何、固定 pivot/弧的整数变换和跨历元 Q，再冻结任何新的科学小试。同信息方法对照还应讨论本窗确实存在的其它频点/星座。当前结论只到“候选输入存在”，不开放 EKF 接入。

## 实际调用与回执

SPP=0、C-ILS=0、导航=0、参考读取=0。strace 显示两份登记 RAW CSV 均只读，无参考打开；解帧读取的是登记 UBX 来源。结果保存于 <TIM_AR_SCRATCH>/RAW_ARC_80_82。

[RAW_ARC_SUMMARY.json](RAW_ARC_SUMMARY.json) 提供输入/代码 hashes、配对/事件计数、弧与I/O回执；逐历元 [RAW_ARC_EPOCH_METADATA.csv](RAW_ARC_EPOCH_METADATA.csv)、全部信号 [RAW_ARC_ALL_SIGNAL_COUNTS.csv](RAW_ARC_ALL_SIGNAL_COUNTS.csv)、GPS跟踪 [RAW_ARC_GPS_L1_TRACKING.csv](RAW_ARC_GPS_L1_TRACKING.csv) 可复核。脚本为 raw_arc_audit.py 与只读派生 summarize_raw_arc.py，没有修改原始数据、旧结果或生产求解器。

独立派生表复核见 [RAW_ARC_METADATA_REVIEW.json](RAW_ARC_METADATA_REVIEW.json)：177 行事件计数、稳定四星的 80 行双接收机跟踪记录与 10 个原始时标配对均一致；未重开原始文件或调用求解器。
