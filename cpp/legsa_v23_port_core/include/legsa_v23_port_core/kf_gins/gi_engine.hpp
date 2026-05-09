// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#pragma once

#include "legsa_v23_port_core/gnss.hpp"
#include "legsa_v23_port_core/imu.hpp"
#include "legsa_v23_port_core/nav_state.hpp"
#include "legsa_v23_port_core/options.hpp"

#include <vector>

namespace legsa_v23_port_core {

// 中文说明：GIEngine 保留 KF-GINS 核心函数名，R1 只提供可编译 source-backed skeleton。
class GIEngine {
 public:
  explicit GIEngine(PortOptions options);

  void initialize(const NavState& initial_state);
  void addImuData(const ImuData& imu);
  void addGnssData(const GnssData& gnss);
  int isToUpdate() const;
  ImuData imuInterpolate(const ImuData& previous, const ImuData& current, double time) const;
  ImuData imuCompensate(const ImuData& imu) const;
  void insPropagation();
  void gnssUpdate();
  void EKFPredict();
  void EKFUpdate();
  void stateFeedback();
  void newImuProcess();
  bool checkCov() const;

  const NavState& navState() const;
  const std::vector<double>& getCovariance() const;
  std::size_t propagationCount() const;
  std::size_t updateCount() const;

 private:
  PortOptions options_;
  NavState state_;
  std::vector<ImuData> imu_buffer_;
  std::vector<GnssData> gnss_buffer_;
  std::vector<double> covariance_;
  std::vector<double> dx_;
  std::size_t propagation_count_ = 0;
  std::size_t update_count_ = 0;
  bool initialized_ = false;
};

}  // namespace legsa_v23_port_core

