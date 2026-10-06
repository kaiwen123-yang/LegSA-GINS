# 原 V3 三全窗导航：事前登记

前端终态已封存，JSON已登记其COMPLETE身份和REGISTERED_READY状态。登记时尚未执行prepare、配置检查、真实native或评价。root独立核对控制器，并由另一agent复核原V3输入/参考隔离；比较器也完成交叉只读审查。登记提交后先prepare六配置及loader检查，确认后依次执行六native、全封存后的六评价、一次只读比较。

## 固定输入和两臂

唯一来源为 FULL_WINDOW_NAV_INPUT_MAP.json / 忽略的 LOCAL_PATHS.json 与 AR_V3_RESEARCH_20261006/V3_BASELINE_LOCK.json。六个新身份为 BY2/BY2H/BY2O × PVT_CONTROL/CARRIER_FALLBACK；原窗 66–340、413–683、3186–3563 s，实际输出边界由 NAV 确认，不能把名义 end 当成最后采样。

从原 V3 三份配置逐字节克隆。仅 13 个显式字段可替换/添加：runtime_contract、stage_id、protocol_id、case_id、run_id、run_label、outputpath、heading_source_policy、dual_antenna_measurement_model、baseline3d_source、external_carrier_baseline_path、baseline3d_body_vector_m、dual_yaw_prediction_model。未改行的字节须相同，其余解析键值须相同；同序列两臂仅身份/output/policy 不同。algorithm_id、原五 provider、7 列 500 Hz IMU、全初始化、P/RV/旧 HV/RD/RP/SA 均保留。

三份原 stage 分别为 CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX 和 CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD（H/O），没有显式预测项，也不属于 IMU_V3_TIME_CONTRACT_FIX_20261004，因此解析后的原公式均是 euler_yaw。新配置显式保留此值，不冒用近期 IMU 修正研究的 lateral_projection。

两个新臂共享 research exact-event 调度，不能宣称它们等同于原 V3 legacy 调度。旧 HV 仍依赖 GNSS 航向旋转，不包装成独立本体速度。原双天线初始化保留，不是纯载波冷启动。

## 入口、预算与锁

新脚本 scripts/paper_rebuild/carrier_phase/full_window_navigation.py：
- prepare --stage <NEW_STAGE> --registration-commit <COMMIT> --local-paths <NAV_INPUT_MAP_LOCAL>/LOCAL_PATHS.json --frontend <SEALED_FRONTEND>
- native --stage <NEW_STAGE> --registration-commit <COMMIT>
- evaluate --stage <NEW_STAGE> --registration-commit <COMMIT>

prepare：绑定登记中的 runner/PLAN/source pins、三份原 config/15 provider（仅运行输入；不重哈希原 raw）、前端 COMPLETE→SUMMARY/三个 OUTPUT_SEAL→CARRIER/各 SUMMARY。CARRIER 保留所有原始时刻与 invalid 行，检查 15 列、严格时序、measurement_time=decision_available_time、窗界与完整计数、有效点 full SPD。前端处理预算耗尽的全窗保留终态必须原样记录，不能当成功固定率；技术 FAILED 不准入。参数/指标不参与输入选择。

prepare 使用已封存的新 native 静态库编译一个只调用 PortConfigLoader + FileSaver 的 config checker，至多编译 1 次、检查 6 配置；不创建或传播 GIEngine，不加载真实 provider。此子阶段亦须等 root 登记后执行。checker 与 binary/lib/源身份一同保存。

native：六次逐个保留调用与原始输出，被动 strace；任何 raw/reference 打开、意外受保护路径读写、配置/源哈希不符均技术停止，不重试。每次事前 ledger 预留唯一槽。检查STD至少10列、行数及逐行时间与NAV完全一致；保存 NAV/STD hash、实际时间键、bound、manifest 和完整 heading event ledger。原始程序异常停止并留证；若有完整有限输出但违反既有 bounded_lla_native 门，则仍封存算法失败、其评价为 NA。所有六个 native 完毕才生成 ALL_NATIVE_SEALED。BY2/H 全有效 PVT 两臂预期 NAV/STD 字节相同，此工程等值门失败不得继续评价。

evaluate：先复核六输出 seal，才允许冻结 evaluator 子进程接触其对应参考；控制器不打开/哈希参考。最多六调用，有原算法失败则该身份保留 NA、不替换。采用 protocol_v3/evaluation_process.evaluate 的 canonical_v2_wgs84_full_support、各序列 base_time 和完整窗；不是旧 BY2 硬窗 wrapper。物理点采用 clean5_parity transform_nav/write_transformed_nav 和各自已锁 median，NAV 只改 LLH 三列，STD 原样，不能宣称点位协方差已运输。frozen.window_metrics 使用各序列窗口；所有原始大误差保留。

## 输出接口与归因

stage/PLAN.json；NATIVE/<sequence>__<arm>/{RESULT.json,RUN_MANIFEST.json,HEADING_SOURCE_EVENTS.csv,NAV,STD}；EVALUATION/<run>/EVALUATION_RESULT.json 与 FROZEN_EVALUATOR/error_series.csv；ALL_NATIVE_SEALED.json、EVALUATION_COMPLETE.json。实际时间键 hash 是 little-endian float64 列1字节的 SHA256。每个评价记录直接 pin error_series，末端 seal pin 六结果及派生产物。

独立比较器负责全窗/实际键交集、旧 V3 复用指标、预登记非退化门和事件恢复统计。本 controller 不开旧参考、不从结果挑起点/观察、也不另造共同支持。Fixposition 参考有共享 GNSS 来源；integer truth、错误固定风险、未传播协方差指标仍不成立。0 新 raw/search、不声称硬件实时。
