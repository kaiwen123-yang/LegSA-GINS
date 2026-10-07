#include "legsa_v23_port_core/factors/pose_clone.hpp"
#include "legsa_v23_port_core/factors/attitude_clone.hpp"
#include "legsa_v23_port_core/common/earth.hpp"
#include <cmath>
#include <stdexcept>

namespace legsa_v23_port_core::pose_clone {
namespace {
void require(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}
Matrix symmetrize(const Matrix& a) { return scale(add(a, transpose(a)), 0.5); }
void validate(const Gaussian& s) {
  require(s.mean.size() == kCurrent || s.mean.size() == kJoint, "POSE_CLONE_STATE_DIMENSION");
  require(s.covariance.rows == s.mean.size() && s.covariance.cols == s.mean.size(),
          "POSE_CLONE_COVARIANCE_DIMENSION");
}
Matrix solveSpd(const Matrix& s, const Matrix& rhs) {
  require(s.rows == s.cols && rhs.rows == s.rows, "POSE_CLONE_SOLVE_DIMENSION");
  Matrix l(s.rows, s.cols);
  for (std::size_t i = 0; i < s.rows; ++i) {
    for (std::size_t j = 0; j <= i; ++j) {
      double value = 0.5 * (s(i, j) + s(j, i));
      for (std::size_t k = 0; k < j; ++k) value -= l(i, k) * l(j, k);
      if (i == j) {
        require(std::isfinite(value) && value > 0.0, "POSE_CLONE_INNOVATION_NOT_SPD");
        l(i, j) = std::sqrt(value);
      } else l(i, j) = value / l(j, j);
    }
  }
  Matrix x = rhs;
  for (std::size_t c = 0; c < x.cols; ++c) {
    for (std::size_t i = 0; i < x.rows; ++i) {
      for (std::size_t j = 0; j < i; ++j) x(i, c) -= l(i, j) * x(j, c);
      x(i, c) /= l(i, i);
    }
    for (std::size_t i = x.rows; i-- > 0;) {
      for (std::size_t j = i + 1; j < x.rows; ++j) x(i, c) -= l(j, i) * x(j, c);
      x(i, c) /= l(i, i);
    }
  }
  return x;
}
}  // namespace

Matrix augmentationJacobian(const Vec3& blh) {
  Matrix j(6, kCurrent);
  const Matrix3 e = Earth::cne(blh);
  setBlock(j, 0, P_ID, e);
  setBlock(j, 3, P_ID, scale(attitude_clone::nedFrameConnection(blh), -1.0));
  setBlock(j, 3, PHI_ID, e);
  return j;
}

Gaussian augment(const Matrix& current, const std::vector<double>& mean, const Matrix& j) {
  require(mean.size() == kCurrent && j.rows == 6 && j.cols == kCurrent,
          "POSE_CLONE_AUGMENT_DIMENSION");
  const Matrix p = attitude_clone::symmetricPsd(current, kCurrent, "POSE_CURRENT_PRIOR");
  Matrix a(kJoint, kCurrent);
  for (std::size_t i = 0; i < kCurrent; ++i) a(i, i) = 1.0;
  for (std::size_t i = 0; i < 6; ++i)
    for (std::size_t q = 0; q < kCurrent; ++q) a(kCurrent + i, q) = j(i, q);
  return {symmetrize(multiply(multiply(a, p), transpose(a))), multiply(a, mean)};
}

Gaussian propagate(const Gaussian& s, const Matrix& phi, const Matrix& q) {
  validate(s);
  require(phi.rows == kCurrent && phi.cols == kCurrent && q.rows == kCurrent && q.cols == kCurrent,
          "POSE_CLONE_PROPAGATION_DIMENSION");
  Matrix a = identityMatrix(s.mean.size()), noise(s.mean.size(), s.mean.size());
  for (std::size_t i = 0; i < kCurrent; ++i) for (std::size_t j = 0; j < kCurrent; ++j) {
    a(i, j) = phi(i, j);
    noise(i, j) = q(i, j);
  }
  return {symmetrize(add(multiply(multiply(a, s.covariance), transpose(a)), noise)),
          multiply(a, s.mean)};
}

Gaussian ordinaryUpdate(const Gaussian& s, const std::vector<double>& z,
                        const Matrix& h, const Matrix& input_r) {
  validate(s);
  require(h.cols == s.mean.size() && h.rows > 0 && z.size() == h.rows &&
          input_r.rows == h.rows && input_r.cols == h.rows, "POSE_CLONE_UPDATE_DIMENSION");
  const Matrix r = attitude_clone::symmetricPsd(input_r, h.rows, "POSE_MEASUREMENT_R");
  const Matrix pht = multiply(s.covariance, transpose(h));
  const Matrix gain = transpose(solveSpd(add(multiply(h, pht), r), transpose(pht)));
  const Matrix a = subtract(identityMatrix(s.mean.size()), multiply(gain, h));
  const Matrix post = add(multiply(multiply(a, s.covariance), transpose(a)),
                          multiply(multiply(gain, r), transpose(gain)));
  const auto hm = multiply(h, s.mean);
  auto innovation = z;
  for (std::size_t i = 0; i < z.size(); ++i) innovation[i] -= hm[i];
  const auto increment = multiply(gain, innovation);
  auto mean = s.mean;
  for (std::size_t i = 0; i < mean.size(); ++i) mean[i] += increment[i];
  return {symmetrize(post), mean};
}

Gaussian footUpdate(const Gaussian& s, const FootModel& model) {
  require(s.mean.size() == kJoint, "POSE_CLONE_FOOT_REQUIRES_CLONE");
  return ordinaryUpdate(s, model.residual, model.H, model.R);
}

Gaussian reset(const Gaussian& s, const Matrix3& position_reset) {
  validate(s);
  Matrix g = identityMatrix(s.mean.size());
  setBlock(g, P_ID, P_ID, position_reset);
  setBlock(g, PHI_ID, PHI_ID, attitude_clone::leftResetJacobian(
      {s.mean[PHI_ID], s.mean[PHI_ID + 1], s.mean[PHI_ID + 2]}));
  if (s.mean.size() == kJoint)
    setBlock(g, kCloneAttitude, kCloneAttitude, attitude_clone::leftResetJacobian(
        {s.mean[kCloneAttitude], s.mean[kCloneAttitude + 1], s.mean[kCloneAttitude + 2]}));
  return {symmetrize(multiply(multiply(g, s.covariance), transpose(g))),
          std::vector<double>(s.mean.size(), 0.0)};
}

Gaussian marginalCurrent(const Gaussian& s) {
  validate(s);
  Matrix p(kCurrent, kCurrent);
  for (std::size_t i = 0; i < kCurrent; ++i)
    for (std::size_t j = 0; j < kCurrent; ++j) p(i, j) = s.covariance(i, j);
  return {p, std::vector<double>(s.mean.begin(), s.mean.begin() + kCurrent)};
}

FootModel footModel(const std::vector<Vec3>& foot0, const std::vector<Vec3>& foot1,
                    const Vec3& p0, const Matrix3& c0, const Matrix3& cbn,
                    const Vec3& blh, const Matrix& sigma, const Vec3& lever, bool horizontal_only) {
  require(!foot0.empty() && foot0.size() == foot1.size(), "POSE_CLONE_FOOT_ENDPOINT_DIMENSION");
  attitude_clone::requireRotation(c0, "POSE_CLONE_CBE");
  attitude_clone::requireRotation(cbn, "POSE_CURRENT_CBN");
  const std::size_t n = foot0.size();
  const Matrix3 e = Earth::cne(blh), c1 = multiply(e, cbn), c0t = transpose(c0);
  const Matrix3 connection = attitude_clone::nedFrameConnection(blh);
  // Subtract ECEF positions before adding sub-metre foot arms. This avoids
  // cancellation of the foot terms against the Earth's multi-million metres.
  const Vec3 delta = subtract(Earth::blh2ecef(blh), p0);
  FootModel model{std::vector<double>(3 * n), Matrix(3 * n, kJoint),
                  Matrix(), Matrix(3 * n, 6 * n)};
  for (std::size_t i = 0; i < n; ++i) {
    const Vec3 u0 = multiply(c0, subtract(foot0[i], lever));
    const Vec3 u1 = multiply(c1, subtract(foot1[i], lever));
    const Vec3 residual_ecef = add(delta, subtract(u1, u0));
    const Vec3 residual = multiply(c0t, residual_ecef);
    for (std::size_t j = 0; j < 3; ++j) model.residual[3 * i + j] = residual[j];
    // residual_nominal - residual_true, consistent with GIEngine feedback.
    setBlock(model.H, 3 * i, P_ID, multiply(c0t, subtract(e, multiply(skew(u1), connection))));
    setBlock(model.H, 3 * i, PHI_ID, multiply(c0t, multiply(skew(u1), e)));
    setBlock(model.H, 3 * i, kClonePosition, scale(c0t, -1.0));
    // Rotating the clone also rotates the body0 residual frame. Omitting the
    // residual_ecef term creates spurious common-rotation information.
    setBlock(model.H, 3 * i, kCloneAttitude,
             scale(multiply(c0t, skew(add(residual_ecef, u0))), -1.0));
    setBlock(model.foot_error_map, 3 * i, 3 * i, scale(identityMatrix3(), -1.0));
    setBlock(model.foot_error_map, 3 * i, 3 * (n + i), multiply(c0t, c1));
  }
  model.R = symmetrize(multiply(multiply(model.foot_error_map,
      attitude_clone::symmetricPsd(sigma, 6 * n, "POSE_FOOT_SIGMA")), transpose(model.foot_error_map)));
  if (horizontal_only) {
    Matrix select(2 * n, 3 * n);
    for (std::size_t i = 0; i < n; ++i) {
      select(2 * i, 3 * i) = 1.0;
      select(2 * i + 1, 3 * i + 1) = 1.0;
    }
    model.residual = multiply(select, model.residual);
    model.H = multiply(select, model.H);
    model.R = multiply(multiply(select, model.R), transpose(select));
    model.foot_error_map = multiply(select, model.foot_error_map);
  }
  return model;
}

}  // namespace legsa_v23_port_core::pose_clone
