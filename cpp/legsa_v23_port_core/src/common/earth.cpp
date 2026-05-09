// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/common/earth.hpp"

#include "legsa_v23_port_core/common/rotation.hpp"

#include <cmath>

namespace legsa_v23_port_core {

double Earth::degToRad(double deg) {
  return deg * D2R;
}

double Earth::radToDeg(double rad) {
  return rad * R2D;
}

// 中文说明：正常重力沿用 KF-GINS reference 的 WGS84 高程修正。
double Earth::gravity(const Vec3& blh_rad_m) {
  const double sinphi = std::sin(blh_rad_m[0]);
  const double sin2 = sinphi * sinphi;
  const double sin4 = sin2 * sin2;
  const double gamma_a = 9.7803267715;
  const double gamma_0 = gamma_a * (1.0 + 0.0052790414 * sin2 + 0.0000232718 * sin4 +
                                    0.0000001262 * sin2 * sin4 + 0.0000000007 * sin4 * sin4);
  return gamma_0 - (3.0877e-6 - 4.3e-9 * sin2) * blh_rad_m[2] + 0.72e-12 * blh_rad_m[2] * blh_rad_m[2];
}

std::pair<double, double> Earth::meridianPrimeVerticalRadius(double lat_rad) {
  const double sinlat = std::sin(lat_rad);
  const double tmp = 1.0 - kWgs84E1 * sinlat * sinlat;
  const double sqrttmp = std::sqrt(tmp);
  return {kWgs84A * (1.0 - kWgs84E1) / (sqrttmp * tmp), kWgs84A / sqrttmp};
}

double Earth::RN(double lat_rad) {
  const double sinlat = std::sin(lat_rad);
  return kWgs84A / std::sqrt(1.0 - kWgs84E1 * sinlat * sinlat);
}

// 中文说明：C_n^e 用于 BLH/ECEF 和导航系姿态传播，导航系为 NED。
Matrix3 Earth::cne(const Vec3& blh_rad_m) {
  const double sinlat = std::sin(blh_rad_m[0]);
  const double coslat = std::cos(blh_rad_m[0]);
  const double sinlon = std::sin(blh_rad_m[1]);
  const double coslon = std::cos(blh_rad_m[1]);
  return Matrix3{{{{-sinlat * coslon, -sinlon, -coslat * coslon}},
                  {{-sinlat * sinlon, coslon, -coslat * sinlon}},
                  {{coslat, 0.0, -sinlat}}}};
}

Quaternion Earth::qne(const Vec3& blh_rad_m) {
  const double coslon = std::cos(blh_rad_m[1] * 0.5);
  const double sinlon = std::sin(blh_rad_m[1] * 0.5);
  const double coslat = std::cos(-kPi * 0.25 - blh_rad_m[0] * 0.5);
  const double sinlat = std::sin(-kPi * 0.25 - blh_rad_m[0] * 0.5);
  return Rotation::normalize(Quaternion{coslat * coslon, -sinlat * sinlon, sinlat * coslon, coslat * sinlon});
}

Vec3 Earth::blh(const Quaternion& qne_value, double height_m) {
  const Quaternion q = Rotation::normalize(qne_value);
  return makeVec3(-2.0 * std::atan(q.y / q.w) - kPi * 0.5, 2.0 * std::atan2(q.z, q.w), height_m);
}

Vec3 Earth::blh2ecef(const Vec3& blh_rad_m) {
  const double coslat = std::cos(blh_rad_m[0]);
  const double sinlat = std::sin(blh_rad_m[0]);
  const double coslon = std::cos(blh_rad_m[1]);
  const double sinlon = std::sin(blh_rad_m[1]);
  const double rn = RN(blh_rad_m[0]);
  const double rnh = rn + blh_rad_m[2];
  return makeVec3(rnh * coslat * coslon, rnh * coslat * sinlon, (rnh - rn * kWgs84E1) * sinlat);
}

Vec3 Earth::ecef2blh(const Vec3& ecef_m) {
  const double p = std::sqrt(ecef_m[0] * ecef_m[0] + ecef_m[1] * ecef_m[1]);
  double lat = std::atan(ecef_m[2] / (p * (1.0 - kWgs84E1)));
  const double lon = 2.0 * std::atan2(ecef_m[1], ecef_m[0] + p);
  double h = 0.0;
  double h2 = -1.0;
  for (int iter = 0; iter < 20 && std::fabs(h - h2) > 1.0e-4; ++iter) {
    h2 = h;
    const double rn = RN(lat);
    h = p / std::cos(lat) - rn;
    lat = std::atan(ecef_m[2] / (p * (1.0 - kWgs84E1 * rn / (rn + h))));
  }
  return makeVec3(lat, lon, h);
}

// 中文说明：DR 将 BLH 微分转换到 NED；D 轴向下而 height 向上，所以高程项为 -1。
Matrix3 Earth::DR(const Vec3& blh_rad_m) {
  const auto rmn = meridianPrimeVerticalRadius(blh_rad_m[0]);
  Matrix3 dr = zeroMatrix3();
  dr[0][0] = rmn.first + blh_rad_m[2];
  dr[1][1] = (rmn.second + blh_rad_m[2]) * std::cos(blh_rad_m[0]);
  dr[2][2] = -1.0;
  return dr;
}

// 中文说明：DRi 是 NED 相对位置到 BLH 增量的转换，同样保持 height 的 -1 约定。
Matrix3 Earth::DRi(const Vec3& blh_rad_m) {
  const auto rmn = meridianPrimeVerticalRadius(blh_rad_m[0]);
  Matrix3 dri = zeroMatrix3();
  dri[0][0] = 1.0 / (rmn.first + blh_rad_m[2]);
  dri[1][1] = 1.0 / ((rmn.second + blh_rad_m[2]) * std::cos(blh_rad_m[0]));
  dri[2][2] = -1.0;
  return dri;
}

Vec3 Earth::iewe() {
  return makeVec3(0.0, 0.0, kWgs84Wie);
}

Vec3 Earth::iewn(const Vec3& blh_rad_m) {
  return makeVec3(kWgs84Wie * std::cos(blh_rad_m[0]), 0.0, -kWgs84Wie * std::sin(blh_rad_m[0]));
}

Vec3 Earth::enwn(const Vec3& blh_rad_m, const Vec3& vel_ned_mps) {
  const auto rmn = meridianPrimeVerticalRadius(blh_rad_m[0]);
  return makeVec3(vel_ned_mps[1] / (rmn.second + blh_rad_m[2]),
                  -vel_ned_mps[0] / (rmn.first + blh_rad_m[2]),
                  -vel_ned_mps[1] * std::tan(blh_rad_m[0]) / (rmn.second + blh_rad_m[2]));
}

}  // namespace legsa_v23_port_core
