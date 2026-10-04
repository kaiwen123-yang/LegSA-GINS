# 科学图资产与PPT使用入口

8个独立READY小块，共32张新图，全部提供300dpi PNG、PDF、可编辑文字SVG。每张图只回答一个科学问题；FIGURE_CATALOG逐项列dominant claim、panel role、caption、文件、分辨率和hash。32张最终PNG均实际分别打开；PDF/SVG由同一Figure导出，本子任务没有逐一渲染PDF。根任务对PPT成品的布局验收另记，不以这些PNG验收代替。

|顺序/块|科学问题与已有数据|推荐使用|
|---|---|---|
|01，4图|三个序列原Proposed/LC01全部H/yaw曲线、全部11自然配置|逐序列全窗曲线；LC01的不同初始化/物理点/几何审计边界不删除|
|02，4图|原BY2完整matched trajectory，以及原三序列roll/pitch/yaw全部误差|轨迹独立一页，姿态独立逐序列一页；原H/O轨迹未在检查的主评价根保留，不能拿后来的FGO图替代|
|03，4图|原CORE 541×11全部5951状态、尾部、四项严格配对消融、原ADD45×11全部495|全矩阵与不利个例作为主线；failure/finite分母和whole-window定义不省略|
|04，4图|动基线四预定条件×三序列，全部原paired历元误差/有效支持|每序列误差＋coverage一起展示，再用12条件图解释小RMSE与低覆盖关系|
|05，4图|原F02/F03 receiver velocity唯一功能开关对比，以及BY2全部1369 heading模式事件|速度作用非普遍改善；状态门不是truth标签，空innovation不补造|
|06，4图|EXT V2九个guardless真实运行的完整native-valid heading误差/原分母|保留64–104°的大RMSE；projected-heading定义及原始观测实例限制明确|
|07，4图|新3个Oi＋旧6个Wen/GNC位置，严格/分段/仅先验secondary支持|GNSS1同点但异输入，不做同输入排名；旧H0/O55不回填，新primary/secondary分开|
|08，4图|新FGO三序列GNSS1轨迹及只有Oi自行估计的yaw|轨迹、位置、姿态分开；1/3/7连续块与3286未收敛状态保留|

共使用89个唯一已存在文件路径，都是保存的评价/指标/运行配置/trace/收据，不重新求解、评价、bootstrap或读rawreference。原统计数值转录原CSV/JSON；轨迹只做固定anchor的坐标显示，不做拟合；每个源/副本/脚本/导出有独立hash。本任务新增的n/N转录、类别计数及绘图坐标转换不是新科学实验。

`EXISTING_ASSET_INVENTORY.csv`对六个明示保留图根做完整当前PNG/PDF/SVG元数据枚举，共120文件。只有其中6张相关旧PNG实际打开并评价可读性，其余明确标NO_NOT_ASSESSED，不能称全部旧图视觉审核。没有展开冷归档成员，也没有宣称整个磁盘所有图都已盘点。旧Fig05/08可作补充材料，但不能与新实例混成同一执行身份。

所有图保留原支持分母、无效/失败和数据量边界。注册历元或已观察输出覆盖不等于物理全时域500Hz连续覆盖；商业GNSS融合参考不等于独立真值；动基线固定标志不证明整数正确；EXT/FGO核心实现及工程适配不等于作者全部实验。照片不在本子任务中编辑。

构建脚本各在block内，目录索引可运行 `python -B build_figure_catalog.py`（只读现有资产并生成本目录索引；不依赖科学包）。CATALOG_RECEIPT对8份READY的全部成员、96导出及120旧资产metadata绑定；每份READY小块冻结后不再改动，提交/推送由根任务统一。
