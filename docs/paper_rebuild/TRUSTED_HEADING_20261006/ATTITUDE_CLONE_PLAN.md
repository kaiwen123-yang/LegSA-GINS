# 单历史姿态 clone：联合协方差局部计划

范围：独立 Python research Gaussian 内核，21 当前误差维度加至多一个 ECEF 姿态 clone3。保持已审 body0 相对脚对残差，不修改 foot_pair_direction/native/provider。最多14个唯一局部pytest，0真实/raw/reference/CILS/nav/evaluator。失败保留，修正后仅重跑受影响检查。全部在Ubuntu-22.04 WSL。

## 固定接口与条件

误差状态均值和P不可变拷贝，维度只21或24；时间、clone_id和本地测量使用ID明确。clone由当前时刻确定性增广J创建，P允许奇异PSD，不floor；退役取Pxx边缘主块，不能Schur条件化或复活旧clone ID。

预测使用原当前Phi21/Q21，clone常值、cross Pxc←Phi Pxc。需要显式声明新增process noise相对既有状态/clone零相关工作模型；未知或已知不满足不能静默假定支持，本内核不实现有色IMU过程。

测量H21自动补零clone列，或显式H24；更新全部均值/P，普通GNSS/RD类current-only观测也通过cross更新clone。使用dz−H mean创新，不能把已减均值的innovation再次当dz。

NoiseCorrelation合同显式选择零C_en工作假设或完整给定C_en，并记录source/qualification说明；零模式不接收另一个被忽略C。给定C必须完整24×m（有clone时），不能把21×m补零；验证[P,C;Cᵀ,R]联合PSD。S=HPHᵀ+R+HC+CᵀHᵀ，K=(PHᵀ+C)S⁻¹；用相应广义Joseph后验。S不可解则拒绝，不floor。来源和统计独立不会从GNSS-free字样继承。

reset要求调用者确认实际反馈向量与完整mean完全一致，不支持clipping后清零。输入当前position reset 3×3及来源（原NED/BLH约定DR(new)DRi(old)），姿态使用已审正号Jl；whole GPGᵀ包含全部cross。此模块不改变nominal pose，reset仅在调用者已完成同向量名义反馈的合同下有意义；局部Jacobian不称精确非线性后验。

## 独立检查（上限14）

确定性增广/奇异PSD；动态Phi/Q后current-only与foot联合测量对独立latent+QR批量Gaussian；给定C_en的相关噪声batch oracle；丢C和丢current-clone cross的错误反例；相对脚对共同旋转gauge；完整retraction独立FD reset与cross；边缘化而非条件化；过程假设/时序/维度域；联合noise PSD、显式噪声合同；duplicate测量/clone生命周期；不可变结果与来源边界。没有靠复制生产公式做唯一正确性证明。

交付只证明给定工作模型下的局部联合Gaussian实现与必要反例，不证明SDK独立、错误固定风险、绝对航向或真实导航增益。后续能否接入仍需root独立审查及另外登记，当前不启动真实流程。
