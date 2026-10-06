# 21+3 单姿态 clone：局部联合高斯实现结果

已实现独立 attitude_clone.py 与14项局部检查，首次执行14/14通过（pytest报告0.22s）。没有失败、修正重试或额外套件重复。命令、实际HEAD、依赖源码/测试SHA及持久日志见相邻receipt与ATTITUDE_CLONE_TEST_01.log。未读取真实raw/reference，未生成provider或运行CILS/native/导航/evaluator；未修改足对内核或EKF生产源码。

## 可调用范围

ErrorGaussian 保存21或24维误差均值、PSD协方差及本地clone/测量使用ID。augment_attitude_clone 由当前时刻与显式3×21 J确定性增广；允许奇异PSD，不floor。propagate_current 接当前Phi21/Q21，维护当前—clone cross；必须显式声明新增过程噪声相对既有状态零相关，未知/有色过程不静默支持。

update_measurement 接H21自动补clone零列，或完整H24；无论何种H都更新完整均值/P，非Schmidt。NoiseCorrelation必须显式选择零状态—测量cross的工作假设或给定完整C_en；联合[P,C;Cᵀ,R]需PSD，S需可逆正定，均不加载噪声过门。采用S=HPHᵀ+R+HC+CᵀHᵀ及对应广义Joseph两负cross项；不能将H21观察解释为clone gain应为0。

reset_after_full_feedback 要求实际应用向量与保存均值完全相同，拒绝clipping/部分反馈；以正号左乘Jl、调用者提供的position reset及来源，对完整P做GPGᵀ再清均值。模块本身不改变nominal pose，来源字符串不验证调用者真实执行了反馈；这是明确前置合同。marginalize_clone只取当前主块与均值，保留消费/退休记录，旧clone ID不得复活。

## 独立证据与反例

主oracle从独立标准正态latent生成初始状态、白过程噪声及测量，使用白化增广最小二乘QR一次求联合后验，不调用生产Kalman递推公式。其与“当前观测→相对足对观测”的顺序更新均值/协方差一致。第一条current-only观测已实际改变clone均值/Pcc，证明未漏掉普通GNSS/RD类更新的cross作用。

给定C_en的独立oracle用测量噪声n=D*w+eta构造共享误差；完整相关更新与QR后验一致。刻意把该C置零会改变后验；仅保留同一R不能修复。另一反例在创建clone的同一时刻使用相对脚对约束：正确cross下没有虚构的绝对姿态信息；删除Pxc会错误缩小当前姿态不确定性。

还验证：确定性clone秩亏；动态Phi/Q及历史时间不变；body0相对方向的共同world角gauge；24维完整retraction独立FD与所有reset cross；边缘化与错误Schur条件化的差别；噪声联合PSD、零S拒绝、维度、过程假设、因果时间、重复测量、clone生命周期和不可变数组。

## 尚未解决、不能推广的事项

这些检查证明的是显式线性/局部Gaussian工作模型，不是非线性精确后验、真实噪声校准、SDK独立性、航向完整性或实测效果。初始P、Phi/Q、E/K、四点Sigma、C_en及position reset仍由调用者绑定正确来源/坐标。given-C只证明数学联合PSD，不证明实际相关项正确；零模式是明确假设，不能从GNSS-free标签继承。R膨胀不是相关性修复。

测量仅支持当前时刻且已可用，迟到不回填；此内核不处理OOS更新。新增过程噪声的历史相关性不在当前模型内。测量ID ledger只防同一声明ID重复，不自动识别换ID后的同一物理足端数据，端点原始身份仍由上层保障。没有接触/滑移验收器、covariance gate、测量质量选择或导航准入。

采用判断：具备可供下一步受控集成使用的小型联合协方差内核；仍需root独立审查和真实来源/时序/相关性资格。当前没有接入native，不把局部14项通过视为三条V3完整窗非退化或航向收益证据。

Root 独立只读审查已逐读内核与14项测试，确认广义Joseph的cross符号、全部观测的clone更新、完整reset与边缘化一致；没有发现阻断局部内核提交的问题。本审查新增算法/测试调用为0，native接入仍未执行。
