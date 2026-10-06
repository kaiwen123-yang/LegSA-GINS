# 本阶段入口与精确身份

本文件记录已经执行的命令。复跑前须拷贝根配置到新的stage/attempt、重新生成事前source/config登记，不覆盖本阶段路径。本文件不会自动启动运行。

环境为WSL Ubuntu-22.04；repo `/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001`。Python `/home/kaiwen/research/LegSA-GINS-SCRATCH/FGO_COMPARISON_20261003T030806Z/oisam_venv/bin/python`。本机ignored roots `configs/paper_rebuild/FGO_FIX_FINAL_ROOTS.local.json`，选定三个 `*_PAPER_CONTRACT_20261004.json` 与RAW新合同。

冻结源码联合回归：

```bash
cd /home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001
PYTHONPATH=src /home/kaiwen/research/LegSA-GINS-SCRATCH/FGO_COMPARISON_20261003T030806Z/oisam_venv/bin/python -m pytest -q tests/paper_rebuild/test_fgo_oisam.py tests/paper_rebuild/test_fgo_obgins.py tests/paper_rebuild/test_fgo_wen_tc.py tests/paper_rebuild/test_fgo_gnc.py tests/paper_rebuild/test_fgo_raw_inputs.py tests/paper_rebuild/test_fgo_evaluation.py
```

实际编排脚本均外置 `G:\LegSA-GINS-project\修复_20261004`（WSL `/mnt/g/LegSA-GINS-project/修复_20261004`），脚本hash、命令、日志和独立收据保留：

1. `freeze_fgo_final.py`：登记22源、3方法/RAW/calibration配置、作者编译来源，并复制每文件snapshot；2种identity mismatch probe另存verify_fgo_identity_gates.py。
2. `prepare_fgo_final.py`：三原始输入，新身份before/after源和raw/config pin，sys.audit拒读参考及外部strace。
3. `run_fgo_final_native.py`：9次真实native，sequential、一线程、每身份strace/reference拒读；汇总native journal和all-nine-seal。
4. `evaluate_fgo_final.py`：检查全9seal且各native outputhash不变后，三个独立offline进程每序列一次参考open。各main4辅助依赖前后hash绑定。
5. `render_fgo_final.py`、`reflow_fgo_h_figure_only_r3.py`：表/图，后者只排H的说明文字；数据和轴limits精确相同，前图保留。
6. `verify_fgo_final_metrics.py`：封存误差/N/E/U/state/events的独立NumPy与身份/支持/算法事件核对，不打开原reference，不启动evaluator/native。
7. `run_fgo_author_continuous600.py`：单独601节点作者ADIS真实连续诊断事前身份，拒读truth；不是九格/原论文全实验。`seal_fgo_final_artifacts.py`封小source/test/helper/figure实际字节。

native核心命令为 `python -m legsa_gins.paper_rebuild.fgo_comparison.runner --roots <new-roots> --sequence <BY2|BY2H|BY2O> --method <OISAM|WEN_TC|GNC> --attempt <fresh-attempt>`；最终本阶段attempt PAPER_CONTRACT已经存在，不可重用。raw准备与offline入口的精确args由上述wrapper保存，不能把旧ROOTS/默认MAIN默认为新合同。

旧GNC配置依赖旧source算法接口；新strict源码拒绝旧尾部alternations参数。重播旧14需要旧source snapshot、旧依赖和旧config单独环境，不能直接调用新solve冒充同历史身份。

运行前/后每方法source/config mismatch主动失败；OB编译源/header或library mismatch主动失败。仅22直接执行源事前身份不等于全部第三方动态import图已事前冻结，support helper额外绑定范围见FGO_FINAL_ARTIFACT_IDENTITY。模型oracle和69测试不是全部原论文实验通过。
