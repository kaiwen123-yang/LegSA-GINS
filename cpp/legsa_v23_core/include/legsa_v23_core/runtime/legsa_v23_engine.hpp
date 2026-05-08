#pragma once

#include "legsa_v23_core/config/gins_options.hpp"
#include "legsa_v23_core/filter/error_state_matrices.hpp"
#include "legsa_v23_core/state/filter_state.hpp"
#include "legsa_v23_core/state/gnss_types.hpp"
#include "legsa_v23_core/state/imu_types.hpp"

#include <deque>

namespace legsa_v23_core {

// 中文说明：LegSA 自有 v23-core EKF 主框架。N4H4B 实现 INS 预测传播，量测更新留给 N4H4C。
class LegSAV23Engine {
 public:
  // 中文说明：保存配置和初始状态；坐标单位遵循 GINSOptions 的 BLH(rad,rad,m)/NED(m/s)。
  explicit LegSAV23Engine(const GINSOptions& options);

  // 中文说明：初始化名义状态和协方差占位；N4H4B/C 后续填充完整初始协方差策略。
  void initialize();

  // 中文说明：加入 IMU 增量样本；compensate=true 时执行 bias/scale 补偿，不做量测反馈。
  void addImuData(const IMUData& imu, bool compensate = false);

  // 中文说明：加入 15 列 GNSS 高层状态样本；不读取 RAWX/trace/final_v23 输出。
  void addGnssData(const GNSSData& gnss);

  // 中文说明：按 KF-GINS-style IMU 主循环推进；N4H4B 遇到 GNSS 只记录边界，不执行量测更新。
  void newImuProcess();

  // 中文说明：返回当前运行时间戳，单位秒。
  double timestamp() const;

  // 中文说明：返回当前名义导航状态；N4H4B 为 propagation foundation，不能作为性能证据。
  NavState getNavState() const;

  // 中文说明：返回当前 21 维滤波状态；N4H4B 只完成预测传播，不代表完整 EKF。
  FilterState getFilterState() const;

 private:
  // 中文说明：判断 GNSS 更新时间与相邻 IMU 区间关系；返回 -1/0/1。
  int isToUpdate(double imu_time_1, double imu_time_2, double update_time) const;

  // 中文说明：将 IMU 增量按时间比例切分到 GNSS 更新时间；N4H4B 可运行插值但不做量测更新。
  static void imuInterpolate(const IMUData& imu1, IMUData& imu2, double timestamp, IMUData& midimu);

  // 中文说明：IMU bias/scale 补偿；输入已是 FRD body 增量，不能二次 FLU->FRD。
  void imuCompensate(IMUData& imu);

  // 中文说明：INS 机械编排传播 hook；N4H4B 填充 vel/pos/att propagation。
  void insPropagation(const IMUData& imupre, const IMUData& imucur);

  // 中文说明：F/G/Phi/Qd 构建 hook；N4H4B 只构建预测矩阵，不构建量测矩阵。
  void buildFGPhiQd(const IMUData& imucur);

  // 中文说明：EKF 预测 hook；N4H4B 执行 dx/P 预测传播，不做量测更新。
  void EKFPredict();

  // 中文说明：GNSS 综合更新 hook；N4H4B 仍为 N4H4C TODO，不生成量测更新。
  void gnssUpdate(const GNSSData& gnss);

  // 中文说明：GNSS 位置更新 hook；输入 BLH(rad,rad,m)，N4H4A 只记录占位残差入口。
  void gnssPositionUpdate(const GNSSData& gnss);

  // 中文说明：GNSS 速度更新 hook；输入 NED(m/s)，N4H4A 不做完整 Kalman update。
  void gnssVelocityUpdate(const GNSSData& gnss);

  // 中文说明：GNSS yaw 更新 hook；输入 yaw(deg)，N4H4A 不做 yaw 性能或 parity claim。
  void gnssYawUpdate(const GNSSData& gnss);

  // 中文说明：EKFUpdate hook；N4H4B 明确不实现，N4H4C 再实现矩阵更新。
  void EKFUpdate();

  // 中文说明：状态反馈 hook；N4H4B 明确不实现，避免 output-only correction。
  void stateFeedback();

  // 中文说明：协方差健康检查；N4H4B 检查有限值、对称性和非负对角线。
  void checkCov() const;

  GINSOptions options_;
  FilterState filter_state_;
  std::deque<IMUData> imu_buffer_;
  std::deque<GNSSData> gnss_buffer_;
  ErrorStateMatrices last_matrices_;
  NoiseMatrix continuous_noise_ = diagonalNoiseMatrix(1.0e-6);
  double current_time_ = 0.0;
  bool initialized_ = false;
};

}  // namespace legsa_v23_core
