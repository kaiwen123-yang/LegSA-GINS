# Q2 科学来源与版本对应

主图和两补图来自已有保存结果。它们不改变冻结V3，也不把新增研究分支写入V3性能。

| 方法或证据 | 原身份 | 在本组中的用途 | 文件 |
|---|---|---|---|
| RTKLIB原配置 | HX07R V0；GPS+BDS、双频、continuous AR | 主图和完整补图 | data/*_V0_full_saved_heading.csv.gz |
| RTKLIB星历变体 | HX07R V0E；仅换外部广播星历 | 完整补图 | data/*_V0E_full_saved_heading.csv.gz |
| RTKLIB多星座 | HX07R V1；在V0E上增加Galileo、QZSS | 完整补图 | data/*_V1_full_saved_heading.csv.gz |
| RTKLIB保持固定 | HX07R V2；在V1上采用fix-and-hold | 完整补图 | data/*_V2_full_saved_heading.csv.gz |
| C-LAMBDA / C-ILS | EXT01，EXT V2 generation 2，独立硬长度约束目标 | 原始方向路线补图 | data/*_all_methods_all_window_epochs.csv.gz |
| C-WLS | EXT02，同一代独立单基线约束加权最小二乘 | 原始方向路线补图 | 同上 |
| DD-KF | EXT03，同一代双差滤波／随机长度伪观测／MLAMBDA | 原始方向路线补图 | 同上 |
| FAR、声明PAR | HX02 EXT04，三记录各两策略 | 零接受结果与完整失败分类 | tables/FAR_PAR_ALL_THREE_TRIALS.csv；BY*_EXT04_C00_FAILURE_LEDGER.csv |
| DG01、DG01R | 原始质量与钟差／半周／转换诊断 | 输入与解释依据 | tables/DG01*.csv、DG01R*.csv |
| RTKLIB trace4 | 保存的BY2/V0唯一仪器化重放；输出字节与原结果一致 | 主图长度与执行机制 | tables/RTKLIB_EPOCH_DIAGNOSTICS.csv及35行大残差表 |
| 同历史RINEX恢复 | AR_V3_INPUT_HISTORY；六观测流 | 输入历史一致性 | tables/INPUT_AUDIT_SUMMARY.json及差异表 |
| 候选器有限资格 | 12个保存真实几何上的合成资格检查 | 补充实现资格，不充当真实固定率 | tables/CLASSIC_QUALIFICATION_RESULTS.csv |
| 两历元角度原型 | 16个机制槽；14返回、2错误先验超时 | 历史研究支线，列入完整工作清单 | tables/MOTION_PAIR_RESULTS.csv |

场景：BY2是常规行走；BY2H／原by3是包含大幅机身运动和明显振动的同路线记录；BY2O／原by1是单侧天线遮挡。实验窗分别为[66,340]、[413,683]和[3186,3563] s。绘图使用各窗起点作为0 s，保留原始数据键和追溯路径。

原始双天线方法比较的量由横向安装基线的水平投影换算，参考量为商业融合设备的Euler航向；有roll/pitch时两者不完全等价。C-LAMBDA和C-WLS是有效候选输出，未定义整数接受检验。DD-KF的ratio-accepted子集为78/70/5，不是真实整数正确率。C-LAMBDA/C-WLS使用GPS L1，DD-KF使用GPS+BDS双频。图件用于展示各处理链的结果和观测条件，不能直接与完整导航姿态混成无条件排名。

FAR/PAR表的完整原生历史分母为1509、1423、2231。EXT V2大幅运动记录的完整历史为1483，三场景绘图窗口配对分母为1370、1350、1885。保留各自实际历史与评价窗，不把这些分母相互替换。

trace4完整历史有1509个历元、177个Q1；本主图使用共同评价窗内的153个Q1，其中35个超过长度日志阈值。下排的横坐标来自保存的钟差校正后输出时间，上排则使用已有评价表时间。trace4的实际日志和解算结果已在10月6日保存，本次没有重新调用RTKLIB。

四配置补图复用2026-10-09已完成布局和三种格式，重新逐表读取、检查PDF并审彩色与灰度。原始方向补图改成误差累积分布，让重叠的方向跳变曲线更易读；全部有效点均参与，原时序也完整复制在data/。

复现命令（只作绘图与整理）：

```sh
NATURE_FIGURE_SCRIPTS=/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts OPENBLAS_NUM_THREADS=1 python3 /mnt/g/LegSA-GINS-project/V3五问题论文组图_20261011/heading/build_heading_section.py
```

运行将重置图件的人工视觉检查状态，交付状态由检查后的JSON与SECTION_PACKAGE.json记录。
