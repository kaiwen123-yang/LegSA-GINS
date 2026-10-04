# 原文与作者材料边界

页码以PDF第一页起计。

| 原文 | 完整身份与关键页 | 本项目取得材料的边界 |
|---|---|---|
| [Yang et al., Satellite Navigation6:23,2025](https://doi.org/10.1186/s43020-025-00173-w) | 18页；SHA1b3a9c79c0285cdf6f41e95b3c3215218bc202df9978376e6bb453c83d693a6e；p3–5 Eq1–14、p10 Algorithm1、p12 Algorithm2、p13–16实验 | 有论文及引用OB_GINS模型；同文OiSAM作者完整程序未取得，不能由OB_GINS名称替代 |
| [Wen et al., NAVIGATION68(2):315–331,2021](https://doi.org/10.1002/navi.421) | 17页；SHA7b94be96194b77b4d4ddc128f7b0df0729765299c789a747a47a79edb322273f；p3–8 Eq1–32、p17 AppendixA | 选定TC-FGO关键因子实现；原文另三方案、XsensTi10实际输出/延迟/动态误差与全部原配置不齐 |
| [GNC-FGO, IEEE TVT71(1):297–310,2022](https://doi.org/10.1109/TVT.2021.3130909) | 14页；SHA7d13d97ccfb8b15d936f4c244579e220691fb252df3aa0f839d0bb33778dc11f；p3–6 Eq1–24/Algorithm1、p7–10实验 | GraphGNSSLib公开普通码/Doppler图入口不是原GNC作者完整程序证明；Eq21平方/Eq22未平方矛盾未获作者裁定 |

[OB_GINS](https://github.com/i2Nav-WHU/OB_GINS)固定commit `e96c69ae84d09f0e8c1c69bdd9323eaec020db86`提供真实Earth预积分；9上游源/header绑定，实际base/earth桥接编译。其一次完整demo通过只能证明OB_GINS程序执行，不能叫OiSAM原程序复现。作者ADIS16465/RTK输入357473–358073秒独立Oi连续诊断601节点，native无参考且没有精度评价，不代表论文所有600秒段/LeaderA15/原对照与计时。

## 宣称上限

1. 原文选定链一致性：状态、观测、残差、白化、求解顺序、边缘化、终止逐项有源码和执行证据；测试不能代替真实运行。
2. 机器人工程适配：坐标、物理点、噪声、初始化、缺测与数值实现允许适配，须记录额外信息量。分段A1初始化不能伪称一次原文初始化。
3. 作者原实验：还需原程序或经过可核等价判定的实现、确切配置/数据段/设备接口/真值/全对照/计时条件；当前这些没有全部闭合，不能保证全部取得。

GNC Eq21推出平方驻点是可独立验证的数学判断；原作者是否以该式产生发表结果仍未知。UBX实际`-lambda*D`、卫星速度/钟漂/Sagnac已核对，但原作者Doppler接口和速度/图协方差未获裁定。Wen ENU到机器人NED/FRD可作代数转换，不能据此声称实际厂家AHRS标定和动态性能相同。原GNC的水平mean/std/max及3Dmean不等于本项目RMSE。

“未取得”只陈述本项目证据状态，不推断材料全球不存在，也不承诺能取得作者全部程序或全部场地数据。
