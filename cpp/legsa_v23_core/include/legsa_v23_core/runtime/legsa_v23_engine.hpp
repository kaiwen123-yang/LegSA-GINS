#pragma once

#include "legsa_v23_core/config/gins_options.hpp"
#include "legsa_v23_core/filter/error_state_matrices.hpp"
#include "legsa_v23_core/state/filter_state.hpp"
#include "legsa_v23_core/state/gnss_types.hpp"
#include "legsa_v23_core/state/imu_types.hpp"
#include "legsa_v23_core/updates/measurement_update.hpp"

#include <deque>
#include <vector>

namespace legsa_v23_core {

// 中文说明：诊断更新记录只用于 N4H4D1 first-epoch/update-isolation，不作为性能结果。
struct DiagnosticUpdateRecord {
  int update_index = 0;
  double gnss_time = 0.0;
  double imu_pre_time = 0.0;
  double imu_cur_time = 0.0;
  int is_to_update_res = 0;
  Vector3 position_residual = zeroVector3();
  double position_residual_norm = 0.0;
  Vector3 velocity_residual = zeroVector3();
  double velocity_residual_norm = 0.0;
  double yaw_obs_deg = 0.0;
  double yaw_pred_deg = 0.0;
  double yaw_residual_deg = 0.0;
  std::string yaw_scheme_mode = "NONE";
  double yaw_effective_std_deg = 0.0;
  double h_pos_phi_norm = 0.0;
  double h_yaw_phi_value_or_norm = 0.0;
  Vector3 r_pos_diag = zeroVector3();
  Vector3 r_vel_diag = zeroVector3();
  double r_yaw = 0.0;
  double k_norm_pos = 0.0;
  double k_norm_vel = 0.0;
  double k_norm_yaw = 0.0;
  double dx_norm_before_update = 0.0;
  double dx_norm_after_update = 0.0;
  bool position_update_applied = false;
  bool velocity_update_applied = false;
  bool yaw_update_applied = false;
  double dx_norm_before_feedback = 0.0;
  double dx_pos_norm = 0.0;
  double dx_vel_norm = 0.0;
  double dx_phi_norm_deg = 0.0;
  double cov_trace_before = 0.0;
  double cov_trace_after = 0.0;
  double cov_min_diag_before = 0.0;
  double cov_min_diag_after = 0.0;
  bool state_feedback_applied = false;
};

// 中文说明：传播记录只保留前若干帧，帮助判断机械编排是否一开始就跳变。
struct DiagnosticPropagationRecord {
  int propagation_index = 0;
  double time_pre = 0.0;
  double time_cur = 0.0;
  double dt = 0.0;
  NavState nav_state;
  double dtheta_norm = 0.0;
  double dvel_norm = 0.0;
  double cov_trace = 0.0;
  double cov_min_diag = 0.0;
  double cov_max_diag = 0.0;
};

// 中文说明：LegSA 自有 v23-core EKF 主框架。N4H4C 已打通 GNSS 松组合更新和误差反馈。
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

  // 中文说明：按 KF-GINS-style IMU 主循环推进；GNSS 分支执行 EKFUpdate 后再 stateFeedback。
  void newImuProcess();

  // 中文说明：返回当前运行时间戳，单位秒。
  double timestamp() const;

  // 中文说明：返回当前名义导航状态；toy/update 输出不能作为性能证据。
  NavState getNavState() const;

  // 中文说明：返回当前 21 维滤波状态；N4H4C 是框架闭环，不代表 final_v23 parity。
  FilterState getFilterState() const;

  // 中文说明：返回运行后 manifest 选项；包含 yaw scheme_C 计数和 N4H4C 更新实现标记。
  GINSOptions getRunOptions() const;

  // 中文说明：返回 N4H4D1 诊断更新记录；默认运行不会生成性能声明。
  const std::vector<DiagnosticUpdateRecord>& getDiagnosticUpdateRecords() const;

  // 中文说明：返回 N4H4D1 诊断传播记录；用于定位 first-epoch 机械编排跳变。
  const std::vector<DiagnosticPropagationRecord>& getDiagnosticPropagationRecords() const;

 private:
  // 中文说明：判断 GNSS 更新时间与相邻 IMU 区间关系；N4H4C 使用 0/1/2/3 区分传播/更新顺序。
  int isToUpdate(double imu_time_1, double imu_time_2, double update_time) const;

  // 中文说明：将 IMU 增量按时间比例切分到 GNSS 更新时间；N4H4B 可运行插值但不做量测更新。
  static void imuInterpolate(const IMUData& imu1, IMUData& imu2, double timestamp, IMUData& midimu);

  // 中文说明：IMU bias/scale 补偿；输入已是 FRD body 增量，不能二次 FLU->FRD。
  void imuCompensate(IMUData& imu);

  // 中文说明：INS 机械编排传播 hook；N4H4B 填充 vel/pos/att propagation。
  void insPropagation(const IMUData& imupre, const IMUData& imucur);

  // 中文说明：F/G/Phi/Qd 构建 hook；只服务预测传播，不构建量测矩阵。
  void buildFGPhiQd(const IMUData& imucur);

  // 中文说明：EKF 预测 hook；执行 dx/P 预测传播，量测更新由独立 EKFUpdate hook 完成。
  void EKFPredict();

  // 中文说明：GNSS 综合更新 hook；汇总 position/velocity/yaw 量测并调用 EKFUpdate。
  void gnssUpdate(const GNSSData& gnss);

  // 中文说明：GNSS 位置更新 hook；输入 BLH(rad,rad,m)，输出 NED(m) 位置残差。
  void gnssPositionUpdate(const GNSSData& gnss);

  // 中文说明：GNSS 速度更新 hook；输入 NED(m/s)，不实现 raw Doppler。
  void gnssVelocityUpdate(const GNSSData& gnss);

  // 中文说明：GNSS yaw 更新 hook；输入 yaw(deg)，scheme_C 只做求解器门控。
  void gnssYawUpdate(const GNSSData& gnss);

  // 中文说明：EKFUpdate hook；Joseph form 只更新误差状态和协方差。
  void EKFUpdate();

  // 中文说明：状态反馈 hook；把 dx 反馈到名义状态并清零，避免 output-only correction。
  void stateFeedback();

  // 中文说明：协方差健康检查；N4H4B 检查有限值、对称性和非负对角线。
  void checkCov() const;

  // 中文说明：记录一次 GNSS update 前后的残差和 dx，仅用于诊断开关，不改变默认求解器数学。
  void recordDiagnosticUpdate(const GNSSData& gnss, int update_status, double imu_pre_time, double imu_cur_time,
                              bool measurement_enabled);

  // 中文说明：记录一次传播后的 PVA 和协方差统计，仅用于 first-epoch/mechanization 诊断。
  void recordDiagnosticPropagation(const IMUData& imupre, const IMUData& imucur);

  // 中文说明：标记最近一次诊断更新是否执行 stateFeedback；不修改 dx/P 数值。
  void markLatestDiagnosticFeedbackApplied();

  GINSOptions options_;
  FilterState filter_state_;
  std::deque<IMUData> imu_buffer_;
  std::deque<GNSSData> gnss_buffer_;
  std::vector<MeasurementBlock> pending_measurements_;
  ErrorStateMatrices last_matrices_;
  NoiseMatrix continuous_noise_ = diagonalNoiseMatrix(1.0e-6);
  std::vector<DiagnosticUpdateRecord> diagnostic_updates_;
  std::vector<DiagnosticPropagationRecord> diagnostic_propagations_;
  double diagnostic_pre_dx_norm_ = 0.0;
  double diagnostic_pre_cov_trace_ = 0.0;
  double diagnostic_pre_cov_min_diag_ = 0.0;
  double current_time_ = 0.0;
  bool initialized_ = false;
};

}  // namespace legsa_v23_core
