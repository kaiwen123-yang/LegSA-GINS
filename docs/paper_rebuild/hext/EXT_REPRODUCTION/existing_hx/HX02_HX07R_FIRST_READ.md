# HX02 / HX07R 已有结果：首批实际读取

本首批索引有629条表行/运行/评价记录，文件约0.96 MB；它是完整HX收集的先交付子集，不能替代其余阶段。入口 [HX02_HX07R_FIRST_INDEX.csv](HX02_HX07R_FIRST_INDEX.csv)，逐文件读取与哈希回执 [HX02_HX07R_FIRST_RECEIPT.json](HX02_HX07R_FIRST_RECEIPT.json)，只读脚本 [collect_hx02_hx07r_first.py](collect_hx02_hx07r_first.py)。原数值完整精度转录，JSON数值词元保存为字符串；未知值不填0。脚本没有导入科学模块，没有新native/evaluator/provider调用，没有读NAV、pos、heading、error_series或reference正文。

实际存储位于 `<CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY/` 与 `.../HX07R/`。它们是当前可打开的归档目录，不是待解压ZIP。索引保留当前G盘路径别名；旧结果中的scratch路径仍标为历史记录，不能据旧scratch消失断言G盘结果丢失。本机根映射见ignored `configs/paper_rebuild/EXT_REPRODUCTION_ROOTS.local.json`。

HX02的 `EXTERNAL_FIVE_CATEGORY_TABLE.csv` 已全文读取480行，包含63个 method/config/sequence/start_mode 展示组合；它们既有本次24个原生运行，也引用旧LC01/EXT05C与内部V3数字及未实现方法占位，**480行和63组合均不是原生运行次数**。24个真实RUNS目录均取得COMMAND/终态及存在的评价JSON；原调用回执为24 native、21参考评价、3无参考覆盖评价。GINav的D8失败、Hartley BY2H两配置异常与EXT04零有效航向均保留，不能把未生成指标或UNAVAILABLE当0误差。后来的官方Hartley属于HX02E独立版本。

HX02 BY2原值示例（`CSV:data_row`为不含表头的数据记录序号）：EXT01行1/2/6分别为 availability `0.7153284671532847`、valid yaw RMSE `120.36002862722869°`、hold yaw RMSE `117.8666282180735°`；EXT04_FAR行39为availability `0.0`，行40/44误差为 `UNAVAILABLE`；RTKLIB行63/64/68分别为 `0.11167883211678832`、`14.566166015767248°`、`58.24105244214757°`。指标使用各方法原生航向支持，不能与IMU点位置误差合成统一精度排行。

HX07R取得13个目录的记录：四变体×三序列对应12份原生COMMAND，另一个BY2 V0-convbin仅是额外评价对照。原回执明确12次rnx2rtkp、13次heading评价/参考读取；本轮这些调用均为0。以下全部数字来自当前 `HX07R/SUMMARY.csv`，行号也是数据记录序号。

|行|变体|序列|有效/注册配对历元|valid RMSE（deg）|hold RMSE（deg）|
|---:|---|---|---|---:|---:|
|1|V0|BY2|153/1370|14.566166015767248|58.24105244214757|
|2|V0|BY2H|179/1350|27.0111690896743|55.117992602685284|
|3|V0|BY2O|112/1885|23.138949511295703|129.98822323173354|
|4|V0E|BY2|194/1370|20.646991249762408|53.423210579873135|
|5|V0E|BY2H|217/1350|31.263814132161954|65.42618640965112|
|6|V0E|BY2O|231/1885|20.40291146083135|34.735075882390845|
|7|V1|BY2|154/1370|14.611254467126965|57.336597334463875|
|8|V1|BY2H|186/1350|12.732971393509587|42.43822741854859|
|9|V1|BY2O|117/1885|21.78190065953815|85.86595587186044|
|10|V2|BY2|60/1370|4.511760777149032|32.368884900817754|
|11|V2|BY2H|149/1350|10.62299168537043|39.641752392726964|
|12|V2|BY2O|93/1885|19.205502081410785|96.11424444748205|
|13|V0-convbin|BY2|157/1370|14.361272071540819|58.96811193411137|

V0/V0E/V1/V2与V0-convbin保持独立身份；有效率和有效/保持误差具有不同支持。此处不重新计算任何性能，也不从变体差值宣称某星座、模糊度策略或文献公式的因果作用。旧HX07的157对153、超出±2门的硬停保留为输入历史不同的原记录，不能被HX07R的新评价反向改写为旧阶段已通过。

首批仍未交付的部分：HX02E、HX03/R2、HX05与旧HX07全体索引；HX02/HX07R其余阶段汇总/分段/残差表正在同一只读总收集里登记。大payload本阶段只核位置与文件元数据，不宣称其正文/CRC已完整读取。方法忠实复现、数学审查、重新实现和新增科学执行均未开始。

本轮索引字段更正：根代理最初把目录第4字段当作纯起点模式，随后核对 `HX02_CONTRACT_V1.yaml#/runs/run_directory` 与 `sequences`，恢复原 CASE 词。HX02 的 `case_id` 为 BY2=`C00`、BY2H=`CONTRACT_START`、BY2O=`FILE_START`；独立 `start_policy` 分别为 `FILE_START`、`CONTRACT_START`、`FILE_START`。这只更正本轮索引映射，不修改原运行身份或科学记录。RUN 行仍分别保留原 native_classification、runner_terminal_status 和 DONE.provenance.code_commit。
