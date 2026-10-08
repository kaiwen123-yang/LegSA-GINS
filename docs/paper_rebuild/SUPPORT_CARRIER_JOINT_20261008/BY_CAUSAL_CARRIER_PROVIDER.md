# BY 因果载波入口修正：方法与实际输入结果

状态：**观测构造和完整输入组装完成；本阶段没有运行导航、整数搜索或参考评价。** 数值与哈希见 [BY_CAUSAL_CARRIER_PROVIDER.json](BY_CAUSAL_CARRIER_PROVIDER.json)。

旧完整输入覆盖 66–340 秒，原成对 RAWX 在这个窗口有 1,370 个槽；并没有从 100 秒人为裁剪 RAWX。旧 `real_trial.prepare` 先要求 GPS L1 码 SPP 成功，失败就跳过全部星座的 DD；其广播 NAV 又只在 66、80、100、120…秒的快照切换。这个 **GPS-only SPP 总闸与粗快照共同造成入口上的虚假等待**：实际可建的首个块在 74.398 秒，旧入口到 100.198 秒才提供，差 **25.8 秒**。这不是原始载波在前段缺失，也不能把全部 25.8 秒单独归因于一个门：新入口中 GPS 自身首个可建块在 90.198 秒，BDS 更早。

## 当前测量模型

`stream_provider.py` 读取同一对已锁定的原 UBX；`stream_rtklib.c` 为两个接收机分别维护 RTKLIB `raw_t`，沿原帧序喂入数据。只有 native decoder 返回完整星历更新时，才将该接收机的完整 GPS/Galileo/BDS 星历追加到公共查询表；从不跨接收机拼导航页。轨道、卫星钟、健康、龄期与频率资格仍用既有 RTKLIB/checked ABI，Galileo 仅继承原 E1B 8-word guard 修正，CRC、IOD、SV 与健康处理未改。

日志中的 SFRBX 没有独立接收时间戳，所以消息必须等待**同接收机紧随其后的原 RAWX 时间戳**才能释放。这是日志可证明的到达上界，不是精确传输到达时刻。没有后续 RAWX 的尾部 SFRBX 不释放；不再使用 20 秒快照栅格。预处理可以读完整文件核哈希，但未来帧不进入当前 RTKLIB 状态。

几何锚改为观测时刻之前最后一个有效的既有 GNSS18 **GNSS1 位置**，只计算 LOS、共同锚处的已知单差项及仰角。`real_data.py` 核对锚与导航使用同一 GNSS18 文件哈希，原 1,371 个 P/V 事件仍是其原有测量入口，没有增加位置因子，也没有消费 PVT 航向或参考。GNSS18 的真实传输延迟未记录，目前仍以源测量时刻表示其可用时间。

DD 继续使用每个接收机自己的原码观测确定卫星发射时刻，继承卫星钟与地球自转处理、同信号分组、原 RAWX 载波条件、ArcTracker、换 pivot 规则和 SD→DD 的 Q 传播。后端 M2 物理信号相关噪声是另一层契约，本阶段没有改它。LOS 锚与 P/V/raw 同源，几何是对该锚的条件化线性模型；未建其完整联合交叉协方差，不能据此宣称来源独立。

## 实际结果

| 项目 | 结果 |
|---|---:|
| 原 RAWX 槽／新 BUILT | 1,370／1,329 |
| 66–100 秒槽／新 BUILT | 170／129 |
| 首个合法 DD 块 | 74.3980000019 s |
| 首个 BDS／GPS／Galileo 块 | 74.398／90.198／99.198 s |
| 首块观测行／整数坐标／B 秩 | 20／10／3 |
| 实际完整星历更新／native 拒绝帧 | 51／0 |
| 已记录的合格信号查询 | 29,490；所用星历全部已到达 |
| 最大 GNSS1 锚龄期 | 0.1980001923 s |
| 完整 real_data 事件 | 8,762；IMU 最大发布延迟仍 13.045238 ms |

首块含 BDS B1I 的 9 颗卫星和 B2I 的 3 颗卫星，两组 pivot 都为 C07；锚为 GNSS18 第 93 行、74.200000048 秒。前 41 个槽仍没有合格 DD 组，未填补。66–100 秒的 129 个 BUILT 块均为 B 秩 3，但这只是测量几何，**不代表整数唯一、全局可信航向或导航已初始化**。

100 秒以后，对共同 1,200 个历元、20,377 个物理 DD 对做精确整数行换基比较：Q 最大差 **0**，y 最大差 **2.1647662×10⁻⁵ m**，B 元素最大差 **1.7739736×10⁻⁵**。旧 GPS SPP 与新 GNSS1 锚最大相差 536.298 m；短基线共同锚差分使实际 DD 变化保持上述量级。新源早段的几何收益不能从这些输入差异直接推出。

只做了一次实际首块独立构造对照：将两个原 UBX 分别截止至 74.398 秒，用既有已锁定 convbin 输出因果前缀 NAV，再经既有 broadcast ABI 构造相同物理 DD。A/Q 完全一致，y 最大差 **4.8428774×10⁻⁸ m**，B 最大差 **8.1475104×10⁻¹²**。回执 `FIRST_BLOCK_CHECK/CHECK.json` 保留两次接收机转换的完整 argv、哈希和结果。这验证流式接入与原生前缀构造一致，没有新增测试矩阵。

Focused scientific read 核对了帧释放顺序、独立页缓存、完整星历合并、接收时刻的星历选择与 provenance 选择一致、own-code 发射时刻、Q 与弧身份及锚的单次测量使用。在当前 BY 数据和调用链中，**未发现改变因果性或物理观测的实质实现错误**。上述时间上界、同源条件化和未证明早期可信航向是科学范围，不用新增保护门替代模型研究。

## 结果身份与复现

实际输出根为 `/home/kaiwen/research/LegSA-GINS-SCRATCH/SUPPORT_CARRIER_JOINT_20261008/BY_CAUSAL_CARRIER_PROVIDER_02`。旧 PLAN、旧模型和旧导航结果未修改；失败 `01` 的缺失 `rtklib_compat.c/showmsg` 载库记录保留。首块检查通过后，独立组装脚本曾误把 `load_by2_events` 返回 dict 按 tuple 解包；修正调用后输入组装完成，没有重跑导航。

| 身份 | SHA-256 |
|---|---|
| 原 GNSS1 UBX | `24177f2d6f25c0b614f769e66c4e4147eea727f3a7f55e22d5e04419eaa10f8b` |
| 原 GNSS2 UBX | `0876d7e67441ddfce66b4ce8e39838b4245bddab3d6d3cce60d5eb9bad42c2c2` |
| GNSS18 | `fc6dd49c0a35c41208fc7d94da1c78ad63fe6938bd8f599021750c3bf5e20760` |
| 旧 PLAN | `16580a87ee787d4890edd22a8fc8bfb9b0771242e427201a952f323f233879ea` |
| 新 PLAN | `436a56c4d8e756a1431bd56af628dd1c0be621b43d760319f653d52e8f7a5845` |
| 新流式 RTKLIB 库 | `98f6dbaaf5f92be69b22a2f6bf686d06ad04f919944dabf1ce8a5b67190919ff` |
| 完整 continuation record | `e23efd46adaed6f18d6f58d88447bae48ed4049281cce9ed0dec8148455b74b1` |

准备时 Git HEAD 为 `a26bdef`；新增/修改源码以配套 JSON 的四文件哈希为实际身份，不能仅用当时 HEAD 复现。完整 Python 依赖源哈希在新 PLAN，C 编译参数和全部依赖源哈希在 `BUILD/BUILD.json`；RTKLIB 源版本为 `180043ee24b6d2b168f98b64be15f69d50046b1a`。

以下在 WSL 仓库根执行；输出必须换成未存在的新目录，避免覆盖本次结果。只构造观测，不启动导航：

```bash
task_scratch=/home/kaiwen/research/LegSA-GINS-SCRATCH
task_output="$task_scratch/SUPPORT_CARRIER_JOINT_20261008/BY_CAUSAL_CARRIER_PROVIDER_REPRO_01"
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src \
/home/kaiwen/research/LegSA-GINS-ENV/support-carrier-joint/bin/python \
scripts/paper_rebuild/carrier_phase/prepare_by2_stream_provider.py \
  --old-plan "$task_scratch/TRUSTED_HEADING_20261006/FULL_WINDOW_PREPARE_ATTEMPT02/BY2/MODELS/PLAN.json" \
  --gnss18 "$task_scratch/CLEAN8_PROTOCOL_V3/02_PROVIDERS/CASES/BY2__C00_clean_normal__b98b48979d509bce1429b360c6e0d675c028ff42e3158d4c97dd63df61d62663/GNSS18.gnss" \
  --clean-root /mnt/g/LegSA-GINS-project/clean_rebuild_202607 \
  --rtklib-root /home/kaiwen/research/LegSA-GINS-EXTERNAL/RTKLIB \
  --bridge-source /home/kaiwen/research/LegSA-GINS-EXTERNAL/rtklib_bridge/legsa_rtklib_bridge.c \
  --output "$task_output"
```

完整输入的接法是将同目录 `input_config.json` 中的 `carrier_plan_path` 替换为新 PLAN，按 `By2InputConfig` 传给 `load_by2_events`，读取其 `events/metadata/input_summary` 三个键。已执行的 `assemble_input.py` 与输出保留在实际结果根；没有改 navigator 或 branch。

旧 full07 比较仍描述**旧 provider 限制下**的导航表现，不能再把 66–100 秒的 NO_INIT 称为原载波不存在。后续导航需使用新输入单独登记；本阶段没有证明更早的可信初始化、速度/位置收益或全程恢复能力。
