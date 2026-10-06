# 三类动基线文献方法：结果与执行入口

2026-10-04 更新：显式V2物理SPP修复后的新九组合、三次offline与独立复算/三图目视验收已全部完成。最新论文数字见 [V2验收与数字入口](v2_fix/README.md)、[V2完整总表](v2_fix/COMPARISON_TABLE.csv) 与 [V2修复/暂停历史](V2_REPAIR_NOTES.md)。下列原总表、图及最终比较仍为完整保留的 **V1历史结果**。

本轮已完成既有横向结果取得、三类核心实现/必要验证、九个完整方法×序列运行和三条序列离线评价。全部失败保留；真实性、可用性和精度分开。[最终比较](FINAL_COMPARISON.md)给出结论与边界，原V3及旧结果未改。

1. [既有结果及存储](EXISTING_COMPARISON_RESULTS.md)、[身份索引](EXISTING_COMPARISON_INDEX.csv)：CLEAN4/CLEAN7与HX02/HX02E/HX03/R2/HX05/HX07/R，包含失败与旧版本。
2. [新三序列完整总表](COMPARISON_TABLE.csv)、[全部共同支持](COMMON_SUPPORT_ALL.csv)、[原生运行/搜索分母](NATIVE_RUN_SUMMARY.csv)、[逐运行队列](RUN_QUEUE.csv)。指标保持原完整精度；派生比例有公式，缺失不是0。
3. 逐序列报告与连续图：[BY2](evaluation_results/BY2/README.md)、[BY2H](evaluation_results/BY2H/README.md)、[BY2O](evaluation_results/BY2O/README.md)。各目录ERROR_SERIES保留新三方法全部窗口行，REUSED_ERROR_SERIES为读取的旧RTKLIB四变体；原生全部历史HEADING在native_results对应序列。
4. [论文/公式/工程假设](REPRODUCTION_NOTES.md)、[EXT02修订](EXT02_IMPLEMENTATION.md)、[EXT03递推适配](EXT03_IMPLEMENTATION.md)、[原始输入pins](INPUT_PINS.csv)、[包内成员](PAPER_PACKAGE_INDEX.csv)。论文原件和页图不上传。
5. [失败解释](FAILURE_EXPLANATION.md)、[103个细化失败的全部来源](FAILURE_DETAIL.csv)、[旧对照及退化层级](CONTROL_AND_DEGRADATION_SCOPE.md)、[离线评价定义](EVALUATION_PROTOCOL.md)。
6. [实际调用与源码一致性](FINAL_EXECUTION_RECEIPT.json)、[逐批提交回执](COMMIT_RECEIPTS.csv)、[执行历史](PROGRESS.md)。最后交付提交的自身SHA由Git/终端回执给出，不递归写入本提交。

## 代码、配置与验证

- [EXT01既有精确核心](../../../../src/legsa_gins/paper_rebuild/horizontal_literature/ext01_clambda.py)、[共同原始DD适配](../../../../src/legsa_gins/paper_rebuild/horizontal_literature/reproduction_backend.py)。
- [EXT02新版本](../../../../src/legsa_gins/paper_rebuild/horizontal_literature/reproduction_ext02.py)、[EXT03新版本](../../../../src/legsa_gins/paper_rebuild/horizontal_literature/reproduction_ext03.py)。旧核心/冻结文件保留。
- [本轮固定配置](../../../../configs/paper_rebuild/horizontal_literature/EXT_REPRODUCTION_V1.json)、[单例执行器](../../../../src/legsa_gins/paper_rebuild/horizontal_literature/reproduction_runner.py)、[离线评价器](../../../../src/legsa_gins/paper_rebuild/horizontal_literature/reproduction_evaluation.py)。RTKLIB基础库复用已验证的pin，无新编译替换冻结库。
- 测试源码在tests/paper_rebuild/test_ext_reproduction_{backend,ext02,ext03,runner,evaluation}.py及对应原核心测试。实际次数/测试修正/跳过见EXT01_SHARED_TEST_RECEIPT、EXT02_TEST_RECEIPT、TEST_RECEIPT、RUNNER_TEST_RECEIPT和EVALUATION_PROTOCOL；不把旧PASS算成本轮新测试。

实际执行入口（BY2H/BY2O只替换sequence，科学配置不变）：

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src python3 scripts/paper_rebuild/run_ext_reproduction_batch.py   --roots configs/paper_rebuild/EXT_REPRODUCTION_ROOTS.local.json   --config configs/paper_rebuild/horizontal_literature/EXT_REPRODUCTION_V1.json --sequence BY2

PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src python3 -m legsa_gins.paper_rebuild.horizontal_literature.reproduction_evaluation   --roots configs/paper_rebuild/EXT_REPRODUCTION_ROOTS.local.json --sequence BY2
```

这些命令已执行，既有输出目录会拒绝覆盖。读取结果无须再运行它们。独立图修订加`--plot-only`只读保存误差，零新reference/evaluator。单方法`reproduction_runner`和准备脚本`reproduction_prepare`均有明确参数；输入资格与运行配置在首次真实运行前已提交，不运行旧controller。

定向测试命令示例（合成/native-library测试，不是新的真实序列运行）：

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=src python3 -m pytest -p no:cacheprovider   tests/paper_rebuild/test_ext_reproduction_backend.py   tests/paper_rebuild/test_ext_reproduction_ext02.py   tests/paper_rebuild/test_ext_reproduction_ext03.py   tests/paper_rebuild/test_ext_reproduction_runner.py   tests/paper_rebuild/test_ext_reproduction_evaluation.py
```

## 真实位置与保留方式

公开文档使用别名；机内根映射为ignored `configs/paper_rebuild/EXT_REPRODUCTION_ROOTS.local.json`。

- `<EXT_REPRO_ROOT>/START_HERE.local.md`：实际WSL/Windows入口。
- `<EXT_REPRO_ROOT>/NEW_RESULTS.local.csv`：9身份的RUN/完整HEADING/重型EPOCH_EVIDENCE精确实际路径；新文件均保留。
- `<EXT_REPRO_ROOT>/runs/<SEQ>__<METHOD>__RAW_REPRO_V1/`：完整历史基线、float/整数候选、模型、协方差与状态，失败不删除。
- `<EXT_REPRO_ROOT>/evaluation/<SEQ>/`：完整评价、旧误差读取、共同key、来源和访问回执、PNG/PDF。
- `<EXT_REPRO_ROOT>/existing_hx.local.csv`、`existing_clean.local.csv`：全部已取得旧结果真实位置；大载荷的存在/读取/释放状态逐条保留。
- `<EXT_REPRO_BUILD>/papers`：指定成员及页图；`lib/`为pin固定的隔离库。原始raw不移走、不改写；没有新ZIP或载荷释放。

heading-only方法没有NAV位置/roll可补，fixed不是真整数正确性。原V3只按ca73冻结身份引用，不是修正版本；商业reference只离线读，未升级独立真值。所有三个方法均有实测大误差/失败，最终报告不以谁胜出作为复现完成标准。
