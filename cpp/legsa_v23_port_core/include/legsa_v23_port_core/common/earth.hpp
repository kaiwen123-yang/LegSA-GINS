// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#pragma once

#include "legsa_v23_port_core/types.hpp"

#include <utility>

namespace legsa_v23_port_core {

// 中文说明：Earth 保持 KF-GINS/final_v23 的 WGS84、NED、BLH 高程符号约定。
class Earth {
 public:
  static constexpr double kWgs84Wie = 7.2921151467E-5;
  static constexpr double kWgs84F = 0.0033528106647474805;
  static constexpr double kWgs84A = 6378137.0;
  static constexpr double kWgs84B = 6356752.3142451793;
  static constexpr double kWgs84E1 = 0.0066943799901413156;
  static constexpr double kWgs84E2 = 0.0067394967422764341;

  static double degToRad(double deg);
  static double radToDeg(double rad);
  static double gravity(const Vec3& blh_rad_m);
  static std::pair<double, double> meridianPrimeVerticalRadius(double lat_rad);
  static double RN(double lat_rad);
  static Matrix3 cne(const Vec3& blh_rad_m);
  static Quaternion qne(const Vec3& blh_rad_m);
  static Vec3 blh(const Quaternion& qne_value, double height_m);
  static Vec3 blh2ecef(const Vec3& blh_rad_m);
  static Vec3 ecef2blh(const Vec3& ecef_m);
  static Matrix3 DR(const Vec3& blh_rad_m);
  static Matrix3 DRi(const Vec3& blh_rad_m);
  static Vec3 iewe();
  static Vec3 iewn(const Vec3& blh_rad_m);
  static Vec3 enwn(const Vec3& blh_rad_m, const Vec3& vel_ned_mps);
};

}  // namespace legsa_v23_port_core
