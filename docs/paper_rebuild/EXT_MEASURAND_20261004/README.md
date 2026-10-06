# EXT航向量定义：完成的定点解释检查

原九次EXT V2 native没有重跑，原Euler航向成绩和全部失败/分母未改变。本检查在3次新FGO native全部封存并由root核验后，才各读一次既定参考；注册合同先于这些读取，绝无新估计、调参、时间拟合或安装拟合。

## 结果与含义

按照已声明body -y侧向基线及冻结reference姿态轴，名义投影角与Euler yaw的差在原7689个正式有效评分键上，RMSE为0.031092–0.043577deg，最大绝对值0.454407deg。九行成绩改变最大0.004278deg。**这项名义倾斜量差不能解释原64–104deg的大航向误差。**

所有7689键原样保留，没有竖直/近竖直reference投影被删除；原各方法期望槽位分母总计13815。原9个Euler RMSE重算最大差1.421085e-14deg，原error逐键差0；9个SPEC/error/metrics绑定文件保持原hash。

|序列|内部执行ID|原Euler RMSE(deg)|名义投影RMSE(deg)|有效/原分母|量差RMS(deg)|
|---|---|---:|---:|---:|---:|
|BY2|EXT01|85.015472|85.015848|980/1370|0.043577|
|BY2|EXT02|85.179795|85.180363|961/1370|0.043501|
|BY2|EXT03|79.931845|79.932328|541/1370|0.038105|
|BY2H|EXT01|89.127388|89.125772|1059/1350|0.035983|
|BY2H|EXT02|89.192923|89.191274|1029/1350|0.036284|
|BY2H|EXT03|63.994556|63.995662|467/1350|0.040759|
|BY2O|EXT01|81.273465|81.275119|1173/1885|0.031603|
|BY2O|EXT02|81.486071|81.487708|1210/1885|0.031092|
|BY2O|EXT03|103.754200|103.758478|269/1885|0.032787|

这是指定实现、指定输入和声明几何下保留的负结果。安装天线次序、真实机体轴/IMU安装旋转及实体测量仍未独立核定，共享GNSS参考也不是独立truth。不能从本检查进一步推导所有原方法普遍不适用，亦不因误差很大就擅自改符号、旋转90deg或挑样本提升成绩。EXT01/02/03的论文方法对应见[原复现说明](../hext/EXT_REPRODUCTION/v2_fix/README.md)。RTKLIB、动基线、LC01本检查没有重跑。

## 独立验收与位置

root用stdlib独立核全部7689键、45个摘要字段，差为0；实际OS openat日志核reference各一次。检查器不导入科学pipeline、不再打开rawreference、不启动native/evaluator。原公式已有7个独立旋转向量算例及竖直拒绝检查。

- [合同](PROTOCOL.md)、[事前绑定](PREREGISTRATION.json)、[9行原值汇总](SUMMARY.csv)。
- [执行收据](RESULT_RECEIPT.json)、[FGO native封存放行](ROOT_NATIVE_SEAL_REVIEW.json)、[独立算术/访问核验](ROOT_OFFLINE_RESULT_REVIEW.json)。
- 本次实际root检查脚本逐字节归档在local_review_scripts，含本机stage路径，不冒称通用CLI或作者程序；真正科学解释脚本是同目录nominal_ext_measurand_diagnostic.py。
- 完整7689行派生errors及OS日志留本机 `<G_PROJECT>/修复_20261004/EXT_MEASURAND_DIAGNOSTIC/`，其SHA在收据中；未删除原九次输出。
