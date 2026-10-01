# raw_gnss 全文件语义审查

本模块 **38/38 个项目文件、5766/5766 物理行已经全文阅读并按函数/关键连续语句组完成语义审查**，不是 AST/枚举覆盖。范围为 `src/legsa_gins/raw_gnss/`；包含嵌在 Python 中的 C helper，包含全部 N5A/N5B/N5C/N5D/N5D1 历史控制、评价和绘图实现。未执行旧实验 runner、未读旧性能结果。本结论仅覆盖此目录；不表示整仓完成，也不表示这些文件每条分支均动态覆盖。

审查源码锚点 `2271d5a38a49aa957bbc3539244ec18ad7fa55ff`，目录相对该提交无本地差异；逐文件 SHA256/Git blob、调用者、深度见 `RAW_GNSS_COVERAGE.csv`。这里只写审查文档和新增反例测试，未改原模块。文件名下的行号均针对该 SHA。

最重要的结论：

- **RG-01/02：原 Python RAWX 多频波长表错误、原 Python Doppler LS 的速度符号错误已经复现。** 当前正式 RD 走 RTKLIB native，未调用这两个实现；不能把二者自动归因为当前正式论文数值错误。当前找到的 Python LS 调用者只有 toy test。历史 DA 的 GPS L1 解算 caller 明确筛 GPS/sig0，L1 波长正确。
- **RG-05/06/13：正式链共享的 helper CSV parser 把 NaN/坏字符串变零；通用 provider 不旋转各轴协方差且允许失败子进程消费残留 CSV。** 当前 formal generation 对中间 STD 重新采用各轴最大值的等方差策略，并要求新的 provider 根，因此前者的轴重命名和后者的残留文件触发条件被收窄；parser 缺陷仍可达，不能声称已经排除。
- **RG-07/08：历史 factor builder 会将不相交时轴按首历元平移；历史 alignment report 将零实际更新和同一条 factor 的重复匹配判为成功。** 当前 formal 路径用 GPST/UTC 元数据换算，明确 `first_epoch_fit_used=false`，未调用旧首历元平移函数。这是反证一条错误的跨版本归因，不是为旧行为辩护。
- **RG-10/11/12/14：历史图和阶段判定存在缺失指标填零、不同时间支撑按行号相减、空必需图集合通过、零更新变体被排除、全局计数冒充逐 spike 已应用、米和度直接求和判收益的问题。** 这些代码需要修正后才可重新使用；本轮不重跑旧矩阵，也不从旧结果构造新性能主张。

## 真实调用链与影响边界

当前清洁链的直接依赖是：

```text
paper_rebuild/formal_generation.py
  ├─ raw_gnss/ubx_raw_binary_rebuilder.py → checksum-valid UBX bytes
  ├─ RTKLIB convbin（外部版本须另锁）→ RINEX obs/nav
  ├─ raw_gnss/rtklib_doppler_helper_builder.py:HELPER_SOURCE
  │     → RTKLIB pntpos/estvel/resdop → ECEF velocity + qv diagonal
  ├─ raw_gnss/rtklib_doppler_velocity_provider.py → run/status wrapper
  └─ raw_gnss/rtklib_solution_velocity_parser.py
        → formal_generation._write_formal_raw_doppler
        → source GPST→UTC-day time + ECEF→NED velocity + isotropic STD
```

`formal_generation.py:21–35, 691–700, 727–748` 是实际 imports/调用；`formal_provider.py:67–70` 和 `clean5_sequence/provider_chain.py:283–286` 登记相同四个共享源文件。`formal_generation.py:306–313` 用日期、GPS day 与 leap seconds 转时轴；`:347–351` 采用 `max(std_x,std_y,std_z,floor)`。通用 provider 的中间 NED STD 不直接作为该正式输出 STD。`hext/heading_provider.py:23`、`clean5_parity/input_audit.py:9`、`clean5_parity_p04/providers.py:11` 也共享 bytes/UBX iterator，因此 RG-04 的诊断计数边界值得保留。

Python `ubx_rawx_parser` 的实际消费者包括 `da_repro/common_epoch_satellite_matcher.py:25–26`、`ambiguity_provider.py:15–16`、`rinex_nav_satpos.py:190–193`。前二者只做匹配/周相位候选，后者 **仅筛 `gnss_id=0,sig_id=0,freq_id=0`** 后在 `:250` 使用波长；该明确 L1 路径不触发 RG-01 的非 L1 错误。`horizontal_literature/shared_raw_backend.py:wavelength_m` 是另外一份实现，不能因同名一并判错。`solve_raw_doppler_velocity` 的仓库文本调用仅 `tests/unit/test_doppler_velocity_ls_boundary.py`，未发现正式 runtime caller。

本目录没有 HPPOSECEF 数值解码器；它只保序转存完整 UBX frame。新增测试证实 signed HP bytes 可逐字节保留。HP cm 整值、signed 0.1 mm 增量、invalidEcef flag 等解析由本轮隔离 `paper_rebuild/audit_xbpg/data_scan.py` 承担，完整实测审查见 `XBPG_DATA_REVIEW.md` 和对应 16 个 parser tests；不把此适配器算作旧 raw_gnss 已实现的功能。旧 SFRBX scanner 也从未解算星历，它的报告明确标 `ephemeris_decode_attempted=false`；可运行 RD 仍需 native convbin/导航覆盖。

## 数学反例与原函数测试

令 `e=(r_s-r_r)/||r_s-r_r||`。直接对几何距离求导得到
`rho_dot=e·(v_s-v_r)`，若钟漂以 m/s 计，则
`-D*lambda=e·v_s-e·v_r+b_r-b_s`。
因此以 `[v_r,b_r]` 为未知量时 H 的前三列应为 `-e`，右端为 `-D*lambda-e·v_s+b_s`（地转项另计）。原 `doppler_velocity_ls.py:97–100` 同时采用 `+e` 和 `rr+e·v_s-b_s`，不是相同未知量下的等价写法。

本轮测试只用真实距离函数 `math.dist` 对静止卫星、移动接收机作 `dt=0.01 s` 中央差分，再把距离导数转成 Doppler 输入原函数，没有重写 LS 作被测实现。真 ECEF `[10,-2,1] m/s`，赤道零经度的真 NED `[1,-2,-10] m/s`；原函数实际输出 `[-0.9999997886472869,2.0000001261973352,9.999999811664054] m/s`，拟合残差 RMS `1.8829126917479496e-7 m/s`。**极小残差不能验证符号正确。** 旧 toy test 用与错误实现相同的 `e·(v_r-v_s)` 造观测，且只断言解存在；`test_raw_doppler_sign_convention.py` 甚至仅 `assert True`，均不能排除此缺陷。原生 RTKLIB 本机源码 `src/pntpos.c:536–552` 使用 `v_s-v_r`、`-D*c/f` 和 `H=-e`；本轮未改它。

波长核对采用生产商 SDK 的 UBX signal ID 映射，而不是把 sigId 误读为频段序号。主要反例：

| GNSS/sigId | 应用载频/MHz | 原函数载频/MHz | 波长相对误差 |
|---|---:|---:|---:|
| GPS 3/4（L2CL/L2CM） | 1227.60 | 1575.42 | −22.0779% |
| GPS 6（L5I） | 1176.45 | 1575.42 | −25.3247% |
| Galileo 6（E5bQ） | 1207.14 | 1575.42 | −23.3766% |
| BDS 2（B2I D1） | 1207.14 | 1561.098 | −22.6737% |
| GLONASS 2, freqId=7（L2OF,k=0） | 1246 | 1602 | −22.2222% |

GPS/QZSS/Galileo/BeiDou/GLONASS 的其它错误/缺失分支见 RG-01；GLONASS L1/L2 应分别使用 `1602+k*.5625` 和 `1246+k*.4375 MHz`，且需合法 channel 范围。生产商映射：[Fixposition SDK UBX protocol definitions](https://raw.githubusercontent.com/fixposition/fixposition-sdk/main/fpsdk_common/include/fpsdk_common/parser/ubx.hpp)；这是 protocol 定义证据，不是对整个 SDK 的审核。

本轮新增 `tests/paper_rebuild/audit_xbpg/test_raw_gnss_findings.py` 直接调用原函数，使用严格 xfail 表示已证实的期待行为失败。最终29个测试文件运行结果为 **48 passed / 25 strict-xfailed / 14环境warnings，进程exit 0**；其中新增文件为3 passed/25 xfailed。14条warning来自matplotlib/pyparsing兼容及未启用3D，不影响本轮2D toy checks。这里的exit 0不是旧实现全绿，25个strict-xfail正是在证明未修复缺陷。额外通过项验证 GPS L1 不受影响、错误 LS 恰好反号、HPPOSECEF frame 字节保留。测试使用合成 fixture；不进入 XBPG 实测表，也不计成独立实验重复次数。完整命令、退出状态、warnings、局部数值证据留在 `<AUDIT_ROOT>/data_audit/raw_gnss_review/{TEST_RECEIPT.json,pytest.log,LS_SIGN_COUNTEREXAMPLE.json}`。

复现新增反例：

```bash
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  python3 -m pytest -q tests/paper_rebuild/audit_xbpg/test_raw_gnss_findings.py -rx
```

## 逐文件、函数/关键语句组说明

以下路径均相对于 `src/legsa_gins/raw_gnss/`。纯 JSON/CSV 写出、argparse CLI 和 import 样板合并说明；每个计算、分支、状态/时间变换单独定位。报告函数没有调用文件访问审计；写出的 `trace_solver_input=false` 等是声明，不能单凭字面证明上游未提前混入参考数据。

### `__init__.py`（5 行）

1–5 为模块说明，无运行状态、函数或 I/O。说明区分 RAWX Doppler 与 PVT/native velocity 合理，但不能替代运行来源锁。

### `raw_doppler_types.py`（104 行）

13–41 定义 c（m/s）及不可变 RawDopplerMeasurement：时间/周、星座/卫星/信号、伪距 m、相位 cycles、Doppler Hz、C/N0、原始质量位、波长 m 和来源；`observed_range_rate_mps` 只在波长 None 时返回 None，实际做 `-Dλ`，不检查 trkStat/数值有效性。44–63 为卫星 ECEF m/m/s 与钟漂 m/s、接收机近似 ECEF 和 rad 经纬度。66–83 的解是 NED m/s、各轴 σ m/s、行数和元数据；没有自动验证单位/协方差。86–104 readiness dataclass 及 `to_dict` 只序列化，禁止源的 false 标记硬编码。RG-02/15。

### `ubx_raw_binary_rebuilder.py`（160 行）

18–33 `parse_bytes_cell` 先安全 literal_eval bytes/list，再 hex 正则回退；不执行 eval，但 list 的 `int(x)&255` 会把越界整数绕回字节，hex 回退可从非严格 hex 文本抽取偶然片段。36–51 `ubx_checksum/is_valid_ubx_frame` 检查 sync、总长度和 Fletcher 校验；正常 frame 算法正确。54–67 `iter_ubx_frames` 顺序找 sync，按 declared length 前进；截断立即停止，可能遗漏损坏帧后仍可恢复的 sync；坏校验不产出原因。70–115 `rebuild_csv_to_ubx` 流式 CSV→valid frames，统计 RAWX/SFRBX 按真实 class/id；`invalid_frame_count` 实为“没有任何 valid frame 且以 sync 开头的 cell 数”，混合好坏 cell 被漏数（RG-04）。缺 data 列已提前创建空 output；零有效 frame 路径删除自身新输出。118–138 双文件汇总，143–160 报告/CLI。正式/外部共享；本轮校验 bytes 输出及计数反例。

### `ubx_raw_message_scanner.py`（153 行）

20–30 `classify_data_format` 只看前缀/前 120 chars；33–46 `_message_name` 依据 CSV name/protocol/info 字符串，未解二进制。49–100 `scan_raw_csv` 全表统计行、标签、前两条元数据样本，`pvt_velocity_available` 仅凭 PVT 标签，不能据此确认合法速度。103–133 `scan_fix_root` 检测两个接收机并用 any 汇总 RAWX/SFRBX 存在性；缺文件单列。136–153 报告/CLI。历史 inventory，不是物理输入资格鉴定。RG-03/15。

### `ubx_rawx_parser.py`（208 行）

25–45 `wavelength_m` 映射错误详上（RG-01）；48–52 `_frame_time` CSV 输入选 arrival Time，UBX 输入选 rcvtow，二者不同时间意义/基准而共用 `time`。55–99 `parse_rawx_frame` 按 UBX RAWX 的 16-byte header、32-byte record 拆 double PR/CP、float D、ID、C/N0 和质量位，字段偏移基本符合结构；声明 numMeas 超过 payload 时 `break` 并返回部分记录，不校验版本、精确 record 长度；独立调用不校验 checksum；locktime 被读后丢弃，leap/recStat 没传出。102–109 UBX 读整个文件再 iter；112–129 CSV 由 name 预筛，标签错误可漏真实 RAWX。132–136 以 round(tow,3) 为键，忽略 week/receiver并可合并时间近邻；139–162 有效 Doppler 仅有限非零，不能等同信号可用于估计。165–190 JSONL 导出及双接收机拼接；193–208 CLI。RG-03。当前实际数值消费者的 L1 限制详调用链。

### `ubx_sfrbx_scanner.py`（88 行）

22–50 `scan_sfrbx_csv` 先按 CSV label 筛 SFRBX，checksum iterator 后直接把 payload 前两字节当 gnssId/svId，仅要求长度≥8；没有验证 class/id=02/13、numWords、版本。一个贴 SFRBX 标签的合法 PVT frame 被错误统计（RG-03 原函数复现）。53–68 双文件汇总星座计数，仅 inventory；71–88 写报告/CLI。不提供任何卫星状态或星历有效区间；“可让 convbin decode”是建议，不是完成证据。

### `doppler_velocity_ls.py`（133 行）

20–22 provider protocol 取 satellite state；25–52 手写矩阵乘、向量乘与 Gauss-Jordan inverse：zip 静默截维，pivot 绝对 1e-12，无有限性/条件数检测。55–62 ECEF→NED 正交矩阵使用 rad；65–72 LOS 是 receiver→satellite，零距离抛异常，NaN norm 未拦。75–103 以 rr 有限非零、C/N0≥20、有 sat state 过滤，未用 trkStat/doStdev/state time；`min_sat` 实际数 signal rows，可重复同卫星；错误符号见 RG-02。104–119 weighted normal equations 以 max(1,CNO/30) 为 weight；残差 RMS 却未同样加权，除以 n−4；对角乘 RMS² 再至少 1e−6 m²。所谓保守 NED σ=最大 ECEF 轴 σ 不是含相关项协方差的方向上界。120–133 输出首记录 time、NED解、row count、钟漂。无当前 runtime caller；动态已证明符号错误，未以该 Python 解替代 native RD。

### `raw_doppler_epoch_exporter.py`（48 行）

14–48 `write_velocity_factors` 将所有 solution 格式化到 9 位小数，输出 time、NED velocity/σ、sat_count/gdop/status；不筛有限性、不核 week/坐标、不保留全部 metadata。不能替代 provider gate，只有调用方已校验解时才成立。历史 N5A 导出器，未发现正式直接依赖。

### `ephemeris_discovery.py`（157 行）

16–41 固定 BY2 日期/通用组织名/扩展名；44–66 分类与候选只看文件名，`.rnx` 不读 header，压缩 RINEX 分类不完整。69–86 `_score` 对 broadcast/sp3/clk 单因 role 加分；89–136 `discover_ephemeris` 却把 score>0 命名为 `by2_date_match`，因此任意其他日期 `.nav` 也为 true（RG-09）。best 优先该伪 date 标志，未检查内容、TOE/TOC、星座、信号、覆盖/年龄，available 只需文件名候选存在。139–157 JSON/CLI 与环境根；仅历史 discovery，不是当前 pinned formal 导航选择。

### `rtklib_command_runner.py`（93 行）

16–31 `CommandResult` 保存命令、返回码及 stdout/stderr尾；34–40 `.exe` 只影响 invocation label。43–82 `run_command` 用 argv 不经 shell，timeout/OSError 转 127；Windows .exe 首次异常后 cmd.exe /C 再试，首个 timeout 也会触发重试，可能重复外部副作用，超时类别被合并为127。85–93 创建派生目录和解析 env root。无 timeout 输出残片保留，无 process identity hash；上层仍须判断返回码与新鲜产物。

### `rtklib_discovery.py`（119 行）

17–31 名字/优先相对路径表；34–44 `_find_first` 首个符合名称文件（不验证可执行位/版本）；47–57 `_find_sources` 不同子树的同名源文件可拼成证据。60–99 help 返回0/1/2即 can_run，任一 convbin 或 rnx2rtkp存在即可 provider_available，不证明同时具备转换与解算链；source_tree_found 用 any 而非全部依赖。102–119 写报告/CLI。仅定位线索，版本身份需要独立 hash/commit。RG-09/15。

### `rtklib_doppler_provider.py`（194 行）

22–36 Windows/WSL路径兼容；39–54 通过函数名子串查源码，只证明文本存在。57–62 fallback broadcast→SP3，但 SP3 不等于完整钟差/导航支持。65–151 `attempt_rtklib_provider` 从发现报告选择 convbin/rnx2rtkp，以 `-r ubx -od -os -oi -ot` 生成 obs/nav，120s限制；artifact存在且非空即可 conversion成功，即使返回码非0或旧文件残留。定位诊断不作为 LegSA输入。153–188 无论上述探测如何，最终 `satellite_state_provider_status=provider_missing_sat_state_export`，activation=false，这个边界是有效的。191–194写报告。不要把本模块称为已完成卫星状态 provider。RG-09/13/15。

### `rtklib_doppler_helper_builder.py`（368 行）

20–35 依赖12个RTKLIB C/header名字。38–120 `HELPER_SOURCE` 是实际编译的项目 C代码：same_epoch用1ns；读obs/nav、sortobs/uniqnav，PMODE_SINGLE/SYS_ALL，按同历元调用pntpos；`doppler_count`数“至少一个通道非零 D 的观测记录”，并非 estvel 真正参与卫星数。105–106以|v|总和>1e−9代替速度解算成功标志，精确静止会被抛弃；失败历元不输出占位，分母只能回到 raw审计。107–111 qv前三个轴每轴floor .04 m²，输出σ、GPST tow精度1ms，省略week和qv交叉项；time跨周需外层封口。return2–6明确不同I/O/无输出失败；末尾打印原始obs/nav计数，未free obs/nav但process退出回收。RG-06/16。

123–166 `_tail/_find_source_dir/_read/discover_rtklib_source_layout` 以首个路径、名字与子串找依赖，无版本锁。169–188 `_patch_header/_patch_pntpos` 仅改复制源的确切字符串，后者可能使注释掉的 estvel_muti启用；没命中不会必然阻塞，应检查报告的patch布尔。191–204编译stderr启发式分类；207–264 WSL path/compiler探测与native→WSL fallback，compile本身无timeout。267–353复制deps、拼C source、gcc -O2链接，build_dir仅报告，成功需exit0+exe存在，未绑定来源SHA。356–368 CLI无论compile状态都exit0。当前 formal另有pinned build与hash；本轮root也实际fresh build及运行helper，版本关系见METHOD_IDENTITY。

### `rtklib_solution_velocity_parser.py`（134 行）

15–29 factor schema；32–44 `_float/_int` 分别将坏/非有限浮点回退为0或给定值、将整数坏串回退0，int(inf)的OverflowError未捕获。47–76 `parse_helper_velocity_csv` 对缺失时间/速度填0、缺σ填.2、负σclamp1e−6，即使status=available也接受（RG-05，父审查 P-IN-05 有严格xfail）。79–92 ECEF→NED输入经纬度degrees，矩阵正确。95–118读取clean GNSS首个位置与所有有限时间，整文件读入，位置坏值也变0，无地理范围检查。121–134禁止PVT/native当RD的说明报告只是固定标签，没有验证文件来源。当前formal直接调用parser，不能因后续finitecheck声称防住已被变0的NaN。

### `rtklib_doppler_velocity_provider.py`（205 行）

21–48近似位置字典/clean文件读取与count-only `gdop_like=sqrt(1/(n−4))`，不是几何DOP。51–79 `_wsl_path/_run_helper` 处理Windows兼容，180s子进程timeout异常直接上抛。82–137路径空值变Path('.')且只exists检查，目录可误过文件gate；失败原因依赖helper后续发现。139–169运行helper后不检查returncode就读CSV；有限性过滤晚于parser的缺失→0回退；velocity正确ECEF→NED而STD直接x→n,y→e,z→d（RG-06）。170–205只要有效行就写provider、activation=true、helper_status=success，即使helper exit3（RG-13反例）；没有清理/隔离旧helper CSV。SP3/CLK参数仅回显，不送到C程序。正式caller新provider-root减少残留触发但不修复此函数contract；STD被formal另重写。

### `raw_doppler_velocity_factor_builder.py`（118 行）

17–39 `_float/_read_rows/_time_range/_overlaps` 把坏速度转0，坏时间用于range时转NaN；时间窗口仅min/max±1s。42–69拒绝三个明确禁止source字符串，其它字符串不验证；status必须available、σ正，velocity NaN先变0后通过，保留原CSV文本写出又使下游可能重新失败。71–90无时交时取provider首时刻−clean首时刻，自动对每行source_epoch_time减偏移；两份无共同钟据的记录被“对齐”（RG-07）。92–118无blocker则写factor，只检查rangeoverlap而非逐历元；sat_count转int可因坏文本抛出；报告中的not_source仅根据传入label。当前formal不调用它；原函数反例1000/1001→10/11s被activation=true。

### `raw_doppler_readiness.py`（52 行）

11–30 `decide_readiness` 聚合RAWX/星历/RTKLIB/provider状态/生成factor等布尔，任一blocker则关闭；31–45按缺失类型选建议阶段，provider类型优先于rawx/eph。46–52返回readiness结构。逻辑本身没有假造速度，但其输入的discovery/scanner标志未含完整物理资格，故no blockers不等于端到端科学通过。RG-09/15。

### `raw_doppler_factor_report.py`（20 行）

13–20 JSON写出（建父目录、sort_keys）和读入。读入未验证top-level dict/schema/finite，异常直接抛给上层；写json允许NaN默认，因此JSON文件存在不代表严格JSON或科学数值合格。没有任何solver执行。

### `raw_doppler_factor_diagnostics.py`（118 行）

15–50 helper读CSV、finite过滤、nearest-rank分位及min/p50/p95/max；`_rows`将missing视为空表。53–97统计原顺序time gaps、卫星行数、各轴速度/σ、5m/s邻接跳跃和σ>5，未按dt归一/区分缺口与加速度，provider_status=available就是valid count。NaN在spike计算时变0可能造成假跳；空表的`all(...)`令covariance_available=true（RG-11）。100–112 update/reject count比率，零尝试返回0而非NA；matched_epoch_count=update_count，unmatched=valid−updates混淆接受与匹配/拒绝。115–118写报告。诊断统计不能作为独立truth误差或完整更新证明。

### `raw_doppler_time_alignment.py`（101 行）

15–43 helper解析首列时间、CSV factor时间、abs-dt分位。46–65空输入明确notok；66–78用GNSS/IMU极值交集筛GNSS，排序factor但不排序gnss；单调指针最近邻可选未来、可重复同factor，不是实际消费表。79–95 `matched==len(gnss_overlap) && (actual==0 || actual==matched)` 将零更新当OK；matched可超过factor数，unmatched再max0掩盖；建议tolerance=max(old,p95*1.2)是数据后验扩大而不是固定clock证据（RG-08）。98–101写报告。当前正式调度须看C++，该report不能代替它。

### `raw_doppler_velocity_comparison.py`（110 行）

16–45 `_f/_rmse/_p95/_corr`有限样本统计与Pearson相关，常量向量相关返回None；48–66读factor与15列GNSS的NED列7/8/9，只作对照。68–85按原顺序单调最近邻，容差默认0.55s、无唯一性/未来限制；未先滤time/velocity有效性。86–103 `possible_copy` 用RMSE或0判断，若全NaN但有时间配对，None回退0会误报copy；`velocity_diff_p95`拼水平范数与D轴误差，不是3D范数的P95。not-PVT/not-15col标志硬编码，只能表示角色约定。107–110报告。RV和RD共接收机，相关接近1既不证明copy，也不证明统计独立。

### `raw_doppler_activation_evaluator.py`（163 行）

16–33 config/GNSS按优先名字或首个排序文件发现，未hash绑定。36–51逐行文本追加enable/path/τ=.08/minsat5/residualgate3/Rscale1，保留旧文本但会产生重复键；有效值取决真实parser末值策略。54–70 `_run_demo` timeout240，之后无论exit值读同目录manifest，残留有风险；timeout/OSError上抛不写终态。73–84摘要缺失计数默认0。87–132 trial检查factor gate/config/exe，factor path为空时未添加missing blocker；baseline失败仍跑raw，最终检查返回码、enabled和updates>0。133–163 report仅诊断，差值为update数差，无性能证据。RG-13/15。未运行此历史runner。

### `raw_doppler_n5b_decision.py`（51 行）

12–21合并四份blocker；22–40优先trial.completed_enabled且updates>0，可在其它report仍有blocker时也归为completed；其余按compile/nooutput/covariance/time分类。41–51completed时blocking_issue清空但blocker_reasons保留，易给上层矛盾印象。只能视为阶段标签聚合，不能代替子进程与产物identity gate。RG-11/15。

### `raw_doppler_ablation_matrix.py`（65 行）

14–22定义七项开关：RV on/off、RD on/off、Rscale1/.5/2/5。25–59可关掉三项Rscreen；只将baseline+raw r1标proposed_candidate，其余diagnostic，返回路径/开关，不执行/调参。62–65写matrix。矩阵是历史规则，不能用于当前方法别名或新20次执行分母；未启动。

### `raw_doppler_ablation_evaluator.py`（266 行）

22–32 JSON helpers；35–69 config文本追加消融开关/τ/minsat/gate/Rscale，bool('false')在调用者传字符串时会变true，默认需要typed bool；重复键同上。72–97 child timeout300，不清已有manifest；build_dir被del。100–117 missing metrics显式None，这个边界合理。120–161 `evaluate_variant` 忽略trace_reference参数、只用dual/final_v23 NAV作parity参考，存在EVAL_NAV就填returncode0，实际退出码须外层覆盖；不看终止时长/finite support就可评价残留文件。164–225 `_delta/_score/compare_variants` 按method id聚合覆盖重复id，用各自summary做差，未共同时间支撑；`_score`直接H m+Up m+Yaw deg，threshold .05混单位，收益/独立约束判定不具有单位不变性（RG-14）；gross limits分别有单位但未消除混合总分。228–252逐个run后仍评价失败产物，最后才写总ledger，timeout会中断未写全失败分母。255–266 starttime/endtime文本float解析不支持注释。旧parity不能更名独立精度。

### `raw_doppler_ablation_decision.py`（80 行）

13–19再次H+Up+Yaw求和；22–47按updates、alignment、copy-suspect、degrade给建议。49–50 iso_score≤0且updates>0即称`independent_velocity_constraint`，性能相似不能证明噪声独立/新信息；factor_diag只回显count。51–80输出边界标志与JSON。RG-14/15。数值变好不能抹去RV/RD共享raw硬件的相关项。

### `raw_doppler_stress_matrix.py`（263 行）

17–35定义12required+2optional；38–50返回第一finitefactor时间（非最小时间），无数据退0。53–94 `_row`统一typed开关、seed20260510、派生路径及diagnostic标记。97–239构造RV disabled/std×5/前30soutage/噪声.5m/s及R2/R5；optional实际上总是加入。`position_yaw_only`与`receiver_velocity_disabled_no_raw`是不同标签实现相同关闭RV语义，需要native开关行为核实而不能当独立实验；240–263校验名单、写matrix。没有读取reference择优；本轮不生成/运行这些故障。RG-14用于独立样本与计数限制。

### `raw_doppler_stress_runner.py`（206 行）

18–32 JSON异常→{}及写出；35–75追加stress参数/诊断标签/RD设置，不修改base文本，但不保证所有键接入真实parser。78–109调用debug update timeline、timeout360，读取同目录manifest，不绑定本次run；112–156委托旧parityevaluator，并明确absolute trace评价missing，图表若把parity当absolute则违背其字段。159–197逐项执行、评价、末尾写runs/summaries，同样中途异常缺终态；200–206可读取既有N5C summary而无hash锁。RG-13/15；只读源码，未复用旧产物。

### `raw_doppler_stress_evaluator.py`（116 行）

16–22列五对（含isolation/disabled语义重复）；25–39summary优先或parityfallback、指标差，数字NaN视isinstance真。42–58分别用H/Up .2m、yaw .5deg判退化，用.02m/.05deg判有帮助，无finite检查时全NaN会落neutral。61–99拼pairs，缺任一metric不等同失败：仅全部None才evidence_missing；完成定义没有检查native退出/覆盖分母。stress_help_count只取receiver_velocity前缀，isolation另拿一次推断independent，不能证明信息独立。100–116边界标签/写出。RG-14/15。

### `raw_doppler_n5d_decision.py`（73 行）

14–17clean gross/degrades；20–43按source/time false、clean退化、degrade≥3、help≥2或≥1等决定建议阶段。没有强制visual_stress_candidate_passed或全部mandatory存在为前提；None缺失与False不同，可在缺source/time证据时靠help计数ready。45–73序列化未实现模块与主张false。RG-11/14/15；completed/ready不是完整论文复现。

### `raw_doppler_n5d1_decision.py`（77 行）

14–43必需coverage失败→notready、spike缺失→partial、action风险→spike caveat、否则ready；semantics_report仅在truthy时检查，缺报告不阻止ready，同时最终flagfalse，存在矛盾。44–77写coverage/spike/去重counts与边界标签。应要求明确存在且通过各个required gate，不能让上游空表vacuous pass穿透。RG-11。

### `raw_doppler_visual_loader.py`（236 行）

23–53安全数值转换（NaN保留）、missing/invalidJSON→{}、CSV全读。56–99装factor/receiver NED速度/STD数列；receiver只读15列7–9，无单位/时标检测。102–120依固定名或首个递归候选找文件，未身份锁。123–164原顺序最近邻τ=.55，可未来/复用，无status gate；3σnorm=`3sqrt(sum σ²)`是raw自身散布，不是raw−receiver差的置信包络，缺共享相关和receiver covariance。167–192根据output_dir/manifest_path找到EVAL_NAV，用旧dual NAV+5ms alignment计算parityerror；195–236聚合report/default旧报告与硬编码source flags。RG-08/10/15。该collector实际可能读reference，但只在评价函数路径；flag无法证明provider先前没用参考。

### `raw_doppler_visual_plots.py`（369 行）

15–48固定32图名；51–135 Agg backend/axes/line/hist/bar/scatter/text写PNG；line `x[:len(y)]`、scatter同样截头而非按finite mask成对删点。138–151每个方法独立以自身首时刻置0，y单独过滤非finite，导致中间缺值后时间错位且跨gap连线（RG-10）。154–190summary/pair查找，missing delta/metric变0（RG-10）；193–212写声明panel。215–247 clean两个结果直接按索引相减，不取共同time；248–258 NED和cross-source一致性曲线正确区别数值角色但hist名bias并不等于真值bias。259–273把variant更新总数画成名为timeline的bar，用raw−RV差作residual proxy，用raw satcount前缀配proxy行，未time join。275–304stress条图混合m和deg且丢missing语义。306–312 raw σ包络标题误称velocity error，summary H/Up/Yaw/Roll/Pitch混同轴；后来的semantics模块仅改部分图。313–369文件存在性/计数与JSON/report输出，无像素检查。历史图不得支持当前性能；本轮真实图另用隔离审查工具。

### `raw_doppler_visual_sanity.py`（116 行）

15–24递归finite检查允许None/str（未知值不阻塞）；27–29只检查finite time非降，重复允许。32–39enabled variants里 `count>0` 的才比较，零更新变体漏掉（RG-11反例）。42–49clean摘要missing默认为no gross divergence。52–109source/time一些默认True，reject阈值只看各方法最大计数，fig_count≥25代替图数据；组合all可能仍在部分证据缺失下pass。112–116报告。只算machine sanity，不能声称raster或science validation。

### `raw_doppler_plot_data_coverage.py`（204 行）

16–47必需图集合和coverage结构；50–80finite/x-y分别过滤再截min长度，忽略成对有效位置。83–156检查source series行数、range、fig存在、指定pair、minrows/minseries等，clean预设最少200s；同label覆盖row_counts可能漏series，传入`require_file_exists=false`可绕过文件存在。159–188仅检查传入mandatory集合，空list使all=true，直接mandatory_coverage_passed=true（RG-11），且没有检查预期完整图清单是否被提供；191–204report extra任意覆盖同名gate。应将expected figures与source时支撑作为输入契约，而非图张数。

### `raw_doppler_clean_ablation_plot_fix.py`（327 行）

26–94定义6repaired图及Agg/line helper，`_values`过滤非finite而 `_rel_time`完整时间保留，仍存在错位。97–124按N5C优先定位同名EVAL_NAV，没有比较身份，存在多个候选选first。127–172对evaluation-only dual NAV匹配并生成parity errors，缺文件明确missing；不是在线修正。175–216构造curve source和diff：各method起点自行置零，diff按min(length)/rowindex，缺失历元即可配错时间（RG-10反例t=[0,1,2] vs[0,2]输出y=[9,17]而共同支撑应[9,27]）。219–317要求两组非空再输出6图、minrows1000/minspan200，机械数量并非完整窗口。320–327序列化dataclass。虽然名字叫fix，也未闭合时间配对/缺失语义。

### `raw_doppler_plot_semantics_audit.py`（245 行）

17–31新名字、短标签、disabled→isolation显式语义alias；34–74Agg/axes/finite/relativeTime/_values工具，missing metric仍回退0（RG-10）。77–96按semantic_key去重，保留先出现项，未以native开关证据验证alias。99–153将raw−receiver改名consistency并注明receiver不是truth，这是合理修正，但raw3σ并非差的统计置信限且时间mask问题未修复。154–215画去重yawdelta与映射文本panel，缺metrics用0使图“非空”；217–245无论coverage是否通过都置semantics_fixed=true再写report。区分修标签、machinecoverage和像素科学复核。

### `raw_doppler_spike_audit.py`（221 行）

20–57finite/nearest-rank/norm/转换、全表min查最近receiver（每raw扫全表，O(NM)，无tolerance）、首历元jump置0。60–125raw顺序遍历计算相邻速度跳、nearest跨源差，residual按round(time,6)字典去重覆盖；字段NaN会在sat int conversion抛异常。127–178jump>5为spike、cross-source差>max(5,p99)另列consistencyoutlier；time差>.08仅建议，不剔除/校正。142–149全局updates>0就把每个spike `applied=true`；全局reject0能排除全局拒绝但不能证明某个factor被消费，updates和reject均>0时更不该分配（RG-12）。180–215用maxjump>15或diff>10称impact high，缺实际EKF误差/逐epochtrace，只能叫输入risk；没有删除spike或调参数，这一边界有效。218–221写report。运行时间瓶颈仅静态复杂度证据，本轮未为此历史函数声称实测实时性。

## 修正建议与仍未验证项

修复必须独立候选，不能覆盖正式冻结输出。优先：严格 helper CSV schema/finite拒收并保留坏行位置；检查本次child exit/独立新输出目录；导出完整qv和native速度成功标志/实际Doppler参与卫星；据完整协方差作NED旋转；RAWX信号表按官方ID版本化；LS按物理距离导数修正并以独立oracle回归；所有时轴必须具week/epoch/source标签，禁止无证据first-epoch offset；图与统计必须做成对time join和共同支撑、保留NA和断线、把coverage与失败纳入分母。

`max(diag(P)) I` 仅在忽略ECEF交叉项的假设下为旋转后对角方差的上界，不是对真实相关矩阵的普适PSD上界。例如 `P=[[1,.9,0],[.9,1,0],[0,0,1]]` 在45°方向方差1.9而maxdiag=1。这里应标“等方差近似+floor”，不得据注释直接宣称保守。0.2m/s floor在具体数据是否盖住该误差，本轮未做调参/优化论证。

需重评的是**采用上述旧函数产生的对应诊断/图/阶段结论**，先按hash锁追到真实产物再决定重跑；不能按目录名批量宣判旧实验无效。当前formal由native RTKLIB产生Doppler而避开RG-01/02/07，仍需检查共享CSVparser、qv丢相关/metadata、失败状态和实际原生输出。未在本模块审查中执行完整C++滤波器；其21维数学、更新、复位、调度由 `NATIVE_REVIEW.md` 等主审查负责。未审核整个第三方RTKLIB、编译器或设备固件，也没有完成三篇文献复现。

数据侧再次明确：XBPG F01目前仅因该录制的Go2采集时钟关系、安装与APC杆臂未获证据闭合，**不以双fixed=0阻塞F01**。双fixed=0与短基线不稳定额外限制需要合法heading的F02/F03/A04/F04。raw_gnss上述历史缺陷不成为禁止合法receiver-only新探索的理由；本轮实际运行状态仍以已冻结protocol及RUNS/METRICS为准。
