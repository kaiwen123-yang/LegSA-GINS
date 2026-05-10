// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"

#include "legsa_v23_port_core/common/earth.hpp"
#include "legsa_v23_port_core/common/rotation.hpp"
#include "legsa_v23_port_core/factors/raw_doppler_factor.hpp"
#include "legsa_v23_port_core/kf_gins/insmech.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <utility>

namespace legsa_v23_port_core {
namespace {

Vec3 vecFromDx(const std::vector<double>& dx, std::size_t offset) {
  return makeVec3(dx.at(offset), dx.at(offset + 1), dx.at(offset + 2));
}

void setDiagonalBlock(Matrix& matrix, std::size_t offset, const Vec3& std_value) {
  for (std::size_t i = 0; i < 3; ++i) {
    matrix(offset + i, offset + i) = std_value[i] * std_value[i];
  }
}

void setDiagonalBlockValue(Matrix& matrix, std::size_t offset, const Vec3& value) {
  for (std::size_t i = 0; i < 3; ++i) {
    matrix(offset + i, offset + i) = value[i];
  }
}

Matrix3 diag3(const Vec3& value) {
  Matrix3 out = zeroMatrix3();
  out[0][0] = value[0];
  out[1][1] = value[1];
  out[2][2] = value[2];
  return out;
}

Vec3 positiveStd(const Vec3& value, double floor_value) {
  return makeVec3(std::max(std::fabs(value[0]), floor_value),
                  std::max(std::fabs(value[1]), floor_value),
                  std::max(std::fabs(value[2]), floor_value));
}

}  // namespace

GIEngine::GIEngine(PortOptions options)
    : options_(std::move(options)),
      Cov_(RANK, RANK, 0.0),
      Qc_(NOISERANK, NOISERANK, 0.0),
      dx_(RANK, 0.0) {
  initializeQc();
}

// 中文说明：初始化 PVA、姿态四元数、IMU 误差和协方差，不读取 final_v23 输出。
void GIEngine::initialize(const NavState& initial_state) {
  pvacur_ = initial_state;
  pvacur_.time = initial_state.time;
  pvacur_.qbn = Rotation::euler2quaternion(pvacur_.euler_rad);
  pvacur_.cbn = Rotation::quaternion2matrix(pvacur_.qbn);
  imuerror_ = options_.init_imu_error;
  pvacur_.imu_error = imuerror_;
  pvapre_ = pvacur_;
  timestamp_ = pvacur_.time;
  initializeCovariance();
  zeroVector(dx_);
  initialized_ = true;
}

// 中文说明：raw Doppler velocity measurements 必须来自 RAWX+satellite-state provider，
// 不能来自 NAV-PVT velocity、.gnss vn/ve/vd、trace 或 final_v23 输出。
void GIEngine::setRawDopplerVelocityMeasurements(const std::vector<RawDopplerVelocityMeasurement>& measurements,
                                                 const RawDopplerFactorStatus& status) {
  raw_doppler_measurements_ = measurements;
  raw_doppler_status_ = status;
  raw_doppler_status_.code_present = true;
  raw_doppler_status_.epoch_count = measurements.size();
  if (raw_doppler_status_.valid_epoch_count == 0) {
    raw_doppler_status_.valid_epoch_count = static_cast<std::size_t>(std::count_if(
        measurements.begin(), measurements.end(), [](const RawDopplerVelocityMeasurement& measurement) {
          return measurement.provider_status == "available";
        }));
  }
  raw_doppler_status_.solver_enabled =
      options_.raw_doppler_config.enable_raw_doppler && status.solver_enabled && status.provider_status == "available";
  if (raw_doppler_status_.factor_source.empty() || raw_doppler_status_.factor_source == "none") {
    raw_doppler_status_.factor_source = options_.raw_doppler_config.raw_doppler_factor_source;
  }
  if (!raw_doppler_status_.solver_enabled && raw_doppler_status_.provider_status.empty()) {
    raw_doppler_status_.provider_status = "provider_missing_sat_state_export";
  }
}

// 中文说明：addImuData 保持 reference 的 imupre/imucur 滚动缓冲；首帧可选择预补偿。
void GIEngine::addImuData(const ImuData& imu, bool compensate) {
  imupre_ = imucur_;
  imucur_ = imu;
  if (compensate) {
    imuCompensateInPlace(imucur_);
  }
}

// 中文说明：GNSS 是 15 列松组合观测，不是 raw pseudorange/Doppler。
void GIEngine::addGnssData(const GnssData& gnss) {
  gnssdata_ = gnss;
  gnssdata_.isvalid = true;
}

int GIEngine::isToUpdate() const {
  const double updatetime = gnssdata_.isvalid ? gnssdata_.time : -1.0;
  return isToUpdate(imupre_.time, imucur_.time, updatetime);
}

// 中文说明：res=0/1/2/3 与 KF-GINS runtime loop 对齐，控制 update 插入位置。
int GIEngine::isToUpdate(double imutime1, double imutime2, double updatetime) const {
  if (std::fabs(imutime1 - updatetime) < TIME_ALIGN_ERR) {
    return 1;
  }
  if (std::fabs(imutime2 - updatetime) <= TIME_ALIGN_ERR) {
    return 2;
  }
  if (imutime1 < updatetime && updatetime < imutime2) {
    return 3;
  }
  return 0;
}

// 中文说明：IMU 内插只拆分增量，不在这里做补偿；res=3 的补偿由后续传播负责。
ImuData GIEngine::imuInterpolate(const ImuData& previous, ImuData& current, double time) const {
  if (previous.time > time || current.time < time) {
    return current;
  }
  const double lambda = (time - previous.time) / (current.time - previous.time);
  ImuData midimu = current;
  midimu.time = time;
  midimu.dtheta = scale(current.dtheta, lambda);
  midimu.dvel = scale(current.dvel, lambda);
  midimu.dt = time - previous.time;
  midimu.compensated = false;
  current.dtheta = subtract(current.dtheta, midimu.dtheta);
  current.dvel = subtract(current.dvel, midimu.dvel);
  current.dt = current.dt - midimu.dt;
  current.compensated = false;
  return midimu;
}

ImuData GIEngine::imuCompensate(const ImuData& imu) const {
  ImuData out = imu;
  imuCompensateInPlace(out);
  return out;
}

// 中文说明：IMU compensation 按 bias*dt 和 scale 分母补偿；process_data 已完成 FLU->FRD，不能二次转换。
void GIEngine::imuCompensateInPlace(ImuData& imu) const {
  if (imu.compensated) {
    return;
  }
  imu.dtheta = subtract(imu.dtheta, scale(imuerror_.gyrbias, imu.dt));
  imu.dvel = subtract(imu.dvel, scale(imuerror_.accbias, imu.dt));
  imu.dtheta = cwiseDivide(imu.dtheta, add(makeVec3(1.0, 1.0, 1.0), imuerror_.gyrscale));
  imu.dvel = cwiseDivide(imu.dvel, add(makeVec3(1.0, 1.0, 1.0), imuerror_.accscale));
  imu.compensated = true;
}

void GIEngine::insPropagation() {
  insPropagation(imupre_, imucur_);
}

// 中文说明：传播先补偿 imucur，再机械编排，再构造 F/G/Phi/Qd 并 EKFPredict。
void GIEngine::insPropagation(ImuData& imupre, ImuData& imucur) {
  imuCompensateInPlace(imucur);
  INSMech::insMech(pvapre_, pvacur_, imupre, imucur);
  Matrix F(RANK, RANK, 0.0);
  Matrix G(RANK, NOISERANK, 0.0);
  Matrix Phi(RANK, RANK, 0.0);
  Matrix Qd(RANK, RANK, 0.0);
  buildErrorStateMatrices(imucur, F, G, Phi, Qd);
  EKFPredict(Phi, Qd);
  timestamp_ = imucur.time;
  ++propagation_count_;
}

void GIEngine::gnssUpdate() {
  gnssUpdate(gnssdata_);
}

// 中文说明：GNSS update 顺序为 position、receiver-native velocity、yaw；N5D velocity stress
// 只用于诊断 raw Doppler 独立约束能力，不代表真实传感器故障模型，也不作为论文性能结果。
void GIEngine::gnssUpdate(GnssData& gnss) {
  if (!gnss.isvalid) {
    return;
  }
  applyPositionUpdate(gnss);
  if (gnss.has_velocity && receiverVelocityUpdateEnabledForTime(gnss.time)) {
    GnssData stressed_gnss = receiverVelocityStressView(gnss);
    applyVelocityUpdate(stressed_gnss);
  }
  if (gnss.has_yaw && options_.yaw_scheme_C_enabled) {
    applyYawUpdate(gnss);
  }
  // 中文说明：raw Doppler auxiliary velocity factor 与 GNSS epoch 对齐，并在 stateFeedback 前进入 EKF。
  applyRawDopplerUpdateForTime(gnss.time);
  gnss.isvalid = false;
  ++update_count_;
}

void GIEngine::EKFPredict() {
  Matrix F(RANK, RANK, 0.0);
  Matrix G(RANK, NOISERANK, 0.0);
  Matrix Phi(RANK, RANK, 0.0);
  Matrix Qd(RANK, RANK, 0.0);
  buildErrorStateMatrices(imucur_, F, G, Phi, Qd);
  EKFPredict(Phi, Qd);
}

// 中文说明：EKFPredict: Cov = Phi Cov Phi^T + Qd, dx = Phi dx。
void GIEngine::EKFPredict(const Matrix& Phi, const Matrix& Qd) {
  Cov_ = add(multiply(multiply(Phi, Cov_), transpose(Phi)), Qd);
  dx_ = multiply(Phi, dx_);
}

// 中文说明：EKFUpdate 使用 dx += K(dz-Hdx) 和 Joseph covariance form。
void GIEngine::EKFUpdate(const std::vector<double>& dz, const Matrix& H, const Matrix& R) {
  if (H.cols != RANK || dz.size() != H.rows || R.rows != H.rows || R.cols != H.rows) {
    throw std::runtime_error("EKFUpdate dimension mismatch");
  }
  const Matrix Ht = transpose(H);
  const Matrix S = add(multiply(multiply(H, Cov_), Ht), R);
  const Matrix K = multiply(multiply(Cov_, Ht), inverse(S));
  const std::vector<double> Hdx = multiply(H, dx_);
  std::vector<double> residual(dz.size(), 0.0);
  for (std::size_t i = 0; i < dz.size(); ++i) {
    residual[i] = dz[i] - Hdx[i];
  }
  const std::vector<double> delta = multiply(K, residual);
  for (std::size_t i = 0; i < dx_.size(); ++i) {
    dx_[i] += delta[i];
  }
  const Matrix I = identityMatrix(RANK);
  const Matrix IKH = subtract(I, multiply(K, H));
  Cov_ = add(multiply(multiply(IKH, Cov_), transpose(IKH)), multiply(multiply(K, R), transpose(K)));
}

// 中文说明：stateFeedback 将误差状态反馈到导航状态；位置/速度减，姿态 qpn 左乘，bias/scale 加。
void GIEngine::stateFeedback() {
  const Vec3 dx_pos = vecFromDx(dx_, P_ID);
  const Vec3 dx_vel = vecFromDx(dx_, V_ID);
  const Vec3 dx_phi = vecFromDx(dx_, PHI_ID);
  pvacur_.pos_blh_rad_m = subtract(pvacur_.pos_blh_rad_m, multiply(Earth::DRi(pvacur_.pos_blh_rad_m), dx_pos));
  pvacur_.vel_ned_mps = subtract(pvacur_.vel_ned_mps, dx_vel);
  const Quaternion qpn = Rotation::rotvec2quaternion(dx_phi);
  pvacur_.qbn = Rotation::multiply(qpn, pvacur_.qbn);
  pvacur_.cbn = Rotation::quaternion2matrix(pvacur_.qbn);
  pvacur_.euler_rad = Rotation::matrix2euler(pvacur_.cbn);
  imuerror_.gyrbias = add(imuerror_.gyrbias, vecFromDx(dx_, BG_ID));
  imuerror_.accbias = add(imuerror_.accbias, vecFromDx(dx_, BA_ID));
  imuerror_.gyrscale = add(imuerror_.gyrscale, vecFromDx(dx_, SG_ID));
  imuerror_.accscale = add(imuerror_.accscale, vecFromDx(dx_, SA_ID));
  pvacur_.imu_error = imuerror_;
  zeroVector(dx_);
}

// 中文说明：newImuProcess 完整处理 res=0/1/2/3，R2 只做 synthetic smoke，不声明 real clean parity。
void GIEngine::newImuProcess() {
  if (!initialized_) {
    return;
  }
  timestamp_ = imucur_.time;
  const double updatetime = gnssdata_.isvalid ? gnssdata_.time : -1.0;
  const int res = isToUpdate(imupre_.time, imucur_.time, updatetime);
  if (res == 0) {
    insPropagation(imupre_, imucur_);
  } else if (res == 1) {
    gnssUpdate(gnssdata_);
    stateFeedback();
    pvapre_ = pvacur_;
    insPropagation(imupre_, imucur_);
  } else if (res == 2) {
    insPropagation(imupre_, imucur_);
    gnssUpdate(gnssdata_);
    stateFeedback();
  } else {
    ImuData midimu = imuInterpolate(imupre_, imucur_, updatetime);
    insPropagation(imupre_, midimu);
    gnssUpdate(gnssdata_);
    stateFeedback();
    pvapre_ = pvacur_;
    insPropagation(midimu, imucur_);
  }
  checkCov();
  pvapre_ = pvacur_;
  imupre_ = imucur_;
}

bool GIEngine::checkCov() const {
  for (std::size_t i = 0; i < RANK; ++i) {
    if (!std::isfinite(Cov_(i, i)) || Cov_(i, i) < 0.0) {
      return false;
    }
  }
  return true;
}

const NavState& GIEngine::navState() const {
  return pvacur_;
}

NavState GIEngine::getNavState() const {
  return pvacur_;
}

const std::vector<double>& GIEngine::getCovariance() const {
  return Cov_.data;
}

double GIEngine::timestamp() const {
  return timestamp_;
}

std::size_t GIEngine::propagationCount() const {
  return propagation_count_;
}

std::size_t GIEngine::updateCount() const {
  return update_count_;
}

std::size_t GIEngine::positionUpdateCount() const {
  return position_update_count_;
}

std::size_t GIEngine::velocityUpdateCount() const {
  return velocity_update_count_;
}

std::size_t GIEngine::yawUpdateCount() const {
  return yaw_update_count_;
}

std::size_t GIEngine::yawNormalCount() const {
  return yaw_normal_count_;
}

std::size_t GIEngine::yawDownweightCount() const {
  return yaw_downweight_count_;
}

std::size_t GIEngine::yawRejectCount() const {
  return yaw_reject_count_;
}

std::size_t GIEngine::rawDopplerUpdateCount() const {
  return raw_doppler_status_.update_count;
}

std::size_t GIEngine::rawDopplerRejectCount() const {
  return raw_doppler_status_.reject_count;
}

std::size_t GIEngine::rawDopplerEpochCount() const {
  return raw_doppler_status_.epoch_count;
}

std::size_t GIEngine::rawDopplerSatCountMin() const {
  return raw_doppler_status_.sat_count_min;
}

std::size_t GIEngine::rawDopplerSatCountMedian() const {
  return raw_doppler_status_.sat_count_median;
}

std::size_t GIEngine::rawDopplerSatCountMax() const {
  return raw_doppler_status_.sat_count_max;
}

double GIEngine::rawDopplerResidualP95() const {
  return raw_doppler_status_.residual_p95_mps;
}

RawDopplerFactorStatus GIEngine::rawDopplerStatus() const {
  return raw_doppler_status_;
}

void GIEngine::initializeCovariance() {
  Cov_ = Matrix(RANK, RANK, 0.0);
  setDiagonalBlock(Cov_, P_ID, positiveStd(options_.init_pos_std_m, 1.0e-6));
  setDiagonalBlock(Cov_, V_ID, positiveStd(options_.init_vel_std_mps, 1.0e-6));
  setDiagonalBlock(Cov_, PHI_ID, positiveStd(options_.init_att_std_rad, 1.0e-9));
  setDiagonalBlock(Cov_, BG_ID, positiveStd(options_.init_imu_error_std.gyrbias, options_.imunoise.gyrbias_std[0]));
  setDiagonalBlock(Cov_, BA_ID, positiveStd(options_.init_imu_error_std.accbias, options_.imunoise.accbias_std[0]));
  setDiagonalBlock(Cov_, SG_ID, positiveStd(options_.init_imu_error_std.gyrscale, options_.imunoise.gyrscale_std[0]));
  setDiagonalBlock(Cov_, SA_ID, positiveStd(options_.init_imu_error_std.accscale, options_.imunoise.accscale_std[0]));
}

// 中文说明：Qc bias/scale blocks 按 2/corr_time * std^2，corr_time 单位为秒。
void GIEngine::initializeQc() {
  Qc_ = Matrix(NOISERANK, NOISERANK, 0.0);
  const ImuNoise& n = options_.imunoise;
  setDiagonalBlockValue(Qc_, ARW_ID, cwiseProduct(n.gyr_arw, n.gyr_arw));
  setDiagonalBlockValue(Qc_, VRW_ID, cwiseProduct(n.acc_vrw, n.acc_vrw));
  const double corr = std::max(n.corr_time, 1.0);
  setDiagonalBlockValue(Qc_, BGSTD_ID, scale(cwiseProduct(n.gyrbias_std, n.gyrbias_std), 2.0 / corr));
  setDiagonalBlockValue(Qc_, BASTD_ID, scale(cwiseProduct(n.accbias_std, n.accbias_std), 2.0 / corr));
  setDiagonalBlockValue(Qc_, SGSTD_ID, scale(cwiseProduct(n.gyrscale_std, n.gyrscale_std), 2.0 / corr));
  setDiagonalBlockValue(Qc_, SASTD_ID, scale(cwiseProduct(n.accscale_std, n.accscale_std), 2.0 / corr));
}

// 中文说明：F/G/Phi/Qd 采用 KF-GINS error-state 结构；此处保留 key block 以便静态审计。
void GIEngine::buildErrorStateMatrices(const ImuData& imu, Matrix& F, Matrix& G, Matrix& Phi, Matrix& Qd) const {
  const double dt = imu.dt > 0.0 ? imu.dt : 0.01;
  const auto rmn = Earth::meridianPrimeVerticalRadius(pvapre_.pos_blh_rad_m[0]);
  const double rmh = rmn.first + pvapre_.pos_blh_rad_m[2];
  const double rnh = rmn.second + pvapre_.pos_blh_rad_m[2];
  const Vec3 accel = scale(imu.dvel, 1.0 / dt);
  const Vec3 omega = scale(imu.dtheta, 1.0 / dt);
  (void)rmh;
  (void)rnh;

  // F.block(P_ID,V_ID) = I: 位置误差由速度误差积分。
  setBlockIdentity(F, P_ID, V_ID);
  // F.block(V_ID,PHI_ID): 比力投影对姿态误差敏感。
  setBlock(F, V_ID, PHI_ID, Rotation::skewSymmetric(multiply(pvapre_.cbn, accel)));
  setBlock(F, V_ID, BA_ID, pvapre_.cbn);
  setBlock(F, V_ID, SA_ID, multiply(pvapre_.cbn, diag3(accel)));
  setBlock(F, PHI_ID, PHI_ID, scale(Rotation::skewSymmetric(add(Earth::iewn(pvapre_.pos_blh_rad_m),
                                                              Earth::enwn(pvapre_.pos_blh_rad_m,
                                                                          pvapre_.vel_ned_mps))),
                                     -1.0));
  setBlock(F, PHI_ID, BG_ID, scale(pvapre_.cbn, -1.0));
  setBlock(F, PHI_ID, SG_ID, scale(multiply(pvapre_.cbn, diag3(omega)), -1.0));
  const double corr = std::max(options_.imunoise.corr_time, 1.0);
  setBlock(F, BG_ID, BG_ID, scale(identityMatrix3(), -1.0 / corr));
  setBlock(F, BA_ID, BA_ID, scale(identityMatrix3(), -1.0 / corr));
  setBlock(F, SG_ID, SG_ID, scale(identityMatrix3(), -1.0 / corr));
  setBlock(F, SA_ID, SA_ID, scale(identityMatrix3(), -1.0 / corr));

  // G.block(V_ID,VRW_ID) 与 G.block(PHI_ID,ARW_ID) 对齐 reference 噪声驱动矩阵。
  setBlock(G, V_ID, VRW_ID, pvapre_.cbn);
  setBlock(G, PHI_ID, ARW_ID, pvapre_.cbn);
  setBlockIdentity(G, BG_ID, BGSTD_ID);
  setBlockIdentity(G, BA_ID, BASTD_ID);
  setBlockIdentity(G, SG_ID, SGSTD_ID);
  setBlockIdentity(G, SA_ID, SASTD_ID);

  Phi = add(identityMatrix(RANK), scale(F, dt));
  const Matrix GQG = multiply(multiply(G, Qc_), transpose(G));
  Qd = scale(add(multiply(multiply(Phi, GQG), transpose(Phi)), GQG), 0.5 * dt);
}

// 中文说明：position update 使用 predicted antenna position minus GNSS observed position。
void GIEngine::applyPositionUpdate(GnssData& gnss) {
  const Matrix3 dr = Earth::DR(pvacur_.pos_blh_rad_m);
  const Matrix3 dri = Earth::DRi(pvacur_.pos_blh_rad_m);
  const Vec3 lever_n = multiply(pvacur_.cbn, options_.antlever_m);
  const Vec3 antenna_pos = add(pvacur_.pos_blh_rad_m, multiply(dri, lever_n));
  const Vec3 dz_vec = multiply(dr, subtract(antenna_pos, gnss.blh_rad_m));
  Matrix H(3, RANK, 0.0);
  setBlockIdentity(H, 0, P_ID);
  // H_gnsspos / H_pos_phi: reference 使用 +skew(Cbn * antlever)。
  setBlock(H, 0, PHI_ID, Rotation::skewSymmetric(lever_n));
  Matrix R = diagonalMatrix(cwiseProduct(positiveStd(gnss.std_ned_m, 1.0e-3), positiveStd(gnss.std_ned_m, 1.0e-3)));
  EKFUpdate(std::vector<double>{dz_vec[0], dz_vec[1], dz_vec[2]}, H, R);
  ++position_update_count_;
}

bool GIEngine::receiverVelocityUpdateEnabledForTime(double time) const {
  if (!options_.enable_receiver_velocity_update) {
    return false;
  }
  if (options_.receiver_velocity_stress_mode == "disabled") {
    return false;
  }
  if (options_.receiver_velocity_stress_mode == "outage") {
    const double start = options_.receiver_velocity_outage_start_sec;
    const double end = start + std::max(0.0, options_.receiver_velocity_outage_duration_sec);
    return !(time >= start && time <= end);
  }
  return true;
}

double GIEngine::deterministicVelocityNoise(double time, int axis) const {
  const double std_mps = options_.receiver_velocity_additive_noise_std_mps;
  if (std_mps <= 0.0) {
    return 0.0;
  }
  const double seed = static_cast<double>(options_.receiver_velocity_additive_noise_seed + axis * 97);
  const double raw = std::sin(time * 12.9898 + seed * 78.233) * 43758.5453;
  const double frac = raw - std::floor(raw);
  return (2.0 * frac - 1.0) * std_mps;
}

GnssData GIEngine::receiverVelocityStressView(const GnssData& gnss) const {
  GnssData out = gnss;
  if (options_.receiver_velocity_stress_mode == "std_scale") {
    // 中文说明：STD scale 只降低 receiver-native velocity 权重以做诊断筛查，不是调参结论。
    out.vel_std_mps = scale(out.vel_std_mps, std::max(1.0e-6, options_.receiver_velocity_std_scale));
  } else if (options_.receiver_velocity_stress_mode == "additive_noise") {
    // 中文说明：固定 seed 的 additive noise 是 stress protocol，不代表真实传感器故障模型。
    out.vel_ned_mps = add(out.vel_ned_mps,
                          makeVec3(deterministicVelocityNoise(gnss.time, 0),
                                   deterministicVelocityNoise(gnss.time, 1),
                                   deterministicVelocityNoise(gnss.time, 2)));
  }
  return out;
}

// 中文说明：velocity update 使用 antenna velocity - GNSS velocity；若 lever velocity evidence 缺失则保持保守项。
void GIEngine::applyVelocityUpdate(GnssData& gnss) {
  const double dt = imucur_.dt > 0.0 ? imucur_.dt : 0.01;
  const Vec3 omega_b = scale(imucur_.dtheta, 1.0 / dt);
  const Vec3 antenna_vel = add(pvacur_.vel_ned_mps, multiply(pvacur_.cbn, cross(omega_b, options_.antlever_m)));
  const Vec3 dz_vec = subtract(antenna_vel, gnss.vel_ned_mps);
  Matrix H(3, RANK, 0.0);
  setBlockIdentity(H, 0, V_ID);
  setBlock(H, 0, PHI_ID, Rotation::skewSymmetric(multiply(pvacur_.cbn, cross(omega_b, options_.antlever_m))));
  Vec3 stdv = add(positiveStd(gnss.vel_std_mps, 1.0e-3), makeVec3(0.05, 0.05, 0.05));
  Matrix R = diagonalMatrix(cwiseProduct(stdv, stdv));
  EKFUpdate(std::vector<double>{dz_vec[0], dz_vec[1], dz_vec[2]}, H, R);
  ++velocity_update_count_;
}

// 中文说明：scheme_C 只对 dual-antenna yaw 观测做鲁棒门控，不放宽 hard=15 deg。
void GIEngine::applyYawUpdate(GnssData& gnss) {
  ++yaw_update_count_;
  const double yaw_obs = gnss.yaw_rad;
  const double yaw_pred = pvacur_.euler_rad[2];
  const double yaw_std = std::max(gnss.yaw_std_rad, options_.yaw_std_min_deg * D2R);
  const double residual = wrapYawResidual(yaw_pred - yaw_obs);
  const double abs_res = std::fabs(residual);
  if (yaw_std >= options_.yaw_std_hard_deg * D2R || abs_res >= options_.yaw_res_hard_deg * D2R) {
    ++yaw_reject_count_;
    return;
  }
  double scale_value = 1.0;
  if (yaw_std >= options_.yaw_std_soft_deg * D2R || abs_res >= options_.yaw_res_soft_deg * D2R) {
    scale_value = options_.yaw_downweight_scale;
    ++yaw_downweight_count_;
  } else {
    ++yaw_normal_count_;
  }
  Matrix H(1, RANK, 0.0);
  H(0, PHI_ID + 2) = -1.0;
  Matrix R(1, 1, scale_value * yaw_std * yaw_std);
  EKFUpdate(std::vector<double>{residual}, H, R);
}

void GIEngine::applyRawDopplerUpdateForTime(double update_time) {
  if (!options_.raw_doppler_config.enable_raw_doppler || !raw_doppler_status_.solver_enabled) {
    return;
  }
  const RawDopplerVelocityMeasurement* best = nullptr;
  double best_dt = options_.raw_doppler_config.raw_doppler_time_tolerance_sec;
  for (const auto& measurement : raw_doppler_measurements_) {
    const double dt = std::fabs(measurement.time - update_time);
    if (dt <= best_dt) {
      best = &measurement;
      best_dt = dt;
    }
  }
  if (!best) {
    return;
  }
  if (!RawDopplerFactor::isProviderBacked(*best) || best->sat_count < options_.raw_doppler_config.raw_doppler_min_sat) {
    ++raw_doppler_status_.reject_count;
    return;
  }
  const Vec3 residual_vec = subtract(pvacur_.vel_ned_mps, best->velocity_ned_mps);
  const double residual = norm(residual_vec);
  if (residual > options_.raw_doppler_config.raw_doppler_residual_gate_mps) {
    ++raw_doppler_status_.reject_count;
    raw_doppler_residual_norms_.push_back(residual);
    return;
  }
  Matrix H(3, RANK, 0.0);
  setBlockIdentity(H, 0, V_ID);
  const Vec3 stdv = RawDopplerFactor::positiveStd(*best);
  Matrix R = diagonalMatrix(scale(cwiseProduct(stdv, stdv), options_.raw_doppler_config.raw_doppler_R_scale));
  // 中文说明：dz = nav.vel - raw_doppler_velocity_ned，与现有 receiver-native velocity residual 同号。
  EKFUpdate(std::vector<double>{residual_vec[0], residual_vec[1], residual_vec[2]}, H, R);
  raw_doppler_residual_norms_.push_back(residual);
  ++raw_doppler_status_.update_count;
  if (raw_doppler_status_.sat_count_min == 0 || best->sat_count < raw_doppler_status_.sat_count_min) {
    raw_doppler_status_.sat_count_min = best->sat_count;
  }
  raw_doppler_status_.sat_count_max = std::max(raw_doppler_status_.sat_count_max, best->sat_count);
  std::vector<std::size_t> sat_counts;
  for (const auto& measurement : raw_doppler_measurements_) {
    if (measurement.provider_status == "available" && measurement.sat_count >= options_.raw_doppler_config.raw_doppler_min_sat) {
      sat_counts.push_back(measurement.sat_count);
    }
  }
  if (!sat_counts.empty()) {
    std::sort(sat_counts.begin(), sat_counts.end());
    raw_doppler_status_.sat_count_median = sat_counts[sat_counts.size() / 2];
  }
  if (!raw_doppler_residual_norms_.empty()) {
    std::vector<double> sorted = raw_doppler_residual_norms_;
    std::sort(sorted.begin(), sorted.end());
    const std::size_t index = static_cast<std::size_t>(0.95 * static_cast<double>(sorted.size() - 1));
    raw_doppler_status_.residual_p95_mps = sorted[index];
  }
}

double GIEngine::wrapYawResidual(double residual_rad) const {
  return Rotation::wrapRad(residual_rad);
}

Matrix GIEngine::covarianceMatrix() const {
  return Cov_;
}

void GIEngine::setCovarianceMatrix(const Matrix& matrix) {
  Cov_ = matrix;
}

}  // namespace legsa_v23_port_core
