// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/common/earth.hpp"

#include <cmath>

namespace legsa_v23_port_core {
namespace {
constexpr double kPi = 3.14159265358979323846;
}

// 中文说明：角度转弧度，保持配置/输出单位边界显式。
double Earth::degToRad(double deg) {
  return deg * kPi / 180.0;
}

// 中文说明：弧度转角度，仅用于 writer/demo 输出。
double Earth::radToDeg(double rad) {
  return rad * 180.0 / kPi;
}

// 中文说明：DR 使用 NED D 轴向下和 height 向上的 -1 高程约定。
Matrix3 Earth::DR(const Vec3& blh_rad_m) {
  const double lat = blh_rad_m[0];
  const double h = blh_rad_m[2];
  const double sin_lat = std::sin(lat);
  const double denom = 1.0 - kWgs84E2 * sin_lat * sin_lat;
  const double rn = kWgs84A / std::sqrt(denom);
  const double rm = rn * (1.0 - kWgs84E2) / denom;
  return Matrix3{{{{rm + h, 0.0, 0.0}}, {{0.0, (rn + h) * std::cos(lat), 0.0}}, {{0.0, 0.0, -1.0}}}};
}

// 中文说明：DRi 是 DR 的对角逆，R1 先保留 source-backed 高程符号合同。
Matrix3 Earth::DRi(const Vec3& blh_rad_m) {
  const Matrix3 dr = DR(blh_rad_m);
  return Matrix3{{{{1.0 / dr[0][0], 0.0, 0.0}}, {{0.0, 1.0 / dr[1][1], 0.0}}, {{0.0, 0.0, -1.0}}}};
}

}  // namespace legsa_v23_port_core
