# N16_ONLY：按实际观测维度检查 std 质量

本候选只在 `<VALIDATION_BUILD_ROOT>/source_N16_ONLY` 实施；正式源码、旧观察源、原配置和真实输入均未修改。来源为原 `ca73cb1` 科学实现及已验证观察层。入口 [READY.json](READY.json) 记录候选 binary、完整 source manifest、两层 patch 的 SHA 和测试结果，等待根代理独立审查/提交后才允许其真实队列执行。本 worker 的真实 native/evaluator/provider 调用均为 0。

## 实现范围

- `SourceMetadata::std_active_axes` 显式表示 std 质量域，默认 `[true,true,true]`；仅实际构造 `horizontal_2d` 的 HV 赋 `[true,true,false]`。不是仅按 vertical_disabled flag 或 source 名称猜维度。
- `maxStd` 和 `finiteStd` 只遍历 active 维，仍按原 N/E/D 顺序比较，保留 active NaN 的原比较行为。空 mask 的 maxStd 为 NaN、finiteStd 为 false，走原 n6b std-invalid 保护，不能视为合法零不确定度。active 非有限/非正值沿原保护/拒绝规则，不新增强制接受。
- `std_xyz` 原值不改，999 不写零；观察 JSON 同时保留 std_xyz 和 std_active_axes，原 trace 的 metadata_summary 另记 mask。原二维 H/R、quality flag、provider/validity、OIM、cap、顺序、N12 dz 统计和 N09 调度均保持。上游 `positiveStd` 预处理未修改，metadata 接口测试与 helper 前处理的作用分开。

[N16_ONLY.patch](N16_ONLY.patch) 是相对 `<OBSERVED_SOURCE>` 的零上下文候选 patch：三份科学文件及必要的 active-axis 观察字段扩展，共四文件。随后才安装 [COMMON_OBSERVATION.patch](COMMON_OBSERVATION.patch)，该层单独增加完整 P 的只读诊断、候选身份与创新 residual_vector；不把公共层算作 N16 科学修补。公共层提交为 `6979459bb69154d70b6e88220e3dff29e3356568`，三个安装目标及父目录均非 symlink，解析后在本候选源内。

## 本轮新增原生测试

GCC 11.4.0、C++17、Release `-O3 -DNDEBUG`，候选独立 `build_N16_ONLY`、`-j2`；构建见 [BUILD_RECEIPT.json](BUILD_RECEIPT.json)。新 [native_fixture.cpp](native_fixture.cpp) 分别链接旧观察 library 和本候选 library，不复用旧测试 PASS。三个新进程为 old-observed baseline、candidate observer-off、candidate observer-on：每进程 126 个 policy 场景与 10 个 GIEngine helper 场景，136 个唯一合成场景、408 次场景执行。

[CHECKS.csv](CHECKS.csv) 为 **366 PASS / 0 FAIL**；[FIXTURE_RECEIPT.json](FIXTURE_RECEIPT.json) 保留编译/调用命令、二进制 hash、退出值和输出入口。覆盖内容包括：

- inactive D 为普通值、999、NaN、正负 Inf、0、负数，不改变二维 std 判别；active N/E 的 NaN/Inf/0/负值仍进入原 std-invalid 保护；空域和单 active 轴、严格阈值 10/nextafter 边界均检查。
- 六来源 × 八组三维 std 条件 × n6b/legacy 两模式的 96 个默认三维控制，其科学结果与旧版逐字段相同，包括 active NaN 顺序、理由词和接受状态。其它源仍默认三维。
- 其它 metadata 质量因素保留 LSIM=1.5；provider 不可用/invalid source、SA-off/source-off/LSIM-off/mode-off 保持原行为。OIM 或 cap 能遮蔽 LSIM 差，未把条件变化等同最终 R 变化。
- 实际 GIEngine helper 的 H/R 维度与 mask 一致，999 仍记录；真实二维路径在不同 inactive D 下科学状态一致。actual 3D 分支、策略关闭和 cap 遮蔽负对照的全状态/P/计数与旧版字节一致；全部 10 场景 candidate observer-off/on 字节一致。cap 场景实际 LSIM 从2变为1.5而最终倍率同为10，完整更新状态不变。

旧实现对新 inactive-domain 契约的六个反例保存在 [OLD_CONTRACT_COUNTEREXAMPLES.json](OLD_CONTRACT_COUNTEREXAMPLES.json)，标为 `EXPECTED_OLD_CONTRACT_FAILURE_RETAINED`，没有改记成旧版通过新契约。异常测试失败 0、native fixture 重试 0。首次源码准备曾因 `rg` 未显示六个 `.gitkeep` 而触发数量断言，发生于复制前且 native=0；准备记录保留于 [CANDIDATE_MANIFEST.json](CANDIDATE_MANIFEST.json)，后续改为安全枚举全部 regular 文件，未遗漏隐藏源成员。

## 实物与边界

旧观察源 156 文件在本项前后 hash 全部相同；新源 157 文件（增加公共 P 头）见 [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json)。源码基线清单 [SOURCE_COPY.csv](SOURCE_COPY.csv) 记录原文件哈希，新代码、编译输出与 fixture 全量输出原位保留：

- `<VALIDATION_BUILD_ROOT>/source_N16_ONLY/`
- `<VALIDATION_BUILD_ROOT>/build_N16_ONLY/`
- `<VALIDATION_BUILD_ROOT>/fixtures_N16_ONLY/{baseline,candidate_off,candidate_on}/`

fixture 输入只在 C++ 内构造；没有真实 provider/reference/NAV 读取，也没有执行运行矩阵、评价器、bootstrap 或 Git 操作。公共 P 专项的旧测试次数没有加入本项 366 检查；本项只额外检查它在新 helper 场景中的逐 IMU 末覆盖及观察无干扰。合成状态变化证明代码路径能到达更新，不是已测真实闭环精度改善；真实 C00/D15 结果待根代理批准后的候选队列。
