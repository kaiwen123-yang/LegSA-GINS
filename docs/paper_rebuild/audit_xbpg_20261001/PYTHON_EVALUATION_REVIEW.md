# 评价、聚合、绘图与外部适配的语义审查

审查基线 `eb3cbed314693358c7c38442b6fbbb7afcf0342e`。本节来自只读审查者的全文语义检查，19 个仓库文件、5,248 行；冻结评价器另计 421 行，不加入当前仓库自有代码分母。没有执行历史矩阵、历史评价或读取旧性能表来论证新性能。函数组以下文行号定位；纯 import/CLI 合并解释。静态语义审查不等于动态测试。

## 冻结评价器与物理量

正式评价器定位 `<CLEAN_ROOT>/16_FINAL_V23_ARCHIVE_RECOVERY/ARCHIVE_45953164c53e/selected/MAIN/KF-GINS/bin/evaluate_nav_trace_kfgins_v2.py`，本轮实测 SHA256 `aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da`。外部保留文件只用于身份和代码审查。

- 14–26 的阈值是程序显示/诊断设定，不是任何期刊验收标准。28–44 对有限误差按样本数计算 RMSE，角差 wrap；高密度时间点不是独立试验。
- 46–56 hold-time 连续性依相邻数组元素，没有测量缺口门槛。90–122 的 drift 是端点绝对误差/区间时长，不扣初始误差，不能解释为去初值的相对漂移。闭区间边界可能重复，格式错误区间跳过。
- 58–88 的经纬度是 degree，先 WGS84 LLH→ECEF，再以首参考点为固定 ENU 原点，不做 SE(3) 配准。124–138 读 NAV 的时间、位置和姿态，不读速度，因此该正式评价器没有速度 RMSE 能力。
- 140–172 参考列先 exact 再 substring 搜索，列顺序可能使 `processed_*` 被选中；七项联合 dropna 使姿态缺失也缩小位置支撑。排序保留重复时间。XB 的 processed 纬经交换使“直接复用任意列名”不合格，不能把整个文件当独立真值。
- 174–195 STD 的水平量为 sqrt(N²+E²)，不含参考误差和完整相关协方差。197–246 时间交集后 numpy.interp，无最大缺口；yaw unwrap 后按 90°−ENU yaw 转换，roll/pitch 线性插值。179°到−179°跨界中点会变成0°，属于条件性姿态插值风险。Euler 分量差不是 SO(3) 旋转误差。
- 248–327 的 STD 可在端点被夹持；JSON 可有 NaN，由 v3 上层再拒绝。335–421 是显示与导出，不改变已捕获误差数组。

因此本轮未把 XB 商业 POI 的时间/物理点资格缺口隐藏在旧评价器内，绝对误差为 NA。已有真实记录是否遇到 gap/跨界必须另查实际支撑，本轮未据静态反例声称所有旧数值无效。

## 当前 v3 正式运行链

文件前缀 `src/legsa_gins/paper_rebuild/protocol_v3/`。

**evaluation_process.py（157行）**：25 独占写 JSON、禁止 NaN；31–71 校验冻结评价器/捕获器身份，设置子进程配置和单线程；72–99 strace 包装、超时及资源回执；100–143 按 PID 追踪一次只读 trace open、禁止 raw 写，哈希从同一文件句柄产生并记录所选列；144–157 封存导出。访问证据比硬编码 flag 强，但只证明该过程访问，不证明 provider 的更早构造无参考污染。

**runtime.py（349行）**：23–37 身份缓存比较大小/mtime/inode，适合非对抗性只读流程，不是任意篡改证明。40–58 flock 保留唯一 run_id；61–86 用逐行克隆保持 runtime 文本语义，记录回显；89–113 seal/load；116–193 检查 native 返回、NAV/STD 有限、严格递增及时间处于请求窗，但缺少首尾覆盖/最大缺口 gate，早退有限轨迹不能仅据此叫 full-window。196–218 失败槽保留 NOT_RUN；219–237 按 BY2 杆臂 `[0.03,0.03−baseline/2,−0.3]` 及完整 Cbn 只变位置，STD 没做杆臂姿态不确定度传播（文档已限制其诊断含义）；238–277 评价一致性和封存；280–340 历史精确归档/删除入口本轮未调用；343 路径映射。上述杆臂不是 XB 校准。

**reporting.py（558行）**：40–100 解析哈希/有限 Decimal/相对差/状态；103–140 Sources 验证角色路径和哈希，拒绝 raw；143–166 验证 registry 全槽唯一和 data_mode；169–196 主表复用外部保留行并不自动构成新完整复现；199–218 v3/v2.1 以精确键且双方有限比较；221–258 失败与成功计数使用注册分母。261–288 paired 摘要仅双成功，需要与 failure 表一起解释；291–304 ECDF 保留全注册分母，失败不填0。307 复制冻结敏感性项；319 固定区间；341 文稿说明；362–398 RuntimeResults 保存所有槽；400–435 失败行 NA；437–480 压缩序列必须唯一递增并绑定一次 reference export；483–558 聚合调度与输出。不能概括成“v3 自动把失败都删掉”；真正的风险是脱离全分母单独引用 pair-only 图表。

**figures.py（495行）**：34–81 failure 标记及 run_id；84–132 machine QA，不能取代光栅检查；135 输入表 hash；156–180 固定区间/无效掩膜；183 失败 bundle 不生成伪曲线。226–269 mfig00 的 local ENU 是显示近似，正式指标仍 WGS84；轨迹绘图没有一般 gap 分段。272 配对值范围；293 mfig03；318 方法阶梯是图形排列，不能证明 F01→F02→F03 单因素；335 掩膜无效值；356–386 mfig05 也缺一般 gap 断线；389 序列失败图；414 主 renderer 在缺项时报告不完整并保留人工 QA 门槛。

**aggregate_recovery.py（583行）**：30–37 常数是身份/计数约束而非性能验收；40 Pins；67–117 audit hook 禁 raw/子进程，仅允许明确 trace_source；120 覆盖检查；148–189 源码/输入 gate；192 重用保留输出；255 source freeze；275 保存旧 hard stop；335 渲染 hash；352 零有限行分类；405 附录；452 状态；476 只聚合保留报告；546 CLI 有 package 能力但本轮没有创建包授权。该历史恢复器本轮未执行。

## 共享评价与旧协议

**src/legsa_gins/datasets/by2/trace_reference_adapter.py（105行）**：读 trace 为 evaluation-only；数据角色 flag 主要为声明，缺少全面有限检查，未做 frame 变换。调用端是 standardize_by2_inputs 等数据适配，不是 v3 冻结评价器的直接入口。不能用该 adapter 的 flag 替代上游 lineage。

**src/legsa_gins/external_dual/trace_reference_adapter.py（46行）**：load 跳过坏行而不回传损坏分母；nearest 每次重建全时间数组为 O(N)，允许未来最近点。作为离线评价可以说明双向匹配，不能外推到在线因果数据供应。

**clean5_parity/evaluation.py（387行）**：25 `body_to_ned` 是 FRD 的 RzRyRx；34 LLH 杆臂位置；57 写位置而保留其他 NAV token；89 yaw-only body bias 属明确旧模型，不是全3D安装解；115 窗口选择；141 外部评价；185 方法各自 NAV 支撑配对；225 固定整窗/分段；247 失败表；279 阶梯中的 partial 必须保留。此文件的 BY2 常数不可未经设备证据迁移。

**scripts/paper_rebuild/v3_evaluator_observer/sitecustomize.py（87行）**：16–56 捕获已存在数组、同时间轴，不再 open trace；59 profile wrapper；70 条件安装；81 捕获异常 exit125。因此 exporter 失败不能宣称评价成功。内部 `truth` 列名为历史变量名，不提升来源资格。

**clean5_sequence/evaluator_capture.py（127行）**：18–58 AST 提取 `_local_enu` 是为算术一致性，并非独立评价 oracle；61–92 同一 pandas 已打开句柄 rewind/hash；93 记录实际选列；110 主 WGS84 与旧一致性检查；127 安装。它不会证明 trace 上游独立。

**clean6_canonical_v2/evaluation.py（216行）**：22 JSON/WGS84；48–85 有限与非降序（允许 duplicate），指标核验覆盖 h/u/yaw 而非 RP；88–127 产物身份。120 固定 `semisynthetic_data_used=False`，可与已控制退化的输入角色矛盾，属于已确认元数据缺陷，不据此推导数值伪造；128 gates；189 失败清空指标。

**clean6_canonical_v2/aggregate.py（418行）**：39 失败转 NA；66–99 PCG64 case bootstrap 与 Wilcoxon 是 case 条件重采样，不是跨场地/独立硬件推断；102 状态集合是旧协议，不能直接认全 v3；114 注册配对保留失败；225 方法 alias 不重复计数；252 v1/v2 精确 case 规则；313–418 聚合，401 同样固定 semi=false。需修文档/manifest并核查实际作用产物，不能靠重新运行算法解决元数据语义。

**clean5_parity_p04/evaluation.py（176行）**：18–28 覆盖为可匹配误差数/NAV窗内数，不等同请求时间比例；31 重用行；44 明示混合因素 decomposition；58 表；79 将 generalization partial 状态保留。高覆盖率不能掩盖 NAV 只输出很短一段。

## 外部代码身份与待办边界

目录前缀 `src/legsa_gins/paper_rebuild/hext/`。

**external_evaluation.py（260行）**：37 window argv 不含 STD；69 NAV 11列/有限/递增及 BY2 物理点；101 窗内指标；116 capture；129 子进程 strace 且一次 trace；208 soft failure 显式 `metrics_admitted=false`。本轮没有调用其性能评价。

**hx02_ginav_nav.py（113行）**：27 GPST→UTC固定18秒对2026适用，不能当跨年代通用；40 官方 GPS week/tow、ECEF→LLH、ENU→NED速度及姿态列重排，时间量化到毫秒；74 输出有限及窗口截取；97 CSV/NAV转换和计数。严格转换身份不等于方法已全面复现。

**hx02_hartley.py（228行）**：48 身份前缀；60 UTF-8 stream、IMU单调和安装转换，高层 foot_position/speed 是设备内部估计，非用关节角独立实现FK；107 缓存/contact门槛/实际dt，列表仍占内存；155 构建自有移植runner，不是官方二进制；179 dirty 标记来自上游选择；194 线程1/hash/timeout，OS访问审计由上层；209 divergence 只看位置速度，不证明旋转/协方差健康，单行边界未动态验证。

**hx02_ginav.py（231行）**：63 MATLAB cfg 与 GPS 起点floor；96 ASCII派生路径按行克隆，原中文路径需scratch适配；133 raw G1 RINEX+Go2 increments，无 trace 输入；172 tracked mirror；195 MATLAB唯一pos/ledger，上层提供OS审计。

目录前缀 `horizontal_literature/ginav2021/`：**constants.py（261行）** 8 身份和状态标签不是用户待办状态的最终证明；83 convbin 的 nominal500不能代表数据实际独立频率；111 噪声PSD/杆臂是配置，不是 XB 校准；173 列和量化；247 禁止角色。**source.py（451行）** 25 hash/copy exclusive；68 Git identity tracked clean不含全部untracked；162 clone能力本轮未调用；188 只mirror tracked source排除data/results；263 校验列表但不证明无额外shadow文件；286 pathname gate不等于payload无泄漏；309 AccessLedger是应用级，非OS级；404 before/after guards；441 fsync原子写。

本机 GINav HEAD `bc6b3ab6c40db996a4fd8e8ca5b748fe21a23666`、tree `94940c5b72c6003f696f6ed3684ee5b10875e792`，tracked clean。不是对全部第三方逐行审查的声明。Hartley路径的自有runner/高层足端代理不等于完整目标论文复现。三篇论文完整复现及公平横比仍为待办；本轮只承认用户已认可的 RTKLIB 动基线工作。

## 部分读取与证据边界

以下只给 `PARTIAL_SEMANTIC`，不计全文完成：canonical541/offline_eval_aggregate.py 230–380/487–665；hext/t5a_runtime.py 1–115/586–608；publication/canonical541_figures.py 25–67；publication/protocol_v2_figures.py 20–95；publication/protocol_v21_figures.py 1–90及部分mfig02；hext/hx02_execution.py 680–790。其余代码队列见覆盖表，不能用 legacy 标签跳过。

v3 tracked AST import 对8个旧未跟踪hext模块没有命中，反证“v3必定依赖这些文件”的断言；未跟踪 hext04_execute 自身依赖 matched_execution 等未提交脚本，仍非 commit 可复现。动态字符串导入的全面排除未完成。原文件均原样保留。

主要问题 ID：P-EVAL-01 元数据；02 时间缺口/重复；03 RP插值；04 运行支撑；05 物理点/STD；06 已反证的失败删除；07 case重采样推断；08 画线缺口；09 上游lineage证据不足；10 已反证的静态未跟踪依赖断言；11 文献完成标签当前不适用；12 hold/drift定义；13 adapter坏行与有限检查。所有旧实际结果受影响历元数均未在本轮重新评价，不能编造需重跑的具体案例数量。
