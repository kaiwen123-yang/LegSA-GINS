# 输入链逐函数/关键语句审查

审查基线 eb3cbed，本文所列文件为人工完整语义阅读；测试只升级对应函数的动态证据，不能把整文件所有分支称测试完成。外部协议字段用 u-blox F9 HPG1.32 Interface Description UBX-22008968 R01 §3.15.11、p146–148 核对：[厂商文档](https://content.u-blox.com/sites/default/files/documents/u-blox-F9-HPG-1.32_InterfaceDescription_UBX-22008968.pdf)。下述新反例均在实际项目Python函数运行，与原生滤波测试分开。

## input_generation/status_yaw_builder.py（329行）

- 15–38 `_as_float/_read_csv`：BOM兼容CSV全读，可限行；只拒NaN不拒Inf，文本存在不等于有效观测。不是流式大数据接口。
- 41–69 布尔和双时轴：header优先，缺失可退到Time；sys时刻独立。float Unix秒可能损失亚微秒，使用者需要按字段角色解释，不能靠fallback建立采集同步。
- 72–128 有效位过滤与rel字段：有该列时逐行要求rel_valid/ant_valid且ant_state=2；任一字段缺失计数。相对外部基站的向量必须由两台接收机在同参考定义下相减，不得把单台rel_pos当机载基线。
- 131–181 排序/插值：按header时间排序，二分寻找两邻居，对NED及精度线性插值。没有最大缺口、重复时间和未来可用时刻门；一小时缺口的中点仍产值（P-IN-04反例）。
- 184–245 A1：在G1时刻插值G2，求G2−G1；三轴acc以hypot相加，隐含两端独立。不含交叉协方差。225行给`−atan2(E,N)`，不是姿态解算或倾斜补偿。
- 248–284 单台方位明确diagnostic_only，保留该反证，不能引用成双天线运行。
- 287–313 std模式固定1.5/2或有界几何启发式；几何项用3D长度及horizontal accuracy，既非严格角协方差传播，也非经过GNSS误差相关校正的标准差。v3采用固定2.933193，不由此函数对XB调参。
- 316–329 sign/offset后`yaw_ned=wrap(90−yaw_body)`；sign=1,offset=0时合成为`90+atan2(E,N)`。provider不存在roll/pitch补偿，故原生倾斜反例不能由“provider已补偿”推翻。

## input_generation/imu_txt_builder.py（158行）

- 17–50 调旧Go2 parser，仅保留时间及gyro/acc齐全行；没有记录逐坏块原因；float筛选同样只拒NaN。
- 53–82 小矩阵乘法、RzRyRx构造和均值；输入角deg转rad，矩阵主动旋转。空均值返回零，不是实测偏置。
- 85–113 把FLU的y/z取反为FRD，再乘安装旋转；BY2默认roll=−1°是设备项，不可作为XB事实。
- 114–137 用最初最多1000条估计gyro均值，再以当前rate×实际相邻dt生成增量；dt≤0或>0.1丢去此增量。这个均值不验证静止，会把初始真实角速度吸进bias。缺口也不是零运动，后续loader时间差可能与积分区间不一致；需检查正式provider是否换过。
- 139–158 报告明确是parity input reconstruction，acc含重力且没有输出后修正。角色布尔是程序声明，不构成文件访问审计。

## input_generation/ubx_nav_pvt.py（117行）

- 20–56 数值/bytes解析用literal_eval，反证任意eval执行；list元素用`int(x)&255`会静默截断，不是严格byte域检查。
- 59–74 实际完整frame检查仅前4bytes和len≥92；NAV-PVT应是92字节payload+8字节封装，未校验header length/CK_A/CK_B。实测坏checksum与截到92-byte的frame均被接受（P-IN-02）。
- 68–70 velocity完整frame offset54/58/62对应payload48/52/56，signed mm/s→m/s正确（动态PASS）。71行sAcc取frame68:72，正确应为payload68即frame74:78。动态已知sAcc=0.05 frame被解成错误值（P-IN-01）。
- 77–117 根据name列筛PVT，取stamp或Time，异常静默跳行并排序；没使用测量iTOW/fix有效位也没坏帧计数。该接口不是通用raw适配。
- 影响界定：process_data_compat固定std_v=0.05且明确`pvt_sacc_used_for_velocity_std=false`，因此sAcc错位不直接改变该路径RV的R；不能把此缺陷夸成既有全部NAV必错。质量元数据的其它调用者仍须逐一追踪。

## input_generation/process_data_compat.py（490行）

- 30–56 明确15列GNSS和7列IMU；没有每测量valid位。
- 59–83 CSV/float同前；85–109最近邻二分，容差双向，允许未来且不消费记录；重复使用不自动满足实时因果。
- 112–148 对缺失前向填充再反向填充，完全不看时间距离。真实函数最小反例把1小时前velocity续填到缺口（P-IN-03）；dropna仅看None，不能滤Inf。
- 151–183 status位置取sys_stamp，hAcc同赋N/E，不根据fix有效位筛选；GNSS位置测量时刻/精度语义必须上游验证。
- 186–205 输出12有效位文本并显式禁止本接口注入故障/噪声；这一禁止真实有效。
- 208–270 提取PVT和status双差航向，拒trace模式；std override只改变yaw std字段，不改变物理定义。
- 272–345 时轴合并后无上限填RV/yaw，输出中的零缺失不代表真实源连续。固定RV噪声使sAcc解析bug不进入R；全部字段缺失才drop。适配旧parity时可以如实命名，不能用它对XB缺测“修好”。
- 347–377 生成IMU和覆盖统计；378–490写报告、输入文件名与source角色。`formal_allowed=true`并非自动物理许可；使用者仍需协议和provider门。

## paper_rebuild/clean5_parity/input_audit.py（122行）

- 15–38 CSV、有限数值分位数、header转换和iTOW舍入辅助；空统计UNAVAILABLE，无伪零。
- 41–71 完整UBX校验迭代器后按HP/PVT解码，PVT严格class/length；重复iTOW和HP/PVT键不一致硬停。只返回velocity/hAcc/vAcc，不受上述sAcc错误影响。缺失一个HP历元即全文件拒绝，是特定冻结链契约，不可无改造套XB。
- 74–87 hash锁且拒trace/bag/fpl在线role；没有读trace内容。90–107对照status float32与raw integer尺度，证明序列化一致性而非真值精度。
- 110–122仅最初1000条acc模长诊断，明确不根据结果挑静止窗；不能据此保证传感器比例正确。

## paper_rebuild/clean6_sensor_v21/providers.py（520行）

- 38–95 动态导入4个审计脚本（确有运行依赖，整仓清单含scripts）；锁合约/半合成注入case身份。副作用是sys.path插入，可导致未受控环境的同名模块替换，源commit本身不证明导入文件唯一。
- 98–139 输出不许symlink/覆盖未封存目录；resume核实际文件hash，seal不把原raw删除。report hash只保护所列文件。
- 142–154 A1圆周unwrap插值，有1.2s开区间缺口门，端点是真实观测可保留。动态跨360°/一小时缺口测试通过，反证所有provider都无缺口门。
- 157–195 HV：FLU→FRD后用Go2 roll/负pitch与status-A1 yaw旋到NED水平，再乘K=1/0.962142，std=0.132838。HV依赖GNSS航向和Go2惯导内部估计，不是独立速度观测；yaw缺失将HV标invalid，不能把0占位融合。位置/航向/HV共享信息需联合噪声或保守说明。
- 198–238 RP精确时刻/输入值一致后翻pitch，锁1.6°；GNSS只改第15列std到2.933193并对非目标token核对。
- 241–323递归残差统计对照、HV/PVT OLS、RP/重力比较；用于冻结校准复现而非外部真值。会读取历史校准定义但不在线读reference。
- 326–406生成三个BY2族provider：保留完整时程，IMU/RD原指针不改；HV/RP/heading-std派生，并验证hash及残差。这不是可直接传XB目录的通用入口。
- 409–434缓存冻结base并实现D61/62等注入；437–520 case生成确保先注入yaw再重算HV，源valid传递、D57原行号保留、其余源字节等同。真实/半合成标签在这里有正确覆盖，不把旧v2标签缺陷泛化到本模块。

## paper_rebuild/protocol_v3/providers.py（303行）

- 39–74 hash、exclusive写入、18列/行/token/空白字节门；只允许yaw与valid变，不能声称所有传感器在v3一起重建。
- 77–115把旧已实现航向扰动解释成1s半开时间单元/显式故障窗，绝非5Hz独立新噪声。
- 118–186以整数iTOW索引替换valid/yaw；GPS week硬锁2408，D57不修复时间；其std仍只保留原行token，HV不重算。对于正式3月BY2闭合，但不是1月XB适配器。
- 189–254严格source pin，HPPOSECEF精确键双差→首点固定NED→冻结A1公式，PVT BOTH_FIXED选有效。没有倾斜补偿，pAcc未传播到新角std。trace=false是角色声明，外层strace另给实际审计。
- 255–303各冻结case逐字节clone、保留非heading/辅助hash；真实/半合成分别记录。v3一方面改主航向为5Hz raw，另一方面HV仍依赖旧status yaw，存在不同有效支撑和相关性，正是协议明示限制，不可叫“heading源完全替换”。

## raw_gnss/rtklib_solution_velocity_parser.py、rtklib_doppler_velocity_provider.py、rtklib_doppler_helper_builder.py

- parser `_float/_int/parse_helper_velocity_csv`：坏数/NaN/Inf替成0或默认std，available标志却可能保留。真实函数NaN velocity被改0反例为P-IN-05。整数Inf可在int转换抛OverflowError；上层没有等价完整失败分类。
- parser `ecef_velocity_to_ned`为标准当地NED旋转，lat/lon用deg；`read_clean_gnss_position_and_times`只取time/LLH不取velocity；`reject_position_solution_as_factor`显式否决位置解输入。此边界有实际代码，不能说它偷偷把PVT速度当RD。
- provider `_approx_position/_gdop_like`、WSL路径/子进程辅助：approx位置只用于方向矩阵，sat数代理`1/sqrt(n−4)`不是几何DOP；sp3/clk参数只写报告，未进入helper命令，不能声称精密星历已启用。
- provider主函数先检查存在性（Path()缺省可能误视目录存在），运行helper后解析；未先以非零returncode禁止旧输出复用，out.mkdir exist_ok且CSV写w，非隔离重跑存在残留风险。有效标志、sat≥5、有限值门遇parser零填会被绕过。
- 142–146（原文件）ECEF速度旋到NED，std_vx/y/z却直接改名std_vn/e/d。若协方差各向同性无影响，非各向同性应`R_n=C R_e C^T`且需要未输出的offdiagonal；因此是条件性科学风险P-IN-06。本轮保留helper ECEF输出，不调用这一路改名。
- helper C源码 `same_epoch/doppler_count/main`：readrnx/sortobs/uniqnav→pntpos的伪距位置用于Doppler线性化→estvel；每个epoch独立sol，SYS_ALL但编译宏决定可用星座，stdout仅速度。只在成功且速度非零时写行，静止真零与失败不会有占位；全输入分母需另从RAWX保留。std来自qv对角、下限0.2m/s。没把PVT速度当Doppler。
- helper builder的source-layout发现、Windows/Linux包装、header与pntpos文本补丁、compile分类/CLI：仅复制到runtime修改，原外部源码不变；如果补丁pattern不命中则返回未改，必须记录实际源身份及pntpos确实调用estvel。`build_dir`参数未用于目录选择；main总返回0，即报告compile失败也能进程exit0，调用者必须读helper_compile_status。

## 本轮复现

`PYTHONPATH=src python3 -m pytest -q -rx tests/paper_rebuild/audit_xbpg/test_provider_findings.py`。7个strict xfail保留已确认旧函数不满足的语义，3个通过是局部反证；exit0表示反例预期成立，不表示旧实现缺陷修好了。正式源文件未编辑。

全文阅读不等于端到端身份已彻底闭合：clean5 provider最初生成链、全部raw Doppler卫星求解/编译宏、全部historical generators尚未完整语义闭合，见覆盖表UNREAD，不用“legacy”隐去。

后续补充：RAW_GNSS_REVIEW.md已闭合raw_gnss全部38文件及当前helper编译宏/调用关系；本段初始“尚未审raw Doppler”不再代表本轮最终覆盖。其它历史生成器仍按覆盖表逐项保留未审。
