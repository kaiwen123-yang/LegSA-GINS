# N09 C00：正常GNSS路径的事件负对照

两个对象均使用原BY2 C00，A04/RUN_00006和F04/RUN_00004。N09按可选能力扩展解释，只有三GNSS有效位全失效的既有事件才允许RP-only；原协议未证实要求独立RP。此处没有这种合格机会，不借正常路径结果证明无GNSS报文时的异步调度。

两组各8214个来源测量键全部一一配对；接受、实际EKF R、dx/actual_delta以及全部56642个共同IMU末状态精确相同，未出现首分叉、新增/缺失键或重复键。比较器的first_difference_categories为空，actual_final_counters两侧逐字段相等。原生五输出各字节一致和离线142字段相同是已单独登记的证据，此项不会再调用它们。

|方法|position|RV|实际yaw接受|RD|HV|RP|新增RP-only实际尝试|
|---|---:|---:|---:|---:|---:|---:|---:|
|A04|1369|1369|1348|1069|1369|1369|0|
|F04|1369|1369|1348|1108|1369|1369|0|

上表是全流实际计数，原版与候选相同；没有把C00任意查询子窗称为故障窗。时间键为原context measurement_time及GNSS身份；共同IMU按同一imu_seq/time，无插值，实际arrival仍UNKNOWN。

本项新读3条流，另一条C00/F04基线复用N12完成缓存，未重复打开原载荷。每条新流均完整到EOF并核序号、首尾和身份，见[N09_C00_READ_RECEIPT.json](N09_C00_READ_RECEIPT.json)。只读算术和关联不增加native/evaluator/provider/reference读取。候选每对象56642次完整P检查仍为NONPOSITIVE_DIAGONAL；基线只核EKF前后P，正定前置未满足，归一化对称/Cholesky未执行。此技术VALIDATED不是P或算法科学正确性PASS，零scale来源见[共同P边界](../../P_MODEL_BOUNDARY.md)。

小摘要与源事件偏移分别在[N09 A04](N09_RP_ONLY__RUN_00006/SUMMARY.json)、[N09 F04](N09_RP_ONLY__RUN_00004/SUMMARY.json)。完整逐更新/逐IMU对照原位在`<VALIDATION_ROOT>/analysis/comparisons/N09_RP_ONLY__{RUN_00006,RUN_00004}/`，缓存来源和hash在读取回执。不由此推出A1无影响或所有输入行为都未改变。
