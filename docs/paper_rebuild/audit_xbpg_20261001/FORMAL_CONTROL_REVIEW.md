# 正式运行控制、评价恢复与聚合语义审查

源码审查锚点：`e24d4735dd51724560f030275179d7e5efc19763`。范围是 supervisor 指定的 **7 个项目文件、2,525 个物理行**，全部文本及全部函数/关键连续语句组已读并作语义审查。逐文件 SHA/Git blob、调用者、输入输出与动态深度见 `FORMAL_CONTROL_COVERAGE.csv`。自动 AST 只补充 import/身份索引，不产生语义覆盖结论。

本单元没有修改正式源码，没有调用任何控制器 `main`、真实 native/evaluator、历史矩阵、provider、历史归档或删除程序，也未打开旧性能表、原始数据或冻结 NAV。新增测试只用临时合成夹具；测试不构成新的真实数据性能证据。对子依赖只追踪必要契约，未将整个依赖文件自动标为全文语义覆盖。

## 主要结论及证据强度

1. **CTL-01 已确认缺陷：v2.1 原生输出验证不能证明完整窗口。** `runtime.run_one:309–311`、`binary_bridge._one:181–184` 的真实绑定均调用 `clean5_sequence.solver_validation.validate_run_outputs:161–187`。该函数只要求非空、有限、时间单调、落在窗内和 NAV/STD 同行同时间；请求 `[0,100] s`、仅有 `t=10 s` 单行时照常返回 `finite=True, nav_rows=1, nav_time_start=10, nav_time_end=10`。两个 strict-xfail 参数只验证两处同一函数绑定，不是两个独立实验。原生计数闭合也不能证明写出的每个 NAV 行齐全。尚未确认任何旧产物实际截断，不能据此宣布所有旧结果无效。
2. **CTL-02 已确认缺陷：局部 phase freeze 的缓存路径不重验源码。** `controller.phase_freeze:107–110` 读取旧回执就把 `ctx.code_commit` 改为旧值并返回；临时文件与回执 SHA 不同仍被接受。与其不同，主执行 `freeze:127–135` 会逐项复验冻结 source_hashes，故这个反例不能外推为主矩阵 freeze 全失效。影响 `main --operation f01` 的阶段身份门。
3. **CTL-03 已确认缺陷：评价恢复身份门允许 NAV/method/evaluator 身份缺口。** `evaluation._validate_identity:67–77` 仅当双方都含顶层 `nav_sha256` 时比对 NAV，然而 `run_one` 的原始终态通过 `output_seal['KF_GINS_Navresult.nav']` 保存 SHA，没有创建顶层 `nav_sha256`。合成夹具的 sealed NAV=`a…a`、恢复评价 NAV=`b…b` 被接受；`method_id=F03` 对 native F04、缺 evaluator SHA、缺 native NAV SHA 也分别被接受。fresh `one_evaluation` 子依赖会先验证 NAV/STD seal，这是反例的边界；恢复后的 JSON 自身 hash 不能替代评价行与当前 native 的交叉绑定。
4. **CTL-04 已确认缺陷：异常分支混淆适配器调用与评价器子进程调用。** `evaluation._call:149–154` 对任意 Python 异常写 `evaluation_invoked=True`。将被调用适配器替换为“进入后、启动子进程前抛错”的最小夹具，真实 `_call` 返回 `FAILED_EVALUATOR/evaluation_invoked=True`，而实际评价器调用为 0。失败未被抹成成功，但调用计数会被高估。
5. **CTL-05/06 是条件风险：聚合端仍依赖上游严谨性。** `normalize_rows:204–205` 将 `NOT_RUN_ALGORITHM_FAILURE` 的 native 状态改写为 `ALL_YAW_REJECTED`，不检查输入原本是否是 `COMPLETED`；文本 `"nan"/"inf"/"-inf"` 绕过 numeric nonfinite 检查，后续 `_finite` 将其作为不可用而不是失败。原始评价 JSON 通常是数值并经过 `_scientific_gate`；本次没有发现冻结实际行触发。应加状态交叉绑定和数值字段显式类型验证，不能将这些夹具当历史数据错误。
6. **CTL-07 当前正式调用不适用。** v2.1 `runtime.profile_template:66–80` 对序列缺失某个待切换 flag 会返回不含该 flag 的文本而不报错；原函数反例已确认。但 `controller.py:22,263` 实际导入的是 `clean6_canonical_v2.runner.profile_template`，不是本文件同名函数，不能把同名函数错误直接归给正式 controller。
7. **CTL-08/09 是证据与恢复风险。** native 身份和计数异常被作为历史人工裁定的 bookkeeping notes 保留后仍可 `COMPLETED`；旧 base/native/evaluation 回执若存在，一些快捷恢复路径只相信 JSON 而未重新走首次运行的全部门。保持原输出和不重跑是合理边界，但 `COMPLETED` 只说明该运行被接纳，不等于科学身份/计数全部 PASS。下一步应做只读逐行绑定复验，先区分真实差异和校验机制不兼容。

**CTL-10 证据边界**：实际有 parent audit hook 和 solver strace 访问审计，不是所有审计都硬编码；但固定 FLAGS 和 `trace_open_count=0` 不能替代子进程访问记录、安装 hook 之前的访问和 provider 上游信息流审查。

**CTL-11 反证/正确边界**：v3 完整注册表要求 6,468 个唯一 run、每个 case 全部 11 个实际 profile 和精确 seed；v3 native/evaluator batch 对已启动任务等待完成并记录终态再抛错；v2.1 的 finite-pair 比较不以失败值补零，保留 registered、available、paired 分母；缺失统计保留 NA；F03/A02 和 F04/A01 是逻辑别名，不能作为额外 native 实验；`classify_all_yaw_rejected` 需要正面完整处理证据，不仅看非零退出码，stderr 任意前缀不破坏 substring 检查。

## 身份、计数与可评价范围

| 范围 | 控制器实际含义 | 不能据标签推断的内容 |
| --- | --- | --- |
| v2.1 主执行 | 588 个 case/sequence 单元 × 10 个 profile = 5,880 个新 native；v3/v2 两个评价版本 = 11,760 终态槽位 | 终态槽位不等于成功评价器进程数；F01 被复用而非这些新运行的一员 |
| v2.1 正式聚合 | 复用 588 个 F01 native 后，共 6,468 唯一 native 身份；两评价版本共 12,936 行 | 复用行不是新试验；必须绑定原 NAV、配置和评价 SHA |
| v3 registry | CORE 5,951、SEQUENCE 22、ADDENDUM 495；588 单元 × 11 profile | 不表示三篇文献复现完成，也不是新 XBPG 合法输入证明 |
| v3 controller | 4 个身份门 native 已属于矩阵注册表，后续 runtime 复用；最终验 6,468 native/12,936 评价终态 | `PASS_V3_EXECUTION_COMPLETE` 包含明确算法失败槽位，不是全方法精度 PASS |
| 逻辑展示 | F03=A02、F04=A01，经 `v2.logical_rows` 扩行；自然三序列 33 唯一/39 逻辑行 | 不可把 39 行视为 39 独立运行；本审查未给依赖 `logical_rows` 全文件覆盖 |

这些文件不重新定义观测方程。v2.1 F02/F03/F04 等参数来自冻结模板、model 与 provider。`patch_config` 允许校准更新 vrw/abstd，明确固定 F02 yaw std 为 `2.933193 deg`，不更改 `yaw_std_soft_deg=3`；`apply_calibration=True` 时 model 的 vrw/abstd 会覆盖同名 parameter_overrides，调用者应清楚这个优先级。当前正式科学方法仍需与根报告 `METHOD_IDENTITY.csv` 的二进制/实际回显相结合，不能由 runner 源码 HEAD 代替二进制科学身份。

## protocol_v3/controller.py — 327 行

| 行/函数组 | 语义、状态与异常传播 |
| --- | --- |
| 1–18 imports | 线程池只编排；`runtime` 承担真实 native/评价/归档；registry 提供唯一身份；本审查不将这些整个依赖算已审。 |
| 20–25 `_resolve` | 递归替换字典、列表中的 `<KEY>` 路径别名，数值/布尔原样保留。不是 YAML parser，也不验证仍有未解析别名；后续文件门负责。替换顺序依赖 paths 次序，不支持循环解析。 |
| 28–33 `_persist` | 既有 JSON 与新值必须 Python 深相等，差异 hard stop；不存在则 write_json。保证语义值一致，不保证旧 JSON 文本字节一致，也不构成并发事务；调用者通常串行写每个 checkpoint。 |
| 36–61 `freeze_receipt` | 要求本机 HEAD 和固定远程 branch 都等于 freeze；枚举指定目录 tracked Python，加协议、registry、calibrated contract、v3 snapshot；git show 字节与工作区逐个比对，再 SHA。声明 all dependencies 的范围实际是这些 namespace，非全解释器/第三方库。Git 读取没有显式 timeout；网络失败直接抛错，不能报 push 已成功。 |
| 64–105 `Context.__init__` | 读取 ignored local config；scratch 必须独立 ext4、固定 stage 名且不能位于 code/clean/raw；解析协议并建 hash；先 freeze，再加载 BY2/BY2H/BY2O 路径。已保存 registry 需 seal 与 registry source pins，否则从历史身份记录构造。验证 6468；生成 native 和双评价白名单；二进制/评价器固定 SHA；既有 HARD_STOP 禁止继续；创建自有目录、源码 snapshot、preregistration；最后装 parent audit hook。构造异常发生在 main try 之外，未保证产生 CONTROLLER_HARD_STOP 文件，但异常不会被当成功。 |
| 106–120 `snapshot_sources` | 仅复制 freeze 指定小型源码/协议，每文件 hash 前验、既存 byte equality、exclusive `xb`、flush/fsync；不包括 local config/raw/binary。已存在 snapshot 不覆盖。 |
| 122–148 `native_batch` | 最多 64 worker；每 future 关联原 spec。首次异常取消未启动 future；with 退出等待已启动全部结束；将取消/失败/已完成记录与 root 写 HARD_STOP_DRAIN，再重抛首错。不同任务输出顺序不稳定，后续排序；`records` 不是分母，`outcomes` 才包含取消/失败。合成并发夹具实际证实 drain 行为。 |
| 150–162 `_install_guard` | CPython `open` audit hook 记录 parent raw opens；trace_ 前缀/.bag/.fpl 一律拒绝；raw 只放行 gnss1/2-raw.csv。hook 安装前的读取不计入，C/C++/外部子进程需各自 strace；前缀拒绝是路径类别控制，不能识别已经掺入参考值的普通 provider。不可将 `trace_open_count:0` 当全系统信息流证明。 |
| 164–189 `prepare` | 复用/准备 provider registry，读 GATES_2A_2B，两个门必须 PASS；对每一 spec 调 runtime.prepare_config；2c 是发射前字节/211 项 expected echo 门，文案明确失败 native 无 echo 不能称通过。parent audit 中 raw count 来自 hook，trace/bag count 的 0 是 guard 不允许通过的声明，记录文件以 PID 区分。 |
| 191–195 `_native` | 向 runtime 传 sequence context、spec、admission、实际 binary、独占输出根、code freeze、注册 reservation ledger、run 白名单；timeout 使用协议值，缺省 1800 s。timeout 单位为墙钟秒，不是数据时长。 |
| 197–218 `identities` | 先 provider/config；固定挑 3 个 F01 自然/C00 + BY2 F04 共 4；F01 与原 frozen NAV、F04 与 t5a_NAV 做全文件 SHA identity。非 COMPLETED 或 hash mismatch hard stop；比较失败仍保存已有 comparisons。未用 RMSE 选择模型。 |
| 220–248 `_evaluate`/`evaluation_batch` | 每 native 注册 v3/v2 两槽，最多 32 worker；native 算法失败是否跳过实际评价由 runtime 决定。异常后取消未启动、等待已启动、保存所有可得终态再抛错。空 records 会导致 `max_workers=0` ValueError，矩阵 batch 非空满足前提。 |
| 250–269 `postflight` | 将旧/新 provider、binary/evaluator/t5a_NAV 按 `(path,SHA)` 去重重验；重验冻结源码；明确 `raw_payload_rehashed=False`、raw hash gate 在 provider preparation。不是再次全盘 raw 哈希。 |
| 271–313 `matrix` 及内嵌 archive 函数 | 必须 2a–2e PASS；按64个 bounded batch 执行 native→双评价→最多8线程归档。只有全部正常终态后写批记录；native/evaluator 异常另有 drain 回执。最终检查精确终态数、postflight，再写全部记录、echo availability 和状态。实际归档语义属于 runtime，本单元没有执行或全文审查。 |
| 316–327 `main` | 参数限 prepare/identities/matrix；Context 初始化先执行；阶段异常若无 stop 文件则写一次，不自动重试；打印可序列化结果。CLI 本次未调用。 |

## protocol_v3/registry.py — 203 行

| 行/函数组 | 语义、边界与调用关系 |
| --- | --- |
| 1–22 constants/imports | 11 唯一 profile；5 provider 路径与 output/case/run 标签是 transport；INPUT_ROLES 把每个路径映射到实际 echo role，不靠方法名字推断开关。 |
| 25–31 `reference`/`_rows` | reference 使用调用者给 digest 或直接hash；不是自动验证 supplied digest。`_rows` 整读 JSON 的辅助函数，当前文件无调用。实际校验由 `_pinned`/payload hash 进行。 |
| 34–44 `_config_root` | 按 archive_receipt/原 output/retained solver 查 v21 或 v2 config，先找到者返回。文件同名不决定真实性，后续用 record.config_hash 严格验；均缺失则 hard stop。 |
| 47–77 `_scientific_bytes`/`derive_expected_echo` | transport 顶层行剔除，其余连注释、科学记数法文本都必须逐字一致；同时 parse 后键集一致、不同键只能transport。以 donor 实际211项echo为基础，仅替换 run/case与路径；标记 historical target echo 不存在，生成 expected 而非伪造历史 echo。test 证实 `1e-3` 与 `0.001` 即使数学相等也不能互换。 |
| 80–88 `expected_echo` | 先 pin echo；有 witness 时再 pin donor config，读 target bytes交叉推导。独立函数本身未在这里再次 pin target config；prepare_config 上游负责 frozen_config identity，不能脱离调用契约称单函数完整验证。 |
| 91–133 `build_registry` 输入与种子 | 读 local paths；只恢复封存记录/config/bundle，函数不创建历史 Context，不读 NAV内容/raw。source_pins给出时每份record JSON必须SHA对应；CORE F01由v2补齐，ADDENDUM F01由addendum补齐。固定core/addendum协议SHA；case registry及顺序、seed meta匹配；恢复8/14批有显式分支。 |
| 134–169 pin/spec 构造 | 文件 hash cache仅去重；cfg拒符号链接并hash匹配record。domain 按 dataset/run prefix 判定，semi为ADDENDUM或D*；将input provider role+历史hash、reference仅evaluation metadata、窗口秒、base_time、baseline记录入spec。GNSS provider_key含序列/case/GNSS SHA。所有provider含未启用字段也登记，开关由cfg决定。 |
| 170–178 缺 echo donor | 无实际echo只允许相同scientific-byte SHA donor；找不到就hard stop。输出按core、C00、sequence、run排序；不是结果优先排序。 |
| 181–203 `validate_registry` | 6468唯一run，domain5951/22/495；588个(sequence,case)每个恰好11profiles；CORE541和ADD45精确case集合，自然2个精确ID，D系seed_index和260306001+i精确。未比较数值性能，无别名重复计数。依赖被冻结record中的dataset/domain一致性；这不是任意无信任输入schema验证器。 |

## clean6_sensor_v21/controller.py — 505 行

| 行/函数组 | 语义、状态、恢复及风险 |
| --- | --- |
| 1–30 imports | controller的`profile_template`来自v2 runner，而非同目录runtime；run_one是本目录正式执行；归档/资源/检查来自维护依赖，本单元不自动覆盖那些文件。 |
| 33–53 `dump_status`/`note`/`persist` | 状态JSON临时文件+replace；UTC更新时间；append ledger；不可变checkpoint深相等后复用。`dump_status`不是进程锁，当前controller单实例前提重要。 |
| 56–74 `context` | ignored config→reg→v21/v2/addendum协议；独立scratch要求绝对、非symlink、非/mnt、不能等于code/clean。和v3不同，此处只拒根相等，未拒code/clean/raw的子孙目录；实际cleanup安全仍需其依赖独立验证，不据此宣称会删除raw。读取gitHEAD；创建stage/scratch属于调用副作用，本次未调用。 |
| 77–96 `binary_gate`/`effective_contract` | 读取44个NAV/STD byte comparison PASS与old/newbinary实际SHA；在v2协议deepcopy上改protocol、stage、sensor_model_hash、newbinary和guardcommit；主科学参数不是这里网格搜索。旧binary与newbinary哈希不同不被当数值变化，先靠实际bridge。 |
| 99–120 `phase_freeze` | 首次F01专门gate检6个源码/协议的git字节与remotecommit并保存；再次直接返回，CTL-02。本次只对临时cached分支执行，无git/network调用。 |
| 123–159 `freeze` | 主executionfreeze复用时验contract与每个记录sourcehash；首次gitremote一致，trackednamespacePython完整hash，排publication/horizontal/aggregate/pack，拒当前v21 namespace未跟踪执行模块。raw_gnss/frames等不在这个枚举namespace里；它们是否是某阶段真实动态依赖应由实际provider lineage核对，不能因主freeze名称宣称全依赖闭合。 |
| 162–168 `raw_checkpoint` | 已有passed_count22直接复用，否则调用独立22-membercheckpoint；这是同一阶段checkpoint恢复而非每次启动都读raw。不能把返回旧PASS称为本次livehash。 |
| 171–210 `provider_task` | D*case已有bundle时逐providerhash重验；新子进程1数值线程、strace openat、7200s timeout；保存stdout/stderr、forbidden与scope。trace/bag/fpl拒绝按路径规则；nonzero ReproductionGateFailure分类科学门失败，其他ValueError维护停止。原始真实provider内容是否有提前reference信息仍需另审。 |
| 213–225 `bases` | 执行freeze/rawPRE；已有 BASE_PROVIDER_GATES PASS直接读3bundle，没有这里逐providerhash；首次调用provider_task。CTL-09恢复捷径：run_one未在此后通用重hashprovider，不应把JSON里的旧hash当本次实测hash。 |
| 228–249 `build_jobs` | selection给core541×11后过滤协议10profiles；先C00再2自然序列再core退化再addendum45，保证先有3dataset evaluator probes。最终5880唯一run。F01不在v21十profile新运行，后续明确复用。 |
| 252–265 `template_for` | addendum交native_template改transport；BY2返回None让run_onepin原runtime；自然序列pin指定旧模板，缺方法用F04模板和canonicalprofile差异。调用的是v2同名function；两个canonical文本在此read_text，其冻结关系由selection/source冻结链负责。 |
| 267–297 `execute` | 已有P13终态则逐seal文件hash复验；没有终态但目录存在拒重跑；否则run_one一次。保留domain/transport，bookkeeping_notes另ledger。除COMPLETED/ALL_YAW_REJECTED外，native非零/非有限→ScientificStop；其他ValueError要求保留证据修理。source counter/identity校验的失败已被runtime接纳，COMPLETED本身不会使这些notes恢复PASS。 |
| 299–325 `reconcile_receipts` | 只补ledger/receipt间隙；检查run身份、outputseal每项size/hash、scratch内匹配receipt。archive_calls=0；不重压缩。不遍历raw。本次未执行。 |
| 328–342 `archive_records` | 调唯一恢复归档；载入return路径的finalrecord，补v21科学commit/5880分母说明；核对已verified记录与receipt每项seal。排序不挑成功。归档本身不在本单元运行或全审范围。 |
| 345–395 `run_batches` 准备/原生波次 | freeze+binary+base+F01gate；workers按依赖资源策略；256run/批。BATCH_COMPLETE存在跳过；NATIVE_TERMINALS缓存直接json.load，不再次调用execute的逐seal检查。未缓存按受控并发执行，先persist每个完成再collecterrors；等待整波后停，不自动重算失败。CTL-09。 |
| 396–445 `run_batches` 评价/归档 | 缓存EVALUATION_PREARCHIVE直接载入，不再走 `_existing/_scientific_gate`；新评价走wrapper，C00/自然序列诊断sidecars、addendum派生统计，附数据role但不覆盖冻结adapter原row；排序persist；archive/exactcleanup由依赖；BATCH_COMPLETE含完成/算法失败与完整evaluator槽。 |
| 446–474 `run_batches` 闭合 | 处理pending归档直到清空；收集resolvedrun，唯一身份必须等jobs；评价11760且run/version唯一，并逐row关联archive_receipt及native状态→对应COMPLETED/NOT_RUN；写final记录。这里有终态关联门，能抑制CTL-05新运行输入矛盾；仍未复核每条评价NAV SHA。pending无进展的重复条件由dependency维护，无本地次数上限。 |
| 477–505 `main` | freeze/bases/f01/checkpoint/run/status有明确分支；ScientificStop写STOPPED，其他异常写bookkeeping并抛出。context在try外；`--through-batch`无非负validation，负值不会run却可生成负completed_main_runs（边缘输入，未实际触发历史）。CLI均未调用。 |

## clean6_sensor_v21/runtime.py — 318 行

| 行/函数组 | 数值参数与行为 |
| --- | --- |
| 1–36 imports/constants | 18列GNSS计数replay、实际native输出validator、strace open audit与process-group timeout；NUMERICAL_FILES列7类产物，本文件未用其自动验全部；PROFILE_KEYS列method和6开关。 |
| 39–58 `append_sequence_runtime_role` | 验非空单行role；原文本作为prefix，末尾只追加JSON引号role；yaml前后比较确认除role外无semantic变化；保留原科学token。不能因此把native实际parser等同标准YAML。 |
| 61–64 `csv_rows` | csv.DictReader整表载入，供有限debug trace；不是raw流式解析，内存随trace行数增加。 |
| 66–80 `profile_template` | 比canonical full/method差异，仅profile+transport；按顶层key替换原序列行，科学字节未round-trip。但只检查序列既有键，没有验证每个待变flag确实存在；CTL-07实际正式caller不同。 |
| 83–120 `classify_all_yaw_rejected` | yaw开启且expected尝试>0，需update/loop两文件；选yaw_update>0；按start首次IMU后处理直到end复算loop数；loopindex连续且尾time与expected差≤0.00051s；position/RV/yaw计数准确，yaw每次REJECT，加确切错误substring，全部成立才ALGORITHM_FAILURE。不会把timeout/任意abort认成all-yaw；synthetic test去掉末loop后失败，stderr加前缀仍成功。 |
| 123–134 `seal_run` | 递归拒symlink、记录全部文件size/SHA；已有OUTPUT_SEAL拒自动重试；写SEALED_BEFORE_EVALUATION。seal生成失败在run_one总try之外，传播到controller而不是正常return；这是保留未闭合的技术失败。 |
| 138–174 `patch_config` | 先bind_config只改transport，vrw/abstd override白名单；若apply_calibration则model覆盖override；sensor_corrections固定yawstd2.933193deg。逐行只替换命中key，set/allowed differences校验，arw/gbstd/initbastd/corrtime/imu_install不得变。输出完整before/after ledger及frozen hash；per_case_tuning=False是该绑定策略声明，不是行为访问证明。 |
| 176–241 `run_one` 初始化/config | 新root exclusive；sequence_spec或合同的窗口秒/base_time/trace评价pin。outerrecord flags+case信息，D*标semi；旧runtime confighash验，model pin；providerpaths/output替换，非BY2兼容NATIVE_IDENTITY和runtime_role。构造同CAL但无yaw修正的v2reference，要求差异唯一yawstd；窗口与spec完全一致才写cfg。 |
| 242–282 `run_one` 输入与实际执行 | np.loadtxt provider IMU/GNSS，expected_counts对真实时间/validity replay。env限制数值线程1；strace -f openat包resource_command和真实binary；debug最多1,000,000行。run_process_group返回124 timeout/127launchfail并保留stdout/stderr，调用者记录exit。先solver scope audit，再验证实际启用provider open集合；这些是真实访问证据，但不等于上游内容无reference。provider SHA在record直接来自bundle，此函数不逐文件重新hash，依赖provider阶段门。 |
| 283–311 `run_one` 接纳 | nonzero只接受有完整trace支持的all-yaw；0则读取native manifest，identity/counter/aux mismatch或ValueError/KeyError/TypeError存notes继续；记录实际native全部counter；调用输出validator后COMPLETED。CTL-01是输出时轴完整性门缺项，CTL-08是历史人工裁定后“完成”和“验证通过”不同。 |
| 312–318 `run_one` 失败/封存 | except任何常规异常形成FAILED_TECHNICAL及类型消息，不吞成成功；无重试；先写terminal后生成全输出seal，seal本身未含自身；runtime_seconds包括配置/IO/子进程/审核，solver_seconds含strace/resource包裹。两者都不是最坏实时延迟。 |

## clean6_sensor_v21/binary_bridge.py — 271 行

| 行/函数组 | 科学身份与执行边界 |
| --- | --- |
| 1–38 constants | oldbinarySHA、BASE_COMMIT、唯一允许改的configloader源；11profiles、4个数值文件，5providerkeys；GUARD_NEW只允许1.5或2.933193deg，tolerance1e-12。 |
| 41–61 `_git`/`_code_gate` | HEAD必须codecommit；4个控制/配置文件与gitshow一致；cpp相对base差异必须只有loader，且文本必须是唯一oldguard的确切替换。严于“同target名”，但编译器/系统库不是此源差异门。 |
| 64–78 `_cache`/`_pin` | CMakeCache略空/注释、按等号分割去类型；_pin拒symlink/不存在/hash不同，返回size。实际identity-only临时夹具验证错hash/链接被拒。 |
| 81–130 `build_record` | 先codegate。已有freeze仅重验old/newbinary再复用；首次pinold、读取其Release/cache编译器/flags/generator，cmakeconfigure并build指定target并行8；记录stdout/stderr/returncode，失败抛；新oldcache选定项完全一致，pin两binary、冻结实际source与command。subprocess.run build本身无timeout，这属构建卡住时运维风险。相同flags不是相同binary证明，后面bridge才做数值输出验证。 |
| 133–191 `_one` | exclusive输出目录，bind只换5provider和outputpath，freeze科学hash；限制线程、strace真实binary，1800s timeout；先pinexe，再退出/访问/启用input检查；validator+4文件pins成功才COMPLETED。失败写terminal并重抛，未隐藏。CTL-01输出validator只能证明有限窗内片段。 |
| 194–258 `bridge` | 重验gate/binaries；原C00bundle5providers全部hash；11原CAL模板逐method/COMPLETED/C00/yawstd1.5/soft3/hard6/providerhash一致，再pinconfig。每methodold/new各一次，共22native；4文件深度byte compare，共44；不接触reference。首失败就保存comparison/终态停止；结束重验providers和binaries。它证明old科学输入在该C00上的数值不变，不证明新std2.933193在新数据上更优，也不保证全部退化等价。 |
| 261–271 `main` | 仅build-record/bridge操作；输出status及nativecall数。这个counter在调用_one之前+1，准确含尝试槽而非必然成功exec次数。CLI本次未调用。 |

## clean6_sensor_v21/evaluation.py — 297 行

| 行/函数组 | 状态、身份、错误与资源 |
| --- | --- |
| 1–26 imports/constants | 保持评价器数学在`clean6_canonical_v2.evaluation.one_evaluation`，这里只编排/恢复；允许COMPLETED和NOT_RUN_ALGORITHM_FAILURE，后者无精度数字。 |
| 29–42 `_safe_id`/`_key`/`_payload_hash` | run字符串严格白名单，拒.和..防路径穿越；key=(run,version)；canonical JSON不允许NaN计算hash。version由固定v3/v2任务列表决定。 |
| 45–65 `_numeric_nonfinite`/`_scientific_gate` | 递归检查float非有限；检查science终态、允许状态、finite_output=False；skip必须对应all-yaw，completed必须对应nativeCOMPLETED。文本NaN和np.float32不是这个jsonfloat递归的覆盖范围；科学输入默认JSON数值。 |
| 67–85 `_validate_identity`/路径组 | run/version必须相等；dataset/case仅双方有值才比；evaluator SHA允许None，NAV SHA只双方顶层具备才比。CTL-03。terminalpath与originalresultpath固定相对scratch/output，不通过用户值拼绝对路径。 |
| 88–119 `_metadata`/`_persist` | 只附data-role/sensor/domain元数据，不改变数值。非有限float row先变FAILED_EVALUATOR，原repr保留诊断；计算rowSHA封装，已有不同row拒覆盖。已有sameSHA字段并不在此重新计算其row，`_existing`另会复核。 |
| 122–138 `_existing` | 优先读取封存envelope验证内容hash；不存在时找原adapterresult，identity验后封存；两种都再identity+science gate。没有找到返回None不是编造值。恢复身份CTL-03仍可穿过；行自身hash只能防变化，不能证明科学来源一致。 |
| 141–154 `_call` | 已存在invocationdir但无terminal直接拒重跑；否则one_evaluation，异常变显式失败行。CTL-04 `evaluation_invoked`硬编码true将prelaunch error计成child调用；修正应使用子进程启动receipt/显式unknown。 |
| 157–175 `_rss`/`_note`/`_workers` | RSS仅接受正int且非bool；无测量返回0作为内部“不可用”哨兵，对外写None/UNAVAILABLE。资源策略ValueError降为1worker并记账；这不是零RSS测量，也不保证低于内存时一个任务必然安全。 |
| 178–185 `_probe_spec` | 每dataset选注册顺序中第一个已completed native，serial v3→v2共6个正式评价；不是根据RMSE择优。自然firstbatch都存在是controller jobs排序前提。 |
| 188–255 `evaluate_batch` 准备/探针 | 先拒native不合格/重复run-version；恢复已存终态不重复调用；机器状态与pilot已冻结evaluatorhash比对；没有pilot则六个串行，每个先persist再gate；即使RSS部分/全缺仍pilotPASS但measurement_status清楚，最多22资源策略前提另列。 |
| 256–297 `evaluate_batch` 波次 | pending按动态内存/RSS规划；记录池和预算，最多本波线程；每结果先persist再验证，失败收集直到所有已启动任务结束再抛，不重新发射；实际峰值超前次估计记缩容意见，下波重新计算。ordered跟原task keys排序；new_terminal_rows包括算法失败跳过槽，不能叫实际新evaluator进程次数；io_context参数未使用。 |

## clean6_sensor_v21/aggregate.py — 604 行

| 行/函数组 | 数值/分母/来源语义 |
| --- | --- |
| 1–33 imports/constants | 使用canonical/v2/sequence/addendum既有统计函数；本文件只新增身份join及H7–H11层。借用函数不等于重新审完统计库。EXTRA_METRICS含无量纲比、计数、m误差，后续分别逐metric处理，未把单位混合为score。 |
| 36–97 `load_baseline_indices`/`checked` | 只读取指定clean/code JSON/CSV身份索引，拒相对/.. /所有父symlink；按tracked证据中的SHA验完整v2/addendum索引，5973+495native/11946+990evaluation，拒duplicate(dataset,case,method)与row_key。证据CSV自身只算hash、不指定预期，其Git/打包身份须由上游提供。本次未调用，不读取历史性能。 |
| 100–143 `_hash_rows`/`_version`/`row_key`/`_domain`/`_finite`/`_success`/`_status` | explicit v3/v2，row key=(version,dataset,case,method)，缺dataset默认为BY2；域由dataset+D61/D62前缀；数值仅有限、拒bool/NA；成功看evaluation_status，all-yaw优先从native状态。字符串NaN→None是CTL-06边界。 |
| 146–156 `_duration` | 先row后case取有限duration_s，或decode degradation_parameters_json；s为单位；JSON损坏抛错，不默默0；不根据实际误差找窗口。 |
| 159–207 `normalize_rows` | deepcopies，拒重复row_key，规范domain/casefamily/degradation/seed/effectiveprofile；旧计数alias只填空，DOWNWEIGHT+REJECT仅两者有限相加。supplement只允许列举diagnostic且不可替换已有不同值，存来源pin。失败evaluation/数值float非有限停止；CTL-05矛盾native状态被覆盖，CTL-06字符串非有限未停。 |
| 210–219 `_metrics` | 所有row字段union寻找numeric，排duration和执行/复用计数，加冻结metric列表；不按数值好坏选字段；自动发现字段的实际单位来自字段定义，不能跨unit平均。 |
| 222–274 `comparison_tables` | old/new按精确4元keyjoin并拒重复；union保留缺方；按ALL/FAMILY/DEGRADATION/DURATION/CASE分组。每metric仅两侧成功有限的同case配对，mean或median分别对相同paired population计算，delta=new−old，百分比delta/abs(old)，old0则NA。单边available、pairedfinite、algorithmfail、registered都输出；未从失败造delta。registered指传入row union，完整性靠aggregate_all的preregistered coverage门。 |
| 277–301 `failure_comparison` | 同4元join，按version/domain/dataset/method/family/degradation/duration计old/new completed/all-yaw/missing；不声明方向。此helper不单独拒输入duplicate，正式入口normalize_rows已拒；脱离入口用要自己保留前提。 |
| 304–315 `_joint` | 任何INCOMPLETE→INCOMPLETE；非定向H11保持REPORTED_NON_DIRECTIONAL；全SUPPORTED/部分SUPPORTED/全UNCHANGED/否则NOT_SUPPORTED。不能从支持数量推统计显著性。 |
| 318–393 `hypothesis_tables` 及`clean_pair`/`values` | 三自然dataset恰一cleancase、每profile每evaluator；H7新ratio[1,2]且下降才支持，H8downweight+reject下降/相等/增多，H10roll/pitch各自下降；BY2 CLEAN与C00另做alias8组件，不能算独立数据；H9严格9个A2 20s种子，error<threshold_m；H11yawdelta无预设好方向。缺失败→INCOMPLETE。阈值来自旧preregisteredcontract，与新XB探索无关。 |
| 396–402 `_failure_tables` | 汇总native family/degradation/method/status及all-yaw；保留所有record，不只successful。 |
| 405–438 `core_tables` | 通过v2.logical_rows增逻辑alias；逐method/case/degradation/familysummary；调用冻结pairwise bootstrap，recovery仅D58/D60；uncertainty按字段名单列，不把diagonal诊断当NEES；runtime用unique而非logical；metriccoverage和failuretables输出，C00anchor保留实际row。n_boot默认10000 seed20260904，不是独立实验次数。 |
| 441–460 `sequence_tables` | BY2/BY2H/BY2O分开，每dataset调用single-casepairwise，无混合三条时轴；logicalalias保留；段统计只读调用者给的segment_rows，不重读raw/trace，单case置信区间不可得由依赖表明。 |
| 463–480 `_segment_coverage`/`_coverage` | segment期望三个dataset×11method；BY2O五段、其他full，每个冻结metric；拒重复/extra，缺失返回INCOMPLETE和精确missingIDs，不造0。主rowcoverage必须完全等preregistration。 |
| 483–534 `aggregate_all` 输入门 | 输出绝对非symlink、已有结果目录拒覆盖；core541+addendum45case，加2natural；new10profiles×双evaluator与baseline11profiles的精确集合核对；newnative identity核对；复用oldF01明确formal_F01_reused；native只能COMPLETED/all-yaw。注意只验证native/evaluation各自集合及终态枚举，未逐row关联状态/NAV，CTL-05上游承担；n_boot非10000只允许全部synthetic fixture。 |
| 535–574 `aggregate_all` domain输出 | 每evaluator分别写core/sequence；segments缺失写PARTIAL；logical39硬编码建立在完整coverage；addendum交其freeze规则。JSON里的trace_used_online=False/synthetic=False及calls0是该聚合函数的声明/静态I/O边界，不是所有上游进程访问证据。 |
| 575–604 `aggregate_all` 报告/封存 | 生成exact-join旧新比较、失败比较和H7–H11，无epoch metric重算。source_index_hashes对提供的row列表canonical JSON hash，不是原始文件fullhash；summary明确summary_statistics_recomputed=True。最后只seal新输出4个目录，小型封存文件不包含自己；发生中途error会留partial目录，入口拒覆盖，需要独立恢复，不应重写旧结果。本次未运行aggregate_all。 |

## 动态验证与复现

本单元新增 `tests/paper_rebuild/audit_xbpg/test_formal_control_findings.py`，调用的都是仓库原函数/真实import绑定；未用重写算法当 oracle。对子进程调用只做 mock 的测试明确注明 adapter mock，不计 native filter 测试。所有夹具在 pytest tmp_path，没有历史数据角色。

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python3 -m pytest -q \
 tests/paper_rebuild/audit_xbpg/test_formal_control_findings.py \
 tests/paper_rebuild/test_clean6_sensor_v21_evaluation.py \
 tests/paper_rebuild/test_clean6_sensor_v21_aggregate.py --disable-warnings -r xX
```

已实际运行：**25 passed、13 strict xfailed，exit 0**。其中新文件 **7 passed/13 strict xfailed**；既有两文件合计18 passed。另外执行 `test_protocol_v3_runtime.py` 的 `test_witness_rejects_science_even_if_metadata_is_valid`、`test_complete_registry_requires_every_profile_in_every_case`、`test_registry_rejects_same_count_wrong_case_and_wrong_seed`：**3 passed，exit 0**；只构造内存注册条目并调用原身份函数，没有执行6468个算法或该测试文件里的归档/清理测试。两次合计 **28 passed/13 strict xfailed**。

xfail表示针对未改旧源码的预期保护断言确实失败，不能写“全部保护通过/CI全绿”。同一函数参数化只代表边界case，不是独立科学重复实验。小型结果回执：`<AUDIT_ROOT>/data_audit/formal_control_review/TEST_RECEIPT.json`。

需重评的是身份/支持域，而非自动重跑：先在获授权历史身份检查中找有`bookkeeping_notes`、缺顶层NAV SHA恢复行、输出首末时刻/行数不闭合的产物；从已保留seal/配置/native循环证据逐项判定。实际完整轨迹且seal/评价关系闭合者不因本反例需要重跑；有输出截断或方法/NAV绑定错误者应重新确定可评价支撑并保持失败分母，是否重跑留给后续明确科学方案。本轮不重启Canonical-541。

剩余范围明确：v3 runtime/providers/恢复归档全文件、v2.1 finalize/diagnostics/downstream控制和import的canonical/v2统计实现不在这7文件的全审计数内。个别关键callee所读行已在本报告给出，不将其升级为整个文件已审。
