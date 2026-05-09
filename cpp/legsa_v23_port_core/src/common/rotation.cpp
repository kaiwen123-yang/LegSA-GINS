// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/common/rotation.hpp"

#include <algorithm>
#include <cmath>

namespace legsa_v23_port_core {

Quaternion Rotation::normalize(const Quaternion& quaternion) {
  const double n = std::sqrt(quaternion.w * quaternion.w + quaternion.x * quaternion.x +
                             quaternion.y * quaternion.y + quaternion.z * quaternion.z);
  if (n <= 0.0) {
    return Quaternion{};
  }
  return Quaternion{quaternion.w / n, quaternion.x / n, quaternion.y / n, quaternion.z / n};
}

Quaternion Rotation::multiply(const Quaternion& lhs, const Quaternion& rhs) {
  return normalize(Quaternion{
      lhs.w * rhs.w - lhs.x * rhs.x - lhs.y * rhs.y - lhs.z * rhs.z,
      lhs.w * rhs.x + lhs.x * rhs.w + lhs.y * rhs.z - lhs.z * rhs.y,
      lhs.w * rhs.y - lhs.x * rhs.z + lhs.y * rhs.w + lhs.z * rhs.x,
      lhs.w * rhs.z + lhs.x * rhs.y - lhs.y * rhs.x + lhs.z * rhs.w});
}

Quaternion Rotation::inverse(const Quaternion& quaternion) {
  const Quaternion q = normalize(quaternion);
  return Quaternion{q.w, -q.x, -q.y, -q.z};
}

Quaternion Rotation::matrix2quaternion(const Matrix3& matrix) {
  const double trace = matrix[0][0] + matrix[1][1] + matrix[2][2];
  Quaternion q;
  if (trace > 0.0) {
    const double s = std::sqrt(trace + 1.0) * 2.0;
    q.w = 0.25 * s;
    q.x = (matrix[2][1] - matrix[1][2]) / s;
    q.y = (matrix[0][2] - matrix[2][0]) / s;
    q.z = (matrix[1][0] - matrix[0][1]) / s;
  } else if (matrix[0][0] > matrix[1][1] && matrix[0][0] > matrix[2][2]) {
    const double s = std::sqrt(1.0 + matrix[0][0] - matrix[1][1] - matrix[2][2]) * 2.0;
    q.w = (matrix[2][1] - matrix[1][2]) / s;
    q.x = 0.25 * s;
    q.y = (matrix[0][1] + matrix[1][0]) / s;
    q.z = (matrix[0][2] + matrix[2][0]) / s;
  } else if (matrix[1][1] > matrix[2][2]) {
    const double s = std::sqrt(1.0 + matrix[1][1] - matrix[0][0] - matrix[2][2]) * 2.0;
    q.w = (matrix[0][2] - matrix[2][0]) / s;
    q.x = (matrix[0][1] + matrix[1][0]) / s;
    q.y = 0.25 * s;
    q.z = (matrix[1][2] + matrix[2][1]) / s;
  } else {
    const double s = std::sqrt(1.0 + matrix[2][2] - matrix[0][0] - matrix[1][1]) * 2.0;
    q.w = (matrix[1][0] - matrix[0][1]) / s;
    q.x = (matrix[0][2] + matrix[2][0]) / s;
    q.y = (matrix[1][2] + matrix[2][1]) / s;
    q.z = 0.25 * s;
  }
  return normalize(q);
}

Matrix3 Rotation::quaternion2matrix(const Quaternion& quaternion) {
  const Quaternion q = normalize(quaternion);
  const double xx = q.x * q.x;
  const double yy = q.y * q.y;
  const double zz = q.z * q.z;
  const double xy = q.x * q.y;
  const double xz = q.x * q.z;
  const double yz = q.y * q.z;
  const double wx = q.w * q.x;
  const double wy = q.w * q.y;
  const double wz = q.w * q.z;
  return Matrix3{{{{1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)}},
                  {{2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)}},
                  {{2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)}}}};
}

// 中文说明：matrix2euler 输出 RPY，heading/yaw 按 reference 归一到 0~2pi。
Vec3 Rotation::matrix2euler(const Matrix3& matrix) {
  Vec3 euler{};
  euler[1] = std::atan(-matrix[2][0] /
                       std::sqrt(matrix[2][1] * matrix[2][1] + matrix[2][2] * matrix[2][2]));
  if (matrix[2][0] <= -0.999) {
    euler[0] = 0.0;
    euler[2] = std::atan2(matrix[1][2] - matrix[0][1], matrix[0][2] + matrix[1][1]);
  } else if (matrix[2][0] >= 0.999) {
    euler[0] = 0.0;
    euler[2] = kPi + std::atan2(matrix[1][2] + matrix[0][1], matrix[0][2] - matrix[1][1]);
  } else {
    euler[0] = std::atan2(matrix[2][1], matrix[2][2]);
    euler[2] = std::atan2(matrix[1][0], matrix[0][0]);
  }
  euler[2] = wrap2Pi(euler[2]);
  return euler;
}

Vec3 Rotation::quaternion2euler(const Quaternion& quaternion) {
  return matrix2euler(quaternion2matrix(quaternion));
}

Quaternion Rotation::rotvec2quaternion(const Vec3& rotvec) {
  const double angle = norm(rotvec);
  if (angle < 1.0e-12) {
    return normalize(Quaternion{1.0, 0.5 * rotvec[0], 0.5 * rotvec[1], 0.5 * rotvec[2]});
  }
  const double half = 0.5 * angle;
  const double s = std::sin(half) / angle;
  return normalize(Quaternion{std::cos(half), s * rotvec[0], s * rotvec[1], s * rotvec[2]});
}

Vec3 Rotation::quaternion2vector(const Quaternion& quaternion) {
  const Quaternion q = normalize(quaternion);
  const double sin_half = std::sqrt(q.x * q.x + q.y * q.y + q.z * q.z);
  if (sin_half < 1.0e-12) {
    return makeVec3(2.0 * q.x, 2.0 * q.y, 2.0 * q.z);
  }
  double angle = 2.0 * std::atan2(sin_half, q.w);
  if (angle > kPi) {
    angle -= 2.0 * kPi;
  }
  const double scale_value = angle / sin_half;
  return makeVec3(scale_value * q.x, scale_value * q.y, scale_value * q.z);
}

Matrix3 Rotation::euler2matrix(const Vec3& euler_rad) {
  const double cr = std::cos(euler_rad[0]);
  const double sr = std::sin(euler_rad[0]);
  const double cp = std::cos(euler_rad[1]);
  const double sp = std::sin(euler_rad[1]);
  const double cy = std::cos(euler_rad[2]);
  const double sy = std::sin(euler_rad[2]);
  return Matrix3{{{{cp * cy, sr * sp * cy - cr * sy, cr * sp * cy + sr * sy}},
                  {{cp * sy, sr * sp * sy + cr * cy, cr * sp * sy - sr * cy}},
                  {{-sp, sr * cp, cr * cp}}}};
}

Quaternion Rotation::euler2quaternion(const Vec3& euler_rad) {
  return matrix2quaternion(euler2matrix(euler_rad));
}

Matrix3 Rotation::skewSymmetric(const Vec3& vector) {
  return skew(vector);
}

std::array<std::array<double, 4>, 4> Rotation::quaternionleft(const Quaternion& quaternion) {
  const Quaternion q = normalize(quaternion);
  return {{{{q.w, -q.x, -q.y, -q.z}},
           {{q.x, q.w, -q.z, q.y}},
           {{q.y, q.z, q.w, -q.x}},
           {{q.z, -q.y, q.x, q.w}}}};
}

std::array<std::array<double, 4>, 4> Rotation::quaternionright(const Quaternion& quaternion) {
  const Quaternion q = normalize(quaternion);
  return {{{{q.w, -q.x, -q.y, -q.z}},
           {{q.x, q.w, q.z, -q.y}},
           {{q.y, -q.z, q.w, q.x}},
           {{q.z, q.y, -q.x, q.w}}}};
}

Matrix3 Rotation::eulerToMatrix(const Vec3& euler_rad) {
  return euler2matrix(euler_rad);
}

Vec3 Rotation::matrixToEuler(const Matrix3& matrix) {
  return matrix2euler(matrix);
}

double Rotation::wrapRad(double angle_rad) {
  while (angle_rad > kPi) {
    angle_rad -= 2.0 * kPi;
  }
  while (angle_rad < -kPi) {
    angle_rad += 2.0 * kPi;
  }
  return angle_rad;
}

double Rotation::wrap2Pi(double angle_rad) {
  while (angle_rad >= 2.0 * kPi) {
    angle_rad -= 2.0 * kPi;
  }
  while (angle_rad < 0.0) {
    angle_rad += 2.0 * kPi;
  }
  return angle_rad;
}

}  // namespace legsa_v23_port_core
