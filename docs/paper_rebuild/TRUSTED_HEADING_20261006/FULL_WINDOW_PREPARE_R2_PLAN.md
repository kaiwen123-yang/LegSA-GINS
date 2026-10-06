# FULL_WINDOW_PREPARE R2：保留早期无 NAV 历元

本文件是工程恢复登记，科学窗口、信号/弧/方差/anchor 参数不变。执行须 root 提交 R2 后启动；本次修改期间真实 converter、prepare、整数搜索、导航、评价、参考读取均为 0。原 ATTEMPT01 目录与其中所有字节保持，不覆盖、不自动重试。

## ATTEMPT01 的确定事实与边界

原登记提交 8e35b51dfc9dfa1d59454551406d97c744a73838；原 runner SHA 506b1ed586400adcb8db393ecd89971f119e86a9d1b15515ea3a989e78861b90。根控制器 FULL_WINDOW_PREPARE_DRIVER_ATTEMPT01 已结束，输入步骤 terminal 为 FULL_WINDOW_PREPARE_ATTEMPT01/FAILED.json。精确调用：1 次 converter（BY2 cutoff66 RX1），退出码 0，0.007721649 s；0 prepare、0 integer search、0 native navigation、0 evaluator。外层在 require(nav.is_file()) 处以 converter produced no NAV 停止，不能归类为导航性能失败。

既存证据均在 <TRUSTED_HEADING_SCRATCH>/FULL_WINDOW_PREPARE_ATTEMPT01/BY2/PREFIX_0066.000：

- CONVERT_RX1/INVOCATION.json、stdout.log、stderr.log：stdout 空，stderr 最终 O=51，没有 N；正常成功退出。
- gnss1_rawx_e1b.ubx：112248 bytes，SHA 29be55a8d36fb49da857f4e86a40d4bfd7e6445c4f14e444316c366cc5161de9。只读派生 payload 元数据解析共 237 帧，51 RAWX + 186 SFRBX，所有 UBX checksum 通过；RAWX 首末 55.99799990653992 / 65.99799990653992 s。未再读取原始完整 UBX。
- GPS L1 有 G03/G04/G06/G09/G11/G14/G17/G19/G22，各仅 1 条 subframe 3，无 subframe 1/2。另外 GPS L2C 12 条是当前 decode_nav 明确跳过的 CNAV。QZSS 亦仅子帧 3 与 CNAV。依据官方 RTKLIB src/rcv/ublox.c:751–781 的十字去 parity 后 getbitu(buff,43,3)；同处 CNAV preamble 分支返回 0。此证明该前缀不足以产生现存 GPS L1 SPP 所需完整广播星历。
- Galileo E1 的 E02/E10/E11/E12/E36 都无完整 word 1–5；保存 PAGE_QUALIFICATION.json 的所有完整事件 included_by_cutoff=false，最早 E11/E10/E02 的完整事件 available_by_rawx_relative_s=99.19799995422363。全文件未来资格统计不会成为早期星历输入。
- 官方 RTKLIB src/convrnx.c:1328–1330 明确删除 n[i]<=0 的空输出；1340 返回非中断成功。故“退出成功但没有 NAV 文件”是允许的零记录输出语义，不必是程序崩溃或写盘失败。

严格边界：确认 converter 本次未输出任何 NAV，以及 GPS/E1 此前缀的完整页不足；没有逐一诊断 BeiDou、GLONASS、SBAS 的解码拒绝原因，不能把 GPS/Galileo 页缺失称为所有星座的唯一原因。RX2 尚未转换；不能据 RX1 推断 RX2 也必为空。没有以参考或未来完整 NAV 验证/补齐这些缺失。

## 最小修正

real_trial.py 新增默认关闭的 --allow-empty-navigation。正常非空 legacy manifest/CheckedRtklibProvider 路径保留。仅 opt-in 且 manifest 明确 navigation_availability=NO_NAV_OUTPUT_AT_PREFIX、navigation=[]、RX1/RX2 的 conversion_outcomes 均为整数 returncode=0 且 navigation_output_present=false，才接受显式空 snapshot。来源 lineage、manifest SHA、cutoff 和严格递增时间检查照旧。

空 snapshot 使用 UnavailableBroadcastProvider：不加载原生库、不伪造 RINEX/卫星状态，state() 抛 RawBackendError 并记原因。原 SPP 路径因此无解，原 anchor 逻辑保留失败/不可用行；不裁窗、不延后起点、不补未来星历。到后续固定 cutoff 才尝试该 snapshot；即便后续 snapshot 为空也不静默回退旧 provider。原先有 anchor 的普通最长 hold 工作规则未改，但空 provider 无法生成合法当前卫星几何。

producer 完成两个 RX 后，以实际存在的 NAV 为正常输入；一个 RX 无输出、另一个有 NAV 时只用存在者并保留两个结果。只有成功转换且路径不存在视为可记录 absence；非零退出、超时、非普通文件、存在但零记录的 NAV 仍停止。

## R2 精确预算与复用

R2 机器计划为 FULL_WINDOW_PREPARE_R2_PLAN.json，入口仍 full_window_prepare.py（新源身份，与原执行不同）。49 prefixes、37 新 prefix/12 旧 NAV prefix、三个完整窗和全部三个 family 与原 PLAN 相同。

**73 次新 converter + 1 次原成功 conversion outcome 复用 + 3 prepare。** 复用对象是 66/RX1 的无 NAV 结果，不是旧 NAV。R2 对原 INVOCATION/日志/PAGE_QUALIFICATION/derived payload/OBS/登记/失败记录逐文件核 SHA/大小，核原转换成功、原 NAV 仍缺失及 cutoff，生成新 REUSED_RX1_CONVERSION.json 引用旧证据；不扫描或重新转换该接收机前缀，不复制、更改原 attempt。66/RX2 仍是一次新调用。源原始 UBX 身份核验、其余前缀生产和新模型完整 seal 规则保持。

R2 输出目录为 <TRUSTED_HEADING_SCRATCH>/FULL_WINDOW_PREPARE_ATTEMPT02，必须不存在。任何失败仍保留停止；没有自动 R3。命令在原计划入口基础上改为新 output，并增加：
    
    --prior-attempt "$SCRATCH_ROOT/TRUSTED_HEADING_20261006/FULL_WINDOW_PREPARE_ATTEMPT01"

--registration-commit 必须使用 root 对 R2 的新登记提交，不能填写旧 8e35b51。新 PLAN 和 runner 的字节也会与该提交核验。完整原始算法 prepare 仍未在编写 R2 阶段执行。

## 局部接口核验

tests/paper_rebuild/test_empty_navigation_prefix.py 唯一新增 6 项测试，首轮 6/6 PASS，pytest 0.14 s。覆盖默认拒 empty；显式资格及来源绑定；空 provider 令四颗合法伪距的合成 SPP 无解/初始无 anchor；未来 manifest 尚不存在仍不早开；到 cutoff 恢复并拒旧 snapshot 回退；单 RX 空的非空正常路径及元数据矛盾拒绝。

唯一计算性调用为一次合成 SPP 失败测试；没有 RTKLIB/CDLL 调用、真实 UBX、converter、prepare、搜索或导航。持久日志 <TRUSTED_HEADING_SCRATCH>/EMPTY_NAVIGATION_LOCAL_TESTS_ATTEMPT01/pytest.log 与 RECEIPT.json；公开回执 FULL_WINDOW_PREPARE_R2_LOCAL_TEST_RECEIPT.json。测试后 runner 仅补“已有非普通文件不可误报缺失”守卫并 py_compile；真实接口源未再变。没有重复旧大套件。

