// 中文说明：地球模型实现只用于 N4 基础滤波骨架，不复制外部 KF-GINS 源码。
// English note: This is a compact WGS84 implementation for toy filter runs.

#include "legsa_gins/math/earth.hpp"

#include <algorithm>
#include <cmath>

#include "legsa_gins/math/constants.hpp"

namespace legsa_gins::math {

EarthRadii meridianPrimeVerticalRadius(double lat_rad) {
  const double sin_lat = std::sin(lat_rad);
  const double denom = std::sqrt(1.0 - wgs84_e2 * sin_lat * sin_lat);
  const double prime_vertical = wgs84_a / denom;
  const double meridian = wgs84_a * (1.0 - wgs84_e2) / (denom * denom * denom);
  return {meridian, prime_vertical};
}

Vec3 DRi(const Vec3& blh_rad_m) {
  const auto radii = meridianPrimeVerticalRadius(blh_rad_m.x);
  const double cos_lat = std::max(1.0e-8, std::abs(std::cos(blh_rad_m.x)));
  return {
      1.0 / (radii.meridian_m + blh_rad_m.z),
      1.0 / ((radii.prime_vertical_m + blh_rad_m.z) * cos_lat),
      -1.0,
  };
}

Vec3 DR(const Vec3& blh_rad_m) {
  const auto radii = meridianPrimeVerticalRadius(blh_rad_m.x);
  const double cos_lat = std::max(1.0e-8, std::abs(std::cos(blh_rad_m.x)));
  return {
      radii.meridian_m + blh_rad_m.z,
      (radii.prime_vertical_m + blh_rad_m.z) * cos_lat,
      -1.0,
  };
}

double normalGravity(const Vec3& blh_rad_m) {
  const double sin_lat = std::sin(blh_rad_m.x);
  const double sin2 = sin_lat * sin_lat;
  const double gravity = normal_gravity_equator *
                         (1.0 + 0.00193185265241 * sin2) /
                         std::sqrt(1.0 - wgs84_e2 * sin2);
  return gravity - 3.086e-6 * blh_rad_m.z;
}

}  // namespace legsa_gins::math
