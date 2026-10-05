# 已安装写作技能的来源核定、安全更新与使用规则

核查及更新日期：2026-10-05。本文只记录本地技能文件更新，不构成论文结果验收或投稿就绪判断。

## 1. 完成情况

已更新 **14 个此前安装的技能**：Yuan1z0825 来源的 10 个 Nature 技能，以及 Boom5426 来源的 manuscript-optimizer、scientific-writing、paper-workflow、nature-portfolio-playbook。新版明确引用 `../nature-shared/`，因此另外安装 **1 个必需共享依赖 nature-shared**；没有安装其他新的论文、专利或实验技能。原 `_shared` 目录保持原字节。

更新前，完整复制所有受影响旧技能与原共享目录，共 **354 个旧文件**，建立逐文件 SHA-256 清单和文本差异文件。更新后重新独立读取并校验 **445 个上游文件**，活动文件全部与所锁定上游字节一致；**224 个 manifest 本地文件引用**均存在，**11 个本地独有文件**仍保留且哈希不变。这 11 个文件均为此前的 Python 缓存，不能据此推定作者修改过技能正文。旧文件与上游差异的来源不全可追溯，故所有旧内容均保留，而不是假定它们全是旧版上游文件。

完整备份位于 `C:\Users\ykw\.codex\backups\writing-skills-20261005T041927Z`。其中 `before/` 可恢复旧内容；`BEFORE_MANIFEST.json`、`PLANNED_UPDATE_MANIFEST.json`、`PRIVATE_UPDATE_DIFF.patch`、`UPDATE_RECEIPT.json` 与 `POST_UPDATE_INDEPENDENT_FILE_RECHECK.json` 保存更新前后证据。完整技能内容、差异和私人缓存不放入项目 Git；本目录只提交本报告、精简台账与收据。

## 2. 明确来源和实际版本

第一来源为 [Yuan1z0825/nature-skills](https://github.com/Yuan1z0825/nature-skills/tree/6655831b8270e0bb48cbcdec22220a56c561de58)，锁定提交 `6655831b8270e0bb48cbcdec22220a56c561de58`。第二来源为 [Boom5426/Nature-Paper-Skills](https://github.com/Boom5426/Nature-Paper-Skills/tree/6ff6c50f5e44b83ba5185da52b3a33cd7c601b5e)，锁定提交 `6ff6c50f5e44b83ba5185da52b3a33cd7c601b5e`，其仓库 VERSION 为 **0.2.0**。后者四个单独技能未声明语义版本，使用提交和 SKILL 哈希确定身份，不能捏造单技能版本号。

这里的“来源”指技能发布者及其 Git 仓库，不意味着 Nature、Springer 或 IEEE 官方发布、认可这些技能。来源经远端仓库和实际克隆文件核定；市场目录仅用于线索发现，没有作为版本验收依据。

| 技能 | 实际版本变化 | 上游活动文件数 |
|---|---|---:|
| nature-academic-search | 2.0.0 → 2.0.0 | 48 |
| nature-citation | 2.0.0 → 2.1.0 | 15 |
| nature-data | 2.0.0 → 2.2.0 | 15 |
| nature-figure | 2.0.0 → 2.8.0 | 126 |
| nature-paper2ppt | 2.0.0 → 2.0.0 | 19 |
| nature-polishing | 6.1.0 → 6.6.0 | 33 |
| nature-reader | 2.0.0 → 2.1.0 | 20 |
| nature-response | 1.0.0 → 1.7.0 | 38 |
| nature-reviewer | 0.1.0 → 1.5.0 | 21 |
| nature-writing | 1.0.0 → 1.5.0 | 77 |
| manuscript-optimizer | not_declared → not_declared | 1 |
| scientific-writing | not_declared → not_declared | 8 |
| paper-workflow | not_declared → not_declared | 1 |
| nature-portfolio-playbook | not_declared → not_declared | 2 |
| nature-shared | not_declared → 1.6.0 | 21 |

`nature-academic-search` 和 `nature-paper2ppt` 版本数字未变，但文件确有差异，已经按本次锁定提交更新。因此“同版本号”不能解释为“没有新内容”。所有活动 SKILL 哈希、变化文件数量及来源提交见 `WRITING_SKILLS_UPDATE_MANIFEST.csv`。

## 3. 安全实施和验收边界

首先完成完整备份、备份哈希核验、待更新文件清单和文本 diff，再准备上游文件副本。已存在的技能目录被当前应用占用，第一次目录替换返回 WinError 5；当时尚未激活任何内容，重新核对原文件没有变化。随后改为逐文件临时副本加原子替换，并保留本地独有文件，最终通过全部上游字节和备份检查。

本次没有执行上游安装 shell、安装 Python 依赖、启用 MCP 服务或创建后台更新任务；也没有更改当前论文的估计器、输入、冻结结果、Git 提交或内存。验收覆盖文件身份和 manifest 引用，**没有宣称所有技能脚本、外部服务及论文工作流已做功能回归**。新版文件已经落地，当前会话的技能目录发现缓存是否即时刷新未验证；后续应用这些技能时需重新读取实际 SKILL 与相关片段。

若需要回退，先关闭占用这些技能目录的进程，将 `before/<skill>/` 中旧文件恢复到对应技能目录，并依据清单将仅本次新增的文件移到独立隔离目录，避免残留新版文件与旧入口混用。恢复后按 BEFORE_MANIFEST 重新核哈希。新增 nature-shared 有独立清单；只有确认没有其他活动技能引用它时才处理该依赖。这里给出可恢复路径，没有执行回退、删除或自动覆盖未知文件。

## 4. PaperSpine：已查新版本，保留当前 3.0.0

原套件的 `paper-spine-update/paperspine_version.json` 明确指向 [WUBING2023/PaperSpine](https://github.com/WUBING2023/PaperSpine)。实际执行旧更新器的只读检查，检测到 **3.0.0 → 4.0.1**。本次远端源码锁定 `f7e3dabaf499b2aef1eabdd1cd5d64f173d7dcc3`；官方兼容包为 [paperspine-compat-4.0.1.zip](https://github.com/WUBING2023/PaperSpine/releases/download/v0.4.0-alpha.2/paperspine-compat-4.0.1.zip)，已下载到私人检查目录，大小 2,845,712 字节、673 个 ZIP 成员，SHA-256 为 `c704bf4f5b0612a1d7b5c0d0dceebd946cfa802a1fdc0233062f3d57a689ba1d`。

实际将当前上游源码及该兼容包交给旧更新器的 `validate_repo`，两者均无法通过其旧布局校验。旧校验器期待 12 个分拆技能、README.zh-CN 和旧命令入口，新上游已改为不同布局。这是**旧更新器与新产品布局的兼容障碍**，不能简写成“最新版不存在”或“官方包损坏”。旧更新器还含直接替换目录的逻辑，故本次不执行其更新/迁移步骤。

**PaperSpine 仍保留 3.0.0**，12 个原 SKILL 哈希再次核对均未改变，版本清单未变。迁移应作为单独适配工作：先确定新产品入口、旧项目和配置转换方式，再独立备份整套 PaperSpine、预演恢复，最后验证旧工程能够打开及继续。用户已授权安全更新；本次保留是实际兼容性结果，不是授权缺失。

## 5. 后续如何使用

- 论文故事、核心贡献和章节组织：先用 paper-workflow 选择任务，再由 manuscript-optimizer / nature-writing 或 scientific-writing 执行；一次优先一个主流程，避免多个技能反复扩大稿件。
- 原论文理解与结构借鉴：nature-reader；文献查找与引文核验：nature-academic-search、nature-citation。核到原文和数据才能写实证主张。
- 英文语言与段落衔接：nature-polishing；同行审查模拟：nature-reviewer；审稿回复：nature-response；数据可得性：nature-data；图与报告幻灯片分别调用 nature-figure、nature-paper2ppt。
- **GPS Solutions 与 TIM 仍是本项目目标**。通用写作原则可以使用，Nature 的篇幅、体例及宣称强度不能覆盖目标期刊当前官方要求。Nature Portfolio 选刊技能只有明确讨论该系列时使用。
- 写作技能不补造实测外参、时钟漂移、独立参考、协方差或作者结果；不把 RMSE 改名为测量不确定度，不把解算层双天线航向改名为内部整数模糊度求解。已有共享参考、条件来源支持、负结果及原 V3 与后续诊断版本的区分仍必须保留。

本次没有改变论文科学结论，也不使当前稿件自动成为 submission-ready。
