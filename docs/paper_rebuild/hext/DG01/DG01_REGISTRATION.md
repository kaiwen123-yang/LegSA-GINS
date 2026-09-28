# DG01 登记：原始 GNSS 诊断定义

2026-09-27，计算前登记。起点 eaa4b67eb711865752aa2a72d544992b9cab844b，stage/clean3-math-repair。29 条既有未跟踪文件逐条、逐哈希保持不变。登记提交后才计算统计量；本文件不含预期结论。

## 输入、时窗与访问边界

W 为本工作树；RAW_ROOT、CLEAN_ROOT 从 DATA_PATHS.CLEAN3R4.local.yaml 读取。HX02 采用 HX02_PREREG.md 所定义的 `<CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY`，不是任务文字中的简写目录。12 个原始文件为三个序列、两接收机的 gnss{1,2}-{raw,status}.csv，使用 RAW_FILE_HASH_LOCK.csv 的 relative_path 和 sha256，内容解析前逐个验证。预检已经验证 12/12，计算程序再次验证。

| 序列 | base_time Unix UTC s | 闭评估窗 / s |
| --- | ---: | --- |
| BY2 | 1772784000 | [66,340] |
| BY2H | 1772784000 | [413,683] |
| BY2O | 1772780400 | [3186,3563] |

RAWX 的 UTC = GPS epoch + week×604800 + rcvTow − leapS；NAV 使用同流 GPS week 与 iTOW，减同一 leapS。消息/字段清单另按导出 stamp 统计窗口内数量，以区分接收/观测时标；status 按 sys_stamp，保留 header 时间。没有从参考估计时差。BY2O 主段固定为 [3369.94,3411.95] s，outside 为该闭段的补集。

只读 HX02 已有 RINEX obs/nav、.conf、.pos 和 native 航向有效表；三序列 RINEX 均已找到，不重建、不调用 bridge。CLEAN4 只读指定小数双差表、manifest 与生成代码定义。路径含 trace（不区分大小写）、.bag、.fpl 的文件一律拒绝，即使它是 RTKLIB 日志；因此不读取 trace 日志。不打开参考轨迹、不运行任何导航算法或评估器、不生成 provider。v3 C00 表只读 time/yaw_valid，列位置由文件头识别。

所有中间数据写 `<CLEAN_ROOT>/stages/CLEAN10_GNSS_RAW_DIAGNOSTIC/DG01/`；仓库仅登记目录与 dg01_*.py、AGENTS 末尾。图缓存若需要只用指定 DG01 scratch，结束删除本任务创建文件。单线程，随机过程不用；不调整参数或按结果筛选。

## D1 消息与字段

raw 按 name（所有实际出现的 UBX/NMEA/其他类型）统计全文件及窗口数量、首末接收时间、窗口 rate=count/(end−start)。每个 status 字段统计非空记录数，保留原名。语义解码清单：RXM-RAWX、RXM-SFRBX（仅清单）、NAV-PVT、NAV-HPPOSECEF、NAV-SAT、NAV-SIG、NAV-RELPOSNED、NAV-CLOCK、NAV-TIMEGPS；其他消息仅做清单，不推断未提供字段。

UBX 帧按长度和 checksum 检查，失败单列，不将失败帧解释成有效观测。NAV-RELPOSNED v1：relPosLength cm + HP 0.1 mm，heading 1e-5 degree，flags 的 carrSoln bits 3–4、relPosHeadingValid bit 8、relPosValid bit 2；报告分布、有效率、length−0.35 m 的中位/P05/P95/最大绝对值及 reference-station ID。该消息的基准站身份不能仅凭名字判为两机短基线，不与参考比较。

## D2 信号与固定状态

RAWX 按 (gnssId,svId,sigId,freqId) 统计；系统名 GPS/SBAS/Galileo/BeiDou/IMES/QZSS/GLONASS。跟踪数是 RAWX 出现的不同 svId 数。NAV-SIG 分开报告 prUsed、crUsed、crCorrUsed；“载波参与并用改正”定义为 crUsed AND crCorrUsed，按不同卫星计数，不把它称为接收机内部整数固定卫星清单。NAV-SAT 的 elevation/azimuth 与 svUsed 单列；status 的 sol_num_sat_* 保留自身语义。

C/N0 分箱 [0,5),[5,10),…,[60,65)，超出范围另列；高度角 [-10,0),[0,10),…,[80,90] degree。逐信号汇总 n、median、P05、P95；C/N0×高度角统计同时留样本数。NAV-SAT 与 RAWX 以同接收机最近导航历元关联，要求严格小于该处 NAV 网格半周期；等距或缺失不关联。

周跳指标分别报告：(a) RINEX 载波 LLI bit 0；(b) RAWX 同卫星同信号 locktime 比前一记录减小；(c) cpStdev 低四位为 15 的溢出/无效样本。首样本不算 lock reset，65535 饱和不算减小。三种指标不能互称同一“真实周跳”；同时给 b OR c 的事件样本计数。率=count/(窗口秒数/60)，另给每信号有效暴露分钟；不以未知的首样本补零事件。保留 cpValid、halfCyc、subHalfCyc，CMC 连续弧在失效、lock reset、clock reset、时间非递增或间隔>1 s 时断开。

NAV-PVT carrSoln=(flags>>6)&3，保留 none=0/float=1/fixed=2/其他。hAcc mm、HPPOSECEF pAcc 0.1 mm，转换 m。两机 fixed 时间线按整数 iTOW 精确内连接，并保留 outer-join 缺失计数；both/one/neither 的分母为双方均有 PVT 的导航历元数。最长连续时长为同状态相邻历元区间长度，含末端一格并截断窗口，缺失或间隔>1 s 断开。与 v3 yaw_valid 在舍入到微秒的相同 time 对照，若时标不同则按 GPS 网格标识关联，报告匹配数、偏移分布和一致率，不调时差使其一致。

## D3 两机一致性

RAWX 配对键为 week 与 round(rcvTow/0.2)，同一键只接受两边各一个样本；保留未配对和重复数。原始 rcvTow 差直接报告，不把配对网格当作时钟同步。公共集合按完整信号标识交集；逐系统卫星集合另按 gnssId/svId。逐信号 C/N0 差为 GNSS2−GNSS1。同历元同信号的 lock-reset/overflow 各报交集计数、并集计数和交并比；并集为零则比例 UNAVAILABLE。

## D4 小数双差

CLEAN4 phase2_runner.py::_fractional_dd_rows 的 proxy_implied 分支是 phase−geometry 再取 wrap；本任务按提问使用 geometry−phase，故有符号量相反、绝对值相同。小数映射沿用 x−ceil(x−0.5)，范围 (−0.5,0.5] 周。不得引用该旧表中基于解算方向或参考的残差作为本次观测诊断。

HPPOSECEF 两机按整数 iTOW 精确成对，再沿用 _proxy_common_grid_associations：唯一最近共同导航历元，距离严格小于局部共同网格最小相邻间隔的一半，等距/无邻格拒绝。NAV-PVT 状态取同一 iTOW。固定解样本是主诊断；非双方 fixed 的有限位置另算，标明几何代理不可靠，不称固定解基准。

每个系统、sigId 与相同波长组内，使用两机共同、cpValid 且 halfCyc valid 的信号；cpStdev=15 不进入残差。每历元 pivot 取两机较低高度角的最大者，同值按 svId 升序；无高度角则按 svId 升序并记录。不设高度角/CNO删样阈值。卫星坐标按已有 RINEX 广播星历在接收时刻减传播时间求出，包含地球旋转修正；HPPOSECEF 固定位置是唯一几何代理，不读取参考。GPS/Galileo/BeiDou/QZSS 用广播 Kepler 模型，BeiDou GEO 用其专用旋转；GLONASS 同波长组没有两颗可用卫星时记录 UNAVAILABLE，不把异频 DD 强解释为整数。

令 Δρ_s=|X_s−r₂|−|X_s−r₁|，ΔL_s=λ(Φ₂s−Φ₁s)。残差 x=[(Δρ_s−Δρ_p)−(ΔL_s−ΔL_p)]/λ。每个信号组、both-fixed/other 分别给 signed median、P95(|x_wrapped|)、|x_wrapped|>0.25 比例、样本分母、直方图（−0.5 至0.5、步长0.025）；再按窗口起点锚定的20 s 时间段和稳定卫星/pivot组合给 median/圆均值、圆离散与数量，描述时间稳定性，不校正相位。缺星历/无几何/无pivot计入不可计算原因。

## D5 CMC 多径代理

载波距离 L_i=λ_i Φ_i。原始 CMC=P_i−L_i。双频时优先使用同星另一频率、标识排序最小的有效信号 j，gamma=f_i²/f_j²，MP_i=P_i−(1+2/(gamma−1))L_i+2/(gamma−1)L_j；这消去一阶电离层项，不代表纯多径。每个连续弧内去均值，SD 用 ddof=1，少于2样本不可计算。没有有效第二频率时另列 single-frequency detrended CMC：按从窗口起点锚定的60 s块、各连续弧线性最小二乘去常数与时间趋势，不声称完全消除电离层。两种代理绝不混汇。

按序列/接收机/卫星/信号/高度角箱/主段或段外报告样本数和上述残差 SD，另留弧级统计。未读取 Go2 IMU，不能用这些代理独立判别振动、多径与接收机相位跟踪误差。

## D6 配置审计

逐序列列出 pos1-posmode、elmask、snrmask（旧键与2.4.3实际 *_r/*_b/*_L1/*_L2/*_L5）、navsys、frequency、dynamics；pos2-armode/gloarmode/bdsarmode、arthres、arlockcnt、arminfix、arelmask、elmaskhold、baselen、basesig、rejionno、maxage；out-solstatic/out-outstat、ant2-postype。区分显式值、缺省值、未知/过时键。核对本机原版2.4.3 options.c/rtkpos.c/rtkcmn.c 的读取与作用条件，不执行二进制。

官方公开文档页面提供2.4.2用户手册，2.4.3为beta；不冒称存在已核验的2.4.3独立手册。将官方手册 moving-base 模型 E.7(7) 与实际2.4.3源码交叉核对。没有手册推荐的通用阈值时写“无统一推荐”，不凭结果给新的数值。建议 diff 只消除过时键、显式写出等效缺省、增加诊断日志建议；保持物理基线和噪声、AR门限、星座、动力学原值，不执行。若建议需要新标定，写待独立标定，不给拟合数。

.pos Q=1/2/5/其他分别计数，GPST 转UTC后裁窗；与 PVT共同历元按前述唯一最近半格规则关联，报告 overlap 数量/分母。已有 native 航向表的 rtklib_q/valid 另列，用于解释其原生配对分母；不把原生表缺失Q当作.pos Q=5。不读取 trace 日志，不能据配置“启用”推断每次更新都实际应用基线约束。

参考文档：[RTKLIB 官方手册](https://www.rtklib.com/prog/manual_2.4.2.pdf)、[官方版本说明](https://rtklib.com/)、[u-blox ZED-F9T 接口](https://content.u-blox.com/sites/default/files/ZED-F9T_InterfaceDescription_%28UBX-18053584%29.pdf)。

## D7 有效历元与运动

使用既有 native 航向表的有效标志，EXT04 FAR/PAR 分开，不作新的算法评估。GNSS1 NAV-PVT 的 ground speed<0.2 m/s 为 low-speed；其余由相邻有效 course 差 wrap到±180°再除dt，|rate|>10°/s 为 course-turning，其余为 translating。dt<=0或>1 s 时 course rate 不可计算；低速不解释course，未读IMU不称该量为机体角速度或步态。按三类/unknown给方法有效数、总数、有效率与历元分布，另按固定20 s块统计。以上分界计算前固定，不优化分类使结论更明显。

## 报告与缺失

分位数 linear；非有限明确计数；不做显著性检验，不按诊断数值停止或删除样本。结论只陈述观察和局限，原因判断留作者。每个汇总有来源别名/明细定位。三图依 publication/style.py/qa.py、174 mm、PNG长边至少4096，并实际检查PNG。原始明细和sha256清单留G:，仓库≤20MB。两次提交后push，scratch为空；无交接包。
