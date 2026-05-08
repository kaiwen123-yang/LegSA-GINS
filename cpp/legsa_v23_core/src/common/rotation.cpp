#include "legsa_v23_core/common/rotation.hpp"

#include "legsa_v23_core/common/constants.hpp"

#include <algorithm>
#include <cmath>

namespace legsa_v23_core {

// 中文说明：反对称矩阵满足 skew(a)*b = a x b，用于 NED/body 旋转小量。
Matrix3 Rotation::skewSymmetric(const Vector3& vector) {
  Matrix3 matrix{};
  matrix.fill(0.0);
  matrix3At(matrix, 0, 1) = -vector[2];
  matrix3At(matrix, 0, 2) = vector[1];
  matrix3At(matrix, 1, 0) = vector[2];
  matrix3At(matrix, 1, 2) = -vector[0];
  matrix3At(matrix, 2, 0) = -vector[1];
  matrix3At(matrix, 2, 1) = vector[0];
  return matrix;
}

// 中文说明：旋转向量到四元数，保留小角近似稳定性。
Quaternion Rotation::rotvec2quaternion(const Vector3& rotvec) {
  const double angle = std::sqrt(rotvec[0] * rotvec[0] + rotvec[1] * rotvec[1] + rotvec[2] * rotvec[2]);
  if (angle < 1.0e-12) {
    return normalize({1.0, 0.5 * rotvec[0], 0.5 * rotvec[1], 0.5 * rotvec[2]});
  }
  const double half = 0.5 * angle;
  const double scale = std::sin(half) / angle;
  return normalize({std::cos(half), rotvec[0] * scale, rotvec[1] * scale, rotvec[2] * scale});
}

// 中文说明：四元数转矩阵；矩阵表示 body 到 nav 或 ECEF 到 NED 时由调用侧约定。
Matrix3 Rotation::quaternion2matrix(const Quaternion& quaternion) {
  const Quaternion q = normalize(quaternion);
  const double w = q[0];
  const double x = q[1];
  const double y = q[2];
  const double z = q[3];
  Matrix3 matrix{};
  matrix3At(matrix, 0, 0) = 1.0 - 2.0 * (y * y + z * z);
  matrix3At(matrix, 0, 1) = 2.0 * (x * y - w * z);
  matrix3At(matrix, 0, 2) = 2.0 * (x * z + w * y);
  matrix3At(matrix, 1, 0) = 2.0 * (x * y + w * z);
  matrix3At(matrix, 1, 1) = 1.0 - 2.0 * (x * x + z * z);
  matrix3At(matrix, 1, 2) = 2.0 * (y * z - w * x);
  matrix3At(matrix, 2, 0) = 2.0 * (x * z - w * y);
  matrix3At(matrix, 2, 1) = 2.0 * (y * z + w * x);
  matrix3At(matrix, 2, 2) = 1.0 - 2.0 * (x * x + y * y);
  return matrix;
}

// 中文说明：矩阵转四元数，保证输出归一化。
Quaternion Rotation::matrix2quaternion(const Matrix3& matrix) {
  const double trace = matrix3At(matrix, 0, 0) + matrix3At(matrix, 1, 1) + matrix3At(matrix, 2, 2);
  Quaternion q{};
  if (trace > 0.0) {
    const double s = std::sqrt(trace + 1.0) * 2.0;
    q = {0.25 * s, (matrix3At(matrix, 2, 1) - matrix3At(matrix, 1, 2)) / s,
         (matrix3At(matrix, 0, 2) - matrix3At(matrix, 2, 0)) / s,
         (matrix3At(matrix, 1, 0) - matrix3At(matrix, 0, 1)) / s};
  } else if (matrix3At(matrix, 0, 0) > matrix3At(matrix, 1, 1) &&
             matrix3At(matrix, 0, 0) > matrix3At(matrix, 2, 2)) {
    const double s = std::sqrt(1.0 + matrix3At(matrix, 0, 0) - matrix3At(matrix, 1, 1) -
                               matrix3At(matrix, 2, 2)) *
                     2.0;
    q = {(matrix3At(matrix, 2, 1) - matrix3At(matrix, 1, 2)) / s, 0.25 * s,
         (matrix3At(matrix, 0, 1) + matrix3At(matrix, 1, 0)) / s,
         (matrix3At(matrix, 0, 2) + matrix3At(matrix, 2, 0)) / s};
  } else if (matrix3At(matrix, 1, 1) > matrix3At(matrix, 2, 2)) {
    const double s = std::sqrt(1.0 + matrix3At(matrix, 1, 1) - matrix3At(matrix, 0, 0) -
                               matrix3At(matrix, 2, 2)) *
                     2.0;
    q = {(matrix3At(matrix, 0, 2) - matrix3At(matrix, 2, 0)) / s,
         (matrix3At(matrix, 0, 1) + matrix3At(matrix, 1, 0)) / s, 0.25 * s,
         (matrix3At(matrix, 1, 2) + matrix3At(matrix, 2, 1)) / s};
  } else {
    const double s = std::sqrt(1.0 + matrix3At(matrix, 2, 2) - matrix3At(matrix, 0, 0) -
                               matrix3At(matrix, 1, 1)) *
                     2.0;
    q = {(matrix3At(matrix, 1, 0) - matrix3At(matrix, 0, 1)) / s,
         (matrix3At(matrix, 0, 2) + matrix3At(matrix, 2, 0)) / s,
         (matrix3At(matrix, 1, 2) + matrix3At(matrix, 2, 1)) / s, 0.25 * s};
  }
  return normalize(q);
}

// 中文说明：矩阵转 RPY，yaw/heading 输出范围为 [-pi,pi)。
Vector3 Rotation::matrix2euler(const Matrix3& matrix) {
  const double pitch = std::asin(std::clamp(-matrix3At(matrix, 2, 0), -1.0, 1.0));
  const double roll = std::atan2(matrix3At(matrix, 2, 1), matrix3At(matrix, 2, 2));
  const double yaw = std::atan2(matrix3At(matrix, 1, 0), matrix3At(matrix, 0, 0));
  return {wrapAngleRad(roll), pitch, wrapAngleRad(yaw)};
}

// 中文说明：RPY 转 body-to-nav 矩阵，body 采用 FRD，nav 采用 NED。
Matrix3 Rotation::euler2matrix(const Vector3& euler) {
  const double cr = std::cos(euler[0]);
  const double sr = std::sin(euler[0]);
  const double cp = std::cos(euler[1]);
  const double sp = std::sin(euler[1]);
  const double cy = std::cos(euler[2]);
  const double sy = std::sin(euler[2]);
  Matrix3 matrix{};
  matrix3At(matrix, 0, 0) = cp * cy;
  matrix3At(matrix, 0, 1) = sr * sp * cy - cr * sy;
  matrix3At(matrix, 0, 2) = cr * sp * cy + sr * sy;
  matrix3At(matrix, 1, 0) = cp * sy;
  matrix3At(matrix, 1, 1) = sr * sp * sy + cr * cy;
  matrix3At(matrix, 1, 2) = cr * sp * sy - sr * cy;
  matrix3At(matrix, 2, 0) = -sp;
  matrix3At(matrix, 2, 1) = sr * cp;
  matrix3At(matrix, 2, 2) = cr * cp;
  return matrix;
}

// 中文说明：RPY 先转矩阵再转四元数，减少公式分支。
Quaternion Rotation::euler2quaternion(const Vector3& euler) {
  return matrix2quaternion(euler2matrix(euler));
}

// 中文说明：四元数转旋转向量，供测试和误差状态可视化使用。
Vector3 Rotation::quaternion2vector(const Quaternion& quaternion) {
  const Quaternion q = normalize(quaternion);
  const double sin_half = std::sqrt(q[1] * q[1] + q[2] * q[2] + q[3] * q[3]);
  if (sin_half < 1.0e-12) {
    return {2.0 * q[1], 2.0 * q[2], 2.0 * q[3]};
  }
  const double angle = 2.0 * std::atan2(sin_half, q[0]);
  const double scale = angle / sin_half;
  return {q[1] * scale, q[2] * scale, q[3] * scale};
}

// 中文说明：rad 包裹用于 yaw/heading，避免跨 pi 导致输出跳变。
double Rotation::wrapAngleRad(double angle) {
  while (angle >= 3.14159265358979323846) {
    angle -= 2.0 * 3.14159265358979323846;
  }
  while (angle < -3.14159265358979323846) {
    angle += 2.0 * 3.14159265358979323846;
  }
  return angle;
}

// 中文说明：deg 包裹用于报告层 yaw/heading。
double Rotation::wrapAngleDeg(double angle) {
  while (angle >= 180.0) {
    angle -= 360.0;
  }
  while (angle < -180.0) {
    angle += 360.0;
  }
  return angle;
}

// 中文说明：四元数乘法，保持 body-to-nav 和小旋转组合顺序可审计。
Quaternion Rotation::multiply(const Quaternion& lhs, const Quaternion& rhs) {
  return normalize({lhs[0] * rhs[0] - lhs[1] * rhs[1] - lhs[2] * rhs[2] - lhs[3] * rhs[3],
                    lhs[0] * rhs[1] + lhs[1] * rhs[0] + lhs[2] * rhs[3] - lhs[3] * rhs[2],
                    lhs[0] * rhs[2] - lhs[1] * rhs[3] + lhs[2] * rhs[0] + lhs[3] * rhs[1],
                    lhs[0] * rhs[3] + lhs[1] * rhs[2] - lhs[2] * rhs[1] + lhs[3] * rhs[0]});
}

// 中文说明：四元数归一化，零范数回退为单位姿态。
Quaternion Rotation::normalize(const Quaternion& quaternion) {
  const double norm = std::sqrt(quaternion[0] * quaternion[0] + quaternion[1] * quaternion[1] +
                                quaternion[2] * quaternion[2] + quaternion[3] * quaternion[3]);
  if (norm < 1.0e-15) {
    return {1.0, 0.0, 0.0, 0.0};
  }
  return {quaternion[0] / norm, quaternion[1] / norm, quaternion[2] / norm, quaternion[3] / norm};
}

}  // namespace legsa_v23_core
