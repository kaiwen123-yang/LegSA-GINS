# 原 V3 三全窗因果 NAV / RAWX 模型准备登记

状态：事前登记，尚未执行转换、SPP、模型构建、整数搜索、导航或评价。执行须由 root 提交本 runner 和 PLAN 后启动。机器合同为 FULL_WINDOW_PREPARE_PLAN.json；唯一新脚本为 scripts/paper_rebuild/carrier_phase/full_window_prepare.py。原 real_trial.py 保持不变。

| 序列 | 原 V3 完整相对秒窗 | NAV cutoff | 新 / 复用 prefix | 新 converter 上限 | 既存全窗 RAWX 对数 |
| --- | --- | --- | --- | --- | --- |
| BY2 | 66–340 | 66、80、100:20:320 | 2 / 12 | 4 | 1370 |
| BY2H | 413–683 | 413、420:20:680 | 15 / 0 | 30 | 1350 |
| BY2O | 3186–3563 | 3186、3200:20:3560 | 20 / 0 | 40 | 1885 |
| 合计 | 原三个完整窗 | 49 prefixes | 37 / 12 | **74** | **4605** |

每个新 prefix 两接收机各转换一次；原 BY2 100–320 的 12 组 NAV 字节复用。准确预算是最多 **74 次 converter + 3 次模型 prepare**，converter 重建、整数搜索、导航 EKF、评价、参考读取均为 0。三个 prepare 各保留全部默认 family（GPS L1、GPS L1/L2、GPS/Galileo/BeiDou 多频）；不能把 BY2 曾有的实际组数强加给 H/O。4605 次原始码 SPP 尝试、最多 13815 个 family 构建机会单独计数，失败与未尝试原因完整保留。

## 输入及计数身份

本地路径由 configs/paper_rebuild/EXT_REPRODUCTION_ROOTS.local.json 与 CLI 参数解析。registry 为 <EXT_REPRO_ROOT>/inputs/{BY2,BY2H,BY2O}/INPUT.json。其 GNSS 原 CSV 路径、登记 SHA、大小逐项绑定 AR_V3_RESEARCH_20261006/V3_BASELINE_LOCK.json。

实际只读 registry 指向的 GNSS1/2 UBX：

- <CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY/RUNS/BY2__RTKLIB__NONE__C00__NA/native/SOURCE_BACKEND/gnss{1,2}.ubx
- 同 RUNS 根：BY2H__RTKLIB__NONE__CONTRACT_START__NA/native/SOURCE_BACKEND/gnss{1,2}.ubx
- 同 RUNS 根：BY2O__RTKLIB__NONE__FILE_START__NA/native/SOURCE_BACKEND/gnss{1,2}.ubx

PLAN 的 source_files/hash_status=NEWLY_VERIFIED 是复制自原 registry 的历史字段，**不是本次编写阶段重新 hash 的声明**。本轮仅核既存 metadata 与大小；实际执行才核 UBX 源身份。原 CSV、body、IMU、PVT、参考 Trace、旧完整 NAV payload 都不打开。

INPUT.json 的全录制 pair_count 为 1509 / 1483 / 2231。全窗 1370 / 1350 / 1885 来自 docs/paper_rebuild/hext/DG01/DG01_OVERVIEW.csv 的两接收机 raw_epochs，并由 DG01_INTER_RECEIVER.csv 的 paired_epochs 行核对；两表已 pin。位置消息 1371 / 1351 / 1886 不是本步骤 RAWX 分母。配对数或重复/不配对数不符，保留输出并停止，归类为输入模型准备失败，不能解释为算法精度差。

复用 <OLD_CARRIER_ROOT>/CAUSAL_NAV_SCHEDULE_V2/NAVIGATION_SCHEDULE.json。初始 100 秒 manifest 指向既有 GAL_NAV_QUALIFICATION_V2 converter，SHA dd9e6d3bf3b68047f53f1efb5c8504ae4849b920b3ab8bf41f2a2a6619396f3c。其已资格 Galileo 八字 guard 修复身份保持，CRC/IOD/SV/health 不改，不重建。100 秒已不再是新 schedule 首条，故新增 metadata wrapper 补齐原 registry/base/UBX 身份，原 NAV 与 manifest 不改，也不利用首条例外跳过身份核验。

## 固定时序与模型

复用 prepare_navigation.scan/nav_records。scan 审查完整 UBX，但 converter payload 只包含 cutoff 前最后 RAWX 关闭的前缀。未来帧统计仅在资格日志，不能进入当前 NAV。NavigationReplay 仅在当前 RAWX 时间加载不晚于当前时刻的最近 prefix。旧完整 NAV 不作默认输入，也不为 provenance 再读。

L=0.35 m、max_gap=0.21 s、TDCP 工作限=0.5 cycle、原始码 anchor 最长 hold=20 s、pivot policy=reselect_when_missing；其余 AnchorPolicy、RAWX SD 方差和模型构建规则保持被 pin 的原源。SPP 几何 anchor 来自原始 GPS L1 码，不能称独立于 GNSS 的位置先验。跨历元独立、SD 独立是原工作模型，不构成已校准统计保证。

完整窗各自重建弧与 pivot 历史，起点弧左删失，不能把旧 100–340 NPZ 拼进新 66–340 结果。各 UBX 为前缀生产核一次 SHA；原样 real_trial 自己各再核一次，共 12 次源身份 hash pass。74 次 scan 重复只读 UBX payload，仅生成因果前缀。新输出封存不再次 hash 原 raw。此为离线因果回放准备，没有硬件实时性主张。

## 失败与输出封存

每次外部调用留 INVOCATION、stdout、stderr；converter 60 s、单序列 prepare 1200 s 外层上限。任何技术、身份或配对资格失败保留 terminal 并停止，不自动重试/补窗。逐历元模型不可用仍保留完整分母，不改参数。每个 prefix 完成输出一行进度。

每序列生成 schedule、prefix manifest/page 资格/转换日志，以及 MODELS 下 PLAN、所有实际 NPZ、ARC_EVENTS、ADAPTER_REJECTIONS、PIVOT_EVENTS、NAVIGATION_SWITCHES、EPHEMERIS_QUALIFICATION、PREPARE_LEDGER。MODEL_OUTPUT_SEAL.json 对本步骤新 MODELS 文件逐一写 SHA/大小，绑定登记/registry/schedule，并核 BUILT 引用与实际 NPZ 集合。MODEL_COUNTS 保留完整分母与 SPP/anchor/family 状态。失败中间产物另留 incomplete partial seal，不冒充完整模型集。

下游打开 PLAN/NPZ 前必须核对应 seal 与来源身份，不能以后猜测 model pin。本步骤不输出候选、整数接纳、航向 provider 或导航性能。

## 登记后唯一入口

以下变量由 root 解析现有本地配置。REGISTRATION_SHA 是包含本脚本/PLAN/所 pin 源的完整提交；runner 对当前与登记版本逐字节核验。编写阶段未执行下面命令：

    export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
    python3 "$CODE_ROOT/scripts/paper_rebuild/carrier_phase/full_window_prepare.py" \
      --roots "$CODE_ROOT/configs/paper_rebuild/EXT_REPRODUCTION_ROOTS.local.json" \
      --carrier-root "$SCRATCH_ROOT/CARRIER_INTEGRATION_20261006" \
      --output "$SCRATCH_ROOT/TRUSTED_HEADING_20261006/FULL_WINDOW_PREPARE_ATTEMPT01" \
      --registration-commit "$REGISTRATION_SHA"

输出目录须不存在。runner 将子进程 PYTHONPATH 设为本工作树 src。语法预检查仅 py_compile 本新文件，不导入或执行算法；回执见 FULL_WINDOW_PREPARE_PREFLIGHT.json。没有新增镜像测试。

Root 已独立只读审查 runner、输入计数来源、原 V3 绑定、prefix 时间资格及本登记，未发现阻断。按上述固定预算执行一个新 attempt；不启动整数搜索、完整导航或参考评价，也不重做既有已封存实验。
