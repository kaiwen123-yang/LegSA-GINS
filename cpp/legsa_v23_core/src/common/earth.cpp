#include "legsa_v23_core/common/earth.hpp"

#include "legsa_v23_core/common/constants.hpp"
#include "legsa_v23_core/common/rotation.hpp"

#include <cmath>

namespace legsa_v23_core {

// 中文说明：WGS84 正常重力模型，NED 下 Down 为正；LegSA 自有实现，不编译 reference 源码。
Vector3 Earth::gravity(const Vector3& blh) {
  const double lat = blh[0];
  const double h = blh[2];
  const double sin_lat = std::sin(lat);
  const double sin2 = sin_lat * sin_lat;
  const double gamma = 9.7803253359 * (1.0 + 0.00193185265241 * sin2) / std::sqrt(1.0 - kWgs84E2 * sin2);
  const double g = gamma - 3.086e-6 * h;
  return {0.0, 0.0, g};
}

// 中文说明：返回 RM/RN，BLH 中纬度单位为 rad；N4H4B 用于 position update 和 F 块。
Vector3 Earth::meridianPrimeVerticalRadius(double lat) {
  const double sin_lat = std::sin(lat);
  const double denom = 1.0 - kWgs84E2 * sin_lat * sin_lat;
  const double sqrt_denom = std::sqrt(denom);
  const double rn = kWgs84A / sqrt_denom;
  const double rm = kWgs84A * (1.0 - kWgs84E2) / (denom * sqrt_denom);
  return {rm, rn, 0.0};
}

// 中文说明：卯酉圈半径 RN，单位 m。
double Earth::RN(double lat) { return meridianPrimeVerticalRadius(lat)[1]; }

// 中文说明：DRi 描述 NED 位移到 BLH 增量的线性关系，height 向上为正所以 Down 位移取负号。
Matrix3 Earth::DRi(const Vector3& blh) {
  const Vector3 rmn = meridianPrimeVerticalRadius(blh[0]);
  const double rm_h = rmn[0] + blh[2];
  const double rn_h = rmn[1] + blh[2];
  Matrix3 matrix{};
  matrix.fill(0.0);
  matrix3At(matrix, 0, 0) = 1.0 / rm_h;
  matrix3At(matrix, 1, 1) = 1.0 / (rn_h * std::max(1.0e-12, std::cos(blh[0])));
  matrix3At(matrix, 2, 2) = -1.0;
  return matrix;
}

// 中文说明：DR 描述 BLH 增量到 NED 位移的线性关系，是 DRi 的近似逆。
Matrix3 Earth::DR(const Vector3& blh) {
  const Vector3 rmn = meridianPrimeVerticalRadius(blh[0]);
  Matrix3 matrix{};
  matrix.fill(0.0);
  matrix3At(matrix, 0, 0) = rmn[0] + blh[2];
  matrix3At(matrix, 1, 1) = (rmn[1] + blh[2]) * std::cos(blh[0]);
  matrix3At(matrix, 2, 2) = -1.0;
  return matrix;
}

// 中文说明：构造 ECEF 到 NED 的旋转四元数；NED 定义为 north/east/down。
Quaternion Earth::qne(const Vector3& blh) {
  const double lat = blh[0];
  const double lon = blh[1];
  Matrix3 cne{};
  matrix3At(cne, 0, 0) = -std::sin(lat) * std::cos(lon);
  matrix3At(cne, 0, 1) = -std::sin(lat) * std::sin(lon);
  matrix3At(cne, 0, 2) = std::cos(lat);
  matrix3At(cne, 1, 0) = -std::sin(lon);
  matrix3At(cne, 1, 1) = std::cos(lon);
  matrix3At(cne, 1, 2) = 0.0;
  matrix3At(cne, 2, 0) = -std::cos(lat) * std::cos(lon);
  matrix3At(cne, 2, 1) = -std::cos(lat) * std::sin(lon);
  matrix3At(cne, 2, 2) = -std::sin(lat);
  return Rotation::matrix2quaternion(cne);
}

// 中文说明：从 qne 近似恢复 BLH 只用于内部测试；正式 ECEF/BLH 反算留给后续扩展。
Vector3 Earth::blh(const Quaternion& qne_value, double height) {
  const Matrix3 cne = Rotation::quaternion2matrix(qne_value);
  const double lat = std::atan2(-matrix3At(cne, 2, 2), matrix3At(cne, 0, 2));
  const double lon = std::atan2(-matrix3At(cne, 1, 0), matrix3At(cne, 1, 1));
  return {lat, lon, height};
}

// 中文说明：地球自转向量投影到 NED；用于速度和姿态传播中的 Coriolis/n-frame 修正。
Vector3 Earth::iewn(double lat) {
  return {kWgs84Wie * std::cos(lat), 0.0, -kWgs84Wie * std::sin(lat)};
}

// 中文说明：导航系相对地球系转率，NED 速度为 vn/ve/vd。
Vector3 Earth::enwn(const Vector3& rmn, const Vector3& blh, const Vector3& vel) {
  const double rm_h = rmn[0] + blh[2];
  const double rn_h = rmn[1] + blh[2];
  const double cos_lat = std::max(1.0e-12, std::cos(blh[0]));
  return {vel[1] / rn_h, -vel[0] / rm_h, -vel[1] * std::tan(blh[0]) / rn_h / cos_lat * cos_lat};
}

}  // namespace legsa_v23_core
