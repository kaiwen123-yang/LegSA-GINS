# 原 V3：可直接进入正文的效应量

所有数值属于原科学冻结 `7d43b9af26120ed5dde21f53e515386361072ba6`、原二进制 `96ae436d...`、原 v3 评价器 `aa049248...`。本块只是选择原 token 和对已保存的 45 个 ADD case 标量作完整描述性汇总；无新 solver/provider/evaluator，无原始数据或参考读取。方向定义为 Full − 同 case 的组件关闭配置；负值表示较低 RMSE。正文不以内部 F04/A06 等代码作方法名称。

## 优先写进 Results 的三组事实

1. **主方向观测的实际收益。** 三自然录制相对于“无在线航向 GNSS/INS”的 yaw RMSE 分别为 BY2 `8.089647 → 1.886272°`、BY2H `7.137488 → 1.933770°`、BY2O `5.739038 → 2.433815°`。这是完整配置对结构基线的组合对照；所有方法共享双接收机初始化，不能借它宣称单一 SA/RD/HV 或新 AR 的贡献。Full 的水平 RMSE 并非三个序列都优于该基线，必须把位置与姿态分开。
2. **SDK tilt 是幅度最明确的组件结果。** CORE 同 case 共同完成 519 对，增加 RP 后 roll/pitch 的 RMSE 配对差中位分别为 `−1.072003171° / −0.663802911°`，均值 `−1.789550009° / −1.026838025°`；519 对全部降低，两配置都失败 22 对、没有单侧完成。这比“tilt produces more consistent attitude effects”具体得多。
3. **SDK HV 的典型收益与特殊条件收益要分开。** CORE 519 对的 H RMSE 差中位 `−0.001118518 m`、均值 `−0.010650602 m`、472 对降低。更有解释力的是原 ADD：位置/RV/RD 失去、航向保留的 D62 20 s 条件，9 个完整 placement 的全窗 H RMSE 中位从 `7.960868926 m` 降至 `0.240759134 m`，逐 case 配对差的中位 `−7.749902307 m`，9/9 降低；对应完全 GNSS 失去的 D61 20 s，两配置中位约 `10.29 / 10.30 m`，配对中位差仅 `−0.003647717 m`。这支持条件融合的工程作用，不支持纯腿式独立 outage bridge。

建议英文结果段：

> In the heading-retained 20-s position/velocity-loss cases, enabling robot-reported horizontal velocity reduced the median whole-window horizontal RMSE from 7.961 m to 0.241 m across all nine placements. The median of the nine case-paired differences was −7.750 m. With heading also unavailable, the corresponding 20-s complete-loss cases had median whole-window RMSEs of 10.292 m and 10.301 m with and without the aid, respectively. These values characterize the original recorded-window experiment; they are not errors restricted to the outage interval.

## 两个应量化的代价

- **SA completion–agreement trade-off。** Full 完成 519、SA-off 完成 513；6 个 Full 独有完成、0 个反向、22 个双方失败。共同 513 对的 H 差均值 `+0.024244628 m`、中位 `+0.000981210 m`，yaw 差均值 `−1.738979774°` 但中位 `+0.000257994°`。可讲多完成了具体强故障并改善部分尾部，同时有位置代价；不能只写 universal robust improvement。
- **方向计数不能替代幅度。** HV 的 Up 在 365/519 对变大，但中位差仅 `+0.000004215 m`，均值反而 `−0.000603775 m`。RD 的 H 在 453/518 对降低，而中位差只有 `−0.000145376 m`；yaw 437/518 对变大，但中位增量 `+0.000596004°`。正文应给出效应量后再解释符号，不能把大量微小差别写成强烈的性能惩罚。

## 完整数据入口

- `ORIGINAL_V3_NATURAL_EXACT_33.csv`：原自然 33 方法/序列行的全部字段、原 token。
- `ORIGINAL_V3_COMPONENT_EFFECTS_EXACT_28.csv`：4 个单开关 × 7 个量，均值/中位/方向/失败成员全字段。
- `ORIGINAL_V3_CORE_OUTCOMES.csv`：原 V3 全 11 方法 CORE completion/divergence/no-heading 记录。
- `ORIGINAL_V3_ADD_HV_WHOLE_WINDOW_BY_DURATION.csv`：D61 10/20/30 s、D62 10/20 s，每组全部 9 case 的 Full/no-HV 中位/范围/成对差。
- `ORIGINAL_V3_ADD_HV_ALL_45_PAIRED_CASES.csv`：45 个完整 case 成对标量和 run/config/nav/evaluator/source 身份。
- `EFFECT_SIZE_SOURCE_PINS.json`：四个只读原表前后 SHA。
- `extract_original_v3_effects.py`：无需估计器的可复核提取/统计入口；重跑此脚本会覆写本目录派生表，不写任何原 science。

原 ADD 源 `CLEAN8_PROTOCOL_V3/07_AGGREGATE/ADDENDUM_TABLE_V3.csv` SHA256 `82aaef841c4e62d13ce4c4a2625b063ec3ac02ffc379db835cf1452486c978bb`。495 行/45 case×11 配置完整机器核；所用 F04/A06 共 90 行均 56642 匹配点、完整 66–340 s 窗。上述 45 对全部选入，无 metric/placement/epoch 筛选。`median(Full−noHV)` 不等于 `median(Full)−median(noHV)`，表中两者不能混用。D61/D62 的信息和 HV 准备条件不同，跨族不是只改变航向的单变量实验。
