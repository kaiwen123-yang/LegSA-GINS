// 中文说明：常用 WGS84 地球模型函数服务 N4 filter foundation，不做 final_v23 oracle claim。
// English note: BLH uses latitude rad, longitude rad, height m.

#pragma once

#include "legsa_gins/math/vec3.hpp"

namespace legsa_gins::math {

struct EarthRadii {
  double meridian_m = 0.0;
  double prime_vertical_m = 0.0;
};

EarthRadii meridianPrimeVerticalRadius(double lat_rad);
Vec3 DRi(const Vec3& blh_rad_m);
Vec3 DR(const Vec3& blh_rad_m);
double normalGravity(const Vec3& blh_rad_m);

}  // namespace legsa_gins::math
