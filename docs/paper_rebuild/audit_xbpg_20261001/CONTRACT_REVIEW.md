# 路径、manifest、方法合约和进程异常审查

审查基线 eb3cbed；全文语义阅读的11个文件见 CONTRACT_COVERAGE.csv。这里只检查源代码/合约，动态输入全部为临时目录中的合成文件，没有启动历史控制器或旧矩阵。正式 v3/v2.1 的进程包装确实导入此处 subprocess_guard；其它 CLEAN0/CLEAN1 合约不能自动当成当前全部协议的实现。

## paths.py（310行）

- 12–46 异常类型、legacy目录分量/连续路径序列、两个CLEAN1协议suffix映射；是路径策略而非内容泄漏检测。49–67 CleanPaths 保存8个显式路径，hash lock和port exe由固定相对目录推导，不查询PATH。
- 70–90 `_simple_scalar` 去首尾引号、bool/null/int/float转换；不会执行Python文本，但不是完整YAML。93–117 fallback按缩进维护mapping栈，重复键覆盖，任何`#`后文字先截掉，包括引号内的合法路径字符。无PyYAML环境下 `"<SCRATCH>/原始#1"` 被改成不闭合字符串；P-CON-01直接原函数反例。
- 120–138 `load_yaml_mapping` 先JSON，失败则PyYAML safe_load，缺依赖才fallback；根节点必须dict。三个parser分支对重复键、浮点和列表的接受语义不同，不能由文件扩展名保证一致。环境中有PyYAML，故本轮本地配置没有走坏fallback；没有声称当前路径已损坏。
- 141–150 `_path_value` 拒空/占位/Windows绝对路径、要求POSIX绝对路径并resolve。153–156 `is_within` 按resolve后的父链判断，能拒普通symlink逃逸。159–174 legacy_reason对原始字符串分量casefold匹配，不读payload。
- 177–203 guard先检查原始路径的legacy分量，再resolve和检查root及文件属性；**没有再次对resolve结果执行legacy denylist**。root内新名字symlink指向同root/experiments/old.txt会过；测试只在scratch生成同构路径，没有打开旧项目目录（P-CON-02）。仍可拒指向root外的symlink，不夸成所有路径保护失效。
- 206–269 load_clean_paths解析7个必填路径，raw/clean、provider/runtime互不包含；BY2文件存在性与目录型检查区分，CLEAN1 suffix一致时要求精确子树。未校验code_root与raw/clean互斥，也未给全部其它协议suffix设等价映射；属于适用范围，不在本轮扩张策略。
- 272–297 assert_clean1_path_contract另绑定执行worktree、BY2规范相对路径；300–310 clean1_stage_root按两个明确协议选择输出路径。将这两个BY2专用入口直接套XB会失败，不应通过偷偷改变raw/几何来“修复”。

## manifest.py（222行）

- 15–52 required/forbidden字段限定CLEAN0 real BY2。59–86 git_code_state读取HEAD和包括未跟踪的porcelain，命令失败抛ManifestContractError，不能将本轮29个旧untracked藏成clean。89–102 stream SHA256/UTF-8 text SHA，不做科学身份推断。
- 105–119 atomic writer同目录mkstemp、flush+fsync、replace，finally移除剩余temp；这是完整写入保护，**不是禁止覆盖已封存文件的保护**，也没有allow_nan=False。调用端必须做exclusive/stage约束。本轮旧文件没有通过该函数写入。
- 122–141 hash lock检查列名、非空、安全相对路径、重复条目，size/hash格式到后一步检验。144–171 verify_raw_sources逐指定路径校验resolve归属、size、真实SHA，不以hash字段长度冒充实际验签；空relative集合返回空dict，由manifest非空mapping gate补充。
- 174–216 validate_run_manifest检查字段存在、BY2角色、严格False flags、零旧输入、非空hash映射、hash长度和部分非空身份。**64个`z`也通过SHA256语法检查**（P-CON-03），而schema明确只许十六进制。实际audit随后重算hash/HEAD时可以拦住，不能说此反例能伪造完整运行证明。schema_version、algorithm_id内容也没有在此函数绑定schema。219–222 assert只是把issues合并抛出。
- 模块强制real_by2_raw、合成false是CLEAN0专用边界；JSON schema允许更多data_mode，是两层适用范围不同。本轮XB/SYNTHETIC receipts明确单列，未冒用这项BY2 validator通过证明。

## methods.py（402行）与 methods.yaml（113行）

- 15–181冻结四方法顺序、六开关、禁用机制、GNSS2−GNSS1横向+90°约定、输入角色、允许变化字段和共同hash字段。F01有RV、F02无RV，F03恢复RV；因此代码直接反证“严格一次只增一项”。yaml中的0.2–0.6m gate明确是BY2专用，非XB安装事实。
- 184–207异常/MethodCatalog/helper；method取浅拷贝，features再拷贝，嵌套payload并非深度不可变，调用者不能当冻结对象任意改它。210–247 catalog验证schema、全部键、顺序、默认值和每方法字典等于源码冻结定义后计算文件hash；dict equality中1与True相等，后续effective检查用`is`，有更严的第二层。
- 250–266输出角色+开关矩阵，267–279 dump为YAML或JSON；这是新建方法快照，不是允许对正式runtime config做YAML round-trip。282–340 effective审计检查共同字段、features、basic std、禁用flags、未知字段及跨方法差异。`algorithm_id`可变化却**没有要求等于外层方法键**，F01 flags配LegSA_Paper_V1标签仍passed（P-CON-04）；构造器当前通常正确填写，历史错标签触发未证明。返回明确preexecution层，仍要求postparse检查，不能称已测native生效值。
- 343–349 assert汇总抛出；352–390写snapshot、hash、matrix和audit，未传effective配置则passed=false/PENDING，不假成功；输出目录exist_ok且write覆盖由上层冻结约束负责。394–395 canonical hash排序紧凑JSON；398–402请求方法必须精确冻结顺序。

## audit.py（181行）

- 22–48本机路径regex与文本枚举；普通文件和ZIP内白名单后缀仅检查路径泄漏，跳symlink，不检查凭据/二进制内容/所有嵌套压缩。这不是完整发布敏感信息扫描。
- 51–80运行root归属、8个必要非空文件、manifest parse；manifest缺失/不可解析立即返回已有失败，未把异常抹成成功。81–118独立执行manifest/raw真实hash/provider真实hash/config legacy文本与config hash检查；provider guard的allowed root是clean_root，并不只限provider_root，`../`在clean内可通过，hash应由调用合约锁定。需要避免把根约束夸成provider目录精确绑定。
- 120–148读取provider lineage，核当前HEAD/dirty、generator commit/config/local config hash；比较实际文件hash比声明强，但不检查每个子进程真实open。这是早期CLEAN0审计，不能替代v3 strace证据或追完整上游trace独立性。
- 150–177 smoke metric必须专用namespace、非论文claim且有行；terminal须PASS；可选export路径泄漏检查。NAV/STD数值、端点和PSD没有在本文件验证，来自其它层。180–181 `all`对空列表返回True，正常audit_clean_runtime至少写required_files行，故仅列通用helper误用风险，不称当前流程绕过已确认。

## subprocess_guard.py（66行）、__init__.py（16行）

- 包初始化仅导出manifest/path接口，不启动native、不读取传感器。
- guard 12–37 Popen新session、UTF-8 replacement、stdout/stderr PIPE；OSError转127且保留错误。38–45正常返回完整returncode/stdout/stderr；没有把非零退出改成成功。46–66 timeout先SIGTERM整个进程组，宽限后SIGKILL、wait/collect，返回124并追加原因，处理kill时进程已退出的race。测试用真实Python子进程和孙进程证明进程组终止，以及launch127、原始exit7/stderr保留。
- PIPE会把全部输出积存在内存；频繁日志/无限输出需上层控制，不能由timeout证明内存安全。进程组不是对子进程自行setsid逃逸的通用沙箱，本轮native没有新增该行为。

## 配置、既有测试及实际结果

- manifest_schema.yaml（87行）逐属性/条件定义schema：SHA regex、禁止角色、data_mode与合成标志联动；additionalProperties=true允许扩展但不保证扩展字段native解析。CLEAN0 Python validator只执行其子集，不是jsonschema自动校验器。
- DATA_PATHS.local.example.yaml（16行）7个原路径加BY2H/BY2O各2个别名，无真实用户路径。当前load_clean_paths忽略额外键，特定sequence registry再解释，不是静默把新数据映射BY2。
- tests/paper_rebuild/test_paths.py（57行）两测试在tmp生成合约；正常路径+直接legacy/root外symlink拒绝通过，未覆盖同root内symlink指向legacy，此处新增最小反例补齐。
- tests/paper_rebuild/test_manifest.py（93行）真实tmp hash修改前校验、禁止flag检查通过；第73–93行`test_tracked_config_contracts_match_clean_runner`仍断言旧7键，实际example已有4个BY2H/O键，**本轮实际失败**。这是测试与已扩展样例失配P-CON-05，不是滤波器精度失败；保留原测试不改成绿。

复现命令：`PYTHONPATH=src python3 -m pytest -q -rx tests/paper_rebuild/audit_xbpg/test_contract_findings.py tests/paper_rebuild/test_manifest.py tests/paper_rebuild/test_paths.py tests/paper_rebuild/test_clean1_formal_contract.py::test_process_guard_terminates_whole_group_and_classifies_launch_failure`。

实际 **1 failed / 9 passed / 4 strict-xfailed，pytest退出1**，完整stdout/stderr/命令收据在 `<AUDIT_ROOT>/verification/contract_tests.*`。后一个既有测试文件只审/执行该进程组函数，不升级整份大文件为语义完成。4个xfail证明旧合约缺口，9个pass含正对照；不能合称“全仓CI通过”。
