#include "hartley_inekf/backend.hpp"
#include "InEKF.h"

#include <Eigen/Dense>

#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

using hartley::ContactMeasurement;
using hartley::ContinuousNoiseDensity;
using hartley::HartleyInEkf;
using hartley::Matrix;
using hartley::Matrix3;
using hartley::StateMean;
using hartley::Vector3;

struct Counts {
  long rows{0};
  long imu_rows{0};
  long contact_rows{0};
  long contact_values{0};
  long kinematic_rows{0};
  long kinematic_points{0};
  long propagation_calls{0};
  long correction_calls{0};
  long correction_measurements{0};
  long additions{0};
  long removals{0};
};

struct Differences {
  double rotation{0.0};
  double velocity{0.0};
  double position{0.0};
  double gyro_bias{0.0};
  double accelerometer_bias{0.0};
  double contacts{0.0};
  double covariance{0.0};
  double covariance_relative_frobenius{0.0};
  long active_id_mismatch_count{0};
  long dimension_mismatch_count{0};
};

std::string jsonArray(const Matrix& matrix) {
  std::ostringstream stream;
  stream << '[' << std::setprecision(17);
  for (int row = 0; row < matrix.rows(); ++row) {
    for (int column = 0; column < matrix.cols(); ++column) {
      if (row != 0 || column != 0) stream << ',';
      stream << matrix(row, column);
    }
  }
  stream << ']';
  return stream.str();
}

std::vector<std::string> split(const std::string& line) {
  std::istringstream stream(line);
  std::vector<std::string> fields;
  std::string field;
  while (stream >> field) fields.push_back(field);
  return fields;
}

Matrix reorderOfficialCovariance(const inekf::RobotState& official_const,
                                 const std::map<int, int>& official_contacts,
                                 const std::vector<int>& sorted_ids) {
  inekf::RobotState official = official_const;
  const Matrix source = official.getP();
  const int dimension = source.rows();
  Matrix selection = Matrix::Zero(dimension, dimension);
  selection.block(0, 0, 9, 9).setIdentity();
  for (std::size_t index = 0; index < sorted_ids.size(); ++index) {
    const int official_x_column = official_contacts.at(sorted_ids[index]);
    const int official_error_offset = 3 * official_x_column - 6;
    selection.block<3, 3>(9 + 3 * index, official_error_offset) =
        Matrix3::Identity();
  }
  selection.block<6, 6>(dimension - 6, dimension - 6) =
      Eigen::Matrix<double, 6, 6>::Identity();
  return selection * source * selection.transpose();
}

void updateDifferences(inekf::InEKF& official, const HartleyInEkf& candidate,
                       Differences& differences) {
  const inekf::RobotState official_state = official.getState();
  inekf::RobotState mutable_state = official_state;
  const auto official_contacts = official.getEstimatedContactPositions();
  std::vector<int> official_ids;
  for (const auto& entry : official_contacts) official_ids.push_back(entry.first);
  const auto candidate_ids = candidate.activeContactIdentities();
  if (official_ids != candidate_ids) ++differences.active_id_mismatch_count;
  if (mutable_state.dimP() != candidate.stateDimension()) {
    ++differences.dimension_mismatch_count;
    return;
  }
  differences.rotation =
      std::max(differences.rotation,
               (mutable_state.getRotation() - candidate.stateMean().rotation).norm());
  differences.velocity =
      std::max(differences.velocity,
               (mutable_state.getVelocity() - candidate.stateMean().velocity).norm());
  differences.position =
      std::max(differences.position,
               (mutable_state.getPosition() - candidate.stateMean().position).norm());
  differences.gyro_bias =
      std::max(differences.gyro_bias,
               (mutable_state.getGyroscopeBias() - candidate.stateMean().gyro_bias).norm());
  differences.accelerometer_bias = std::max(
      differences.accelerometer_bias,
      (mutable_state.getAccelerometerBias() - candidate.stateMean().accelerometer_bias)
          .norm());
  const Matrix official_x = mutable_state.getX();
  for (const int id : candidate_ids) {
    differences.contacts =
        std::max(differences.contacts,
                 (official_x.block<3, 1>(0, official_contacts.at(id)) -
                  candidate.stateMean().contacts.at(id))
                     .norm());
  }
  if (official_ids == candidate_ids) {
    const Matrix reordered =
        reorderOfficialCovariance(official_state, official_contacts, candidate_ids);
    differences.covariance =
        std::max(differences.covariance,
                 (reordered - candidate.stateCovariance()).cwiseAbs().maxCoeff());
    differences.covariance_relative_frobenius = std::max(
        differences.covariance_relative_frobenius,
        (reordered - candidate.stateCovariance()).norm() /
            std::max(1.0e-30, reordered.norm()));
  }
}

}  // namespace

int main(int argc, char** argv) {
  if (argc != 2) {
    std::cerr << "usage: official_regression <imu_kinematic_measurements.txt>\n";
    return 2;
  }
  try {
    inekf::RobotState initial_official;
    Matrix3 rotation;
    rotation << 1.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, -1.0;
    initial_official.setRotation(rotation);
    initial_official.setVelocity(Vector3::Zero());
    initial_official.setPosition(Vector3::Zero());
    initial_official.setGyroscopeBias(Vector3::Zero());
    initial_official.setAccelerometerBias(Vector3::Zero());
    inekf::NoiseParams official_noise;
    official_noise.setGyroscopeNoise(0.01);
    official_noise.setAccelerometerNoise(0.1);
    official_noise.setGyroscopeBiasNoise(1.0e-5);
    official_noise.setAccelerometerBiasNoise(1.0e-4);
    official_noise.setContactNoise(0.01);
    inekf::InEKF official(initial_official, official_noise);

    StateMean initial_candidate;
    initial_candidate.rotation = rotation;
    const ContinuousNoiseDensity candidate_noise{0.01, 0.1, 1.0e-5, 1.0e-4,
                                                  0.01};
    HartleyInEkf candidate(initial_candidate, Matrix::Identity(15, 15),
                           candidate_noise,
                           hartley::BackendIdentity::OFFICIAL_CPP_EARLY_REGRESSION);

    std::ifstream input(argv[1]);
    if (!input) throw std::runtime_error("official dataset could not be opened");
    Counts counts;
    Differences differences;
    std::map<int, bool> contact_indicators;
    Eigen::Matrix<double, 6, 1> imu = Eigen::Matrix<double, 6, 1>::Zero();
    Eigen::Matrix<double, 6, 1> previous_imu = Eigen::Matrix<double, 6, 1>::Zero();
    double previous_time = 0.0;
    std::string line;
    while (std::getline(input, line)) {
      const auto fields = split(line);
      if (fields.empty()) continue;
      ++counts.rows;
      const double time = std::stod(fields.at(1));
      if (fields[0] == "IMU") {
        ++counts.imu_rows;
        if (fields.size() != 8) throw std::runtime_error("malformed IMU row");
        for (int index = 0; index < 6; ++index) imu(index) = std::stod(fields[2 + index]);
        const double dt = time - previous_time;
        if (dt > 1.0e-6 && dt < 1.0) {
          official.Propagate(previous_imu, dt);
          candidate.propagate(previous_imu.head<3>(), previous_imu.tail<3>(), dt);
          ++counts.propagation_calls;
        }
      } else if (fields[0] == "CONTACT") {
        ++counts.contact_rows;
        if ((fields.size() - 2) % 2 != 0) {
          throw std::runtime_error("malformed CONTACT row");
        }
        std::vector<std::pair<int, bool>> contacts;
        for (std::size_t index = 2; index < fields.size(); index += 2) {
          const int id = std::stoi(fields[index]);
          const bool active = std::stod(fields[index + 1]) != 0.0;
          contacts.emplace_back(id, active);
          contact_indicators[id] = active;
          ++counts.contact_values;
        }
        official.setContacts(contacts);
      } else if (fields[0] == "KINEMATIC") {
        ++counts.kinematic_rows;
        if ((fields.size() - 2) % 44 != 0) {
          throw std::runtime_error("malformed KINEMATIC row");
        }
        inekf::vectorKinematics official_measurements;
        std::vector<ContactMeasurement> candidate_measurements;
        for (std::size_t start = 2; start < fields.size(); start += 44) {
          const int id = std::stoi(fields[start]);
          Eigen::Quaterniond quaternion(std::stod(fields[start + 1]),
                                        std::stod(fields[start + 2]),
                                        std::stod(fields[start + 3]),
                                        std::stod(fields[start + 4]));
          quaternion.normalize();
          Eigen::Matrix4d pose = Eigen::Matrix4d::Identity();
          pose.block<3, 3>(0, 0) = quaternion.toRotationMatrix();
          pose.block<3, 1>(0, 3) =
              Vector3(std::stod(fields[start + 5]), std::stod(fields[start + 6]),
                      std::stod(fields[start + 7]));
          Eigen::Matrix<double, 6, 6> covariance;
          for (int row = 0; row < 6; ++row) {
            for (int column = 0; column < 6; ++column) {
              covariance(row, column) =
                  std::stod(fields[start + 8 + row * 6 + column]);
            }
          }
          official_measurements.emplace_back(id, pose, covariance);
          candidate_measurements.push_back(
              {id, pose.block<3, 1>(0, 3), covariance.block<3, 3>(3, 3)});
          ++counts.kinematic_points;
        }

        const std::vector<int> active_before = candidate.activeContactIdentities();
        const Matrix3 rotation_before = candidate.stateMean().rotation;
        std::vector<ContactMeasurement> corrections;
        std::vector<ContactMeasurement> additions;
        std::vector<int> removals;
        for (const auto& measurement : candidate_measurements) {
          const auto indicator = contact_indicators.find(measurement.leg_id);
          if (indicator == contact_indicators.end()) continue;
          const bool found = std::binary_search(active_before.begin(), active_before.end(),
                                                measurement.leg_id);
          if (!indicator->second && found) {
            removals.push_back(measurement.leg_id);
          } else if (indicator->second && !found) {
            additions.push_back(measurement);
          } else if (indicator->second && found) {
            corrections.push_back(measurement);
          }
        }
        official.CorrectKinematics(official_measurements);
        if (!corrections.empty()) {
          std::sort(corrections.begin(), corrections.end(),
                    [](const auto& lhs, const auto& rhs) {
                      return lhs.leg_id < rhs.leg_id;
                    });
          candidate.correctContactSubsetForOfficialEarlyRegression(corrections);
          ++counts.correction_calls;
          counts.correction_measurements += corrections.size();
        }
        if (!removals.empty()) {
          candidate.removeContacts(removals);
          counts.removals += removals.size();
        }
        if (!additions.empty()) {
          // The pinned early implementation captures R at entry to CorrectKinematics
          // and uses that pre-correction value for later same-call augmentation.
          const Matrix3 rotation_after = candidate.stateMean().rotation;
          for (auto& addition : additions) {
            addition.foot_position_body = rotation_after.transpose() * rotation_before *
                                          addition.foot_position_body;
            addition.covariance_body_m2 =
                rotation_after.transpose() * rotation_before *
                addition.covariance_body_m2 * rotation_before.transpose() *
                rotation_after;
          }
          candidate.augmentContacts(additions);
          counts.additions += additions.size();
        }
      } else {
        throw std::runtime_error("unknown official dataset row type");
      }
      previous_time = time;
      previous_imu = imu;
      updateDifferences(official, candidate, differences);
    }

    inekf::RobotState final_official = official.getState();
    const double covariance_asymmetry =
        (candidate.stateCovariance() - candidate.stateCovariance().transpose())
            .cwiseAbs()
            .maxCoeff();
    Eigen::SelfAdjointEigenSolver<Matrix> eigen(candidate.stateCovariance());
    const bool pass = counts.rows == 59976 && counts.imu_rows == 19992 &&
                      counts.contact_rows == 19992 && counts.kinematic_rows == 19992 &&
                      counts.propagation_calls == 19992 && counts.additions == 34 &&
                      counts.removals == 33 && counts.correction_calls == 19780 &&
                      counts.correction_measurements == 26741 &&
                      differences.active_id_mismatch_count == 0 &&
                      differences.dimension_mismatch_count == 0 &&
                      differences.rotation < 5.0e-8 && differences.velocity < 5.0e-8 &&
                      differences.position < 5.0e-8 && differences.gyro_bias < 5.0e-8 &&
                      differences.accelerometer_bias < 5.0e-8 &&
                      differences.contacts < 5.0e-8 &&
                      differences.covariance_relative_frobenius < 2.0e-7 &&
                      differences.covariance < 2.0e-8;

    const auto final_ids = candidate.activeContactIdentities();
    const int group_matrix_dimension =
        5 + static_cast<int>(final_ids.size());
    Matrix final_candidate_x =
        Matrix::Identity(group_matrix_dimension, group_matrix_dimension);
    final_candidate_x.block<3, 3>(0, 0) = candidate.stateMean().rotation;
    final_candidate_x.block<3, 1>(0, 3) = candidate.stateMean().velocity;
    final_candidate_x.block<3, 1>(0, 4) = candidate.stateMean().position;
    for (std::size_t index = 0; index < final_ids.size(); ++index) {
      final_candidate_x.block<3, 1>(0, 5 + static_cast<int>(index)) =
          candidate.stateMean().contacts.at(final_ids[index]);
    }
    Matrix final_candidate_theta(6, 1);
    final_candidate_theta.block<3, 1>(0, 0) = candidate.stateMean().gyro_bias;
    final_candidate_theta.block<3, 1>(3, 0) =
        candidate.stateMean().accelerometer_bias;

    std::cout << std::setprecision(17)
              << "{\"pass\":" << (pass ? "true" : "false")
              << ",\"rows\":" << counts.rows << ",\"imu_rows\":" << counts.imu_rows
              << ",\"contact_rows\":" << counts.contact_rows
              << ",\"contact_values\":" << counts.contact_values
              << ",\"kinematic_rows\":" << counts.kinematic_rows
              << ",\"kinematic_points\":" << counts.kinematic_points
              << ",\"propagation_calls\":" << counts.propagation_calls
              << ",\"correction_calls\":" << counts.correction_calls
              << ",\"correction_measurements\":" << counts.correction_measurements
              << ",\"additions\":" << counts.additions
              << ",\"removals\":" << counts.removals
              << ",\"final_active_contacts\":"
              << candidate.activeContactIdentities().size()
              << ",\"final_state_dimension\":" << candidate.stateDimension()
              << ",\"max_rotation_fro_difference\":" << differences.rotation
              << ",\"max_velocity_norm_difference\":" << differences.velocity
              << ",\"max_position_norm_difference\":" << differences.position
              << ",\"max_gyro_bias_norm_difference\":" << differences.gyro_bias
              << ",\"max_accelerometer_bias_norm_difference\":"
              << differences.accelerometer_bias
              << ",\"max_contact_norm_difference\":" << differences.contacts
              << ",\"max_covariance_abs_difference\":" << differences.covariance
              << ",\"max_covariance_relative_frobenius_difference\":"
              << differences.covariance_relative_frobenius
              << ",\"active_id_mismatch_count\":"
              << differences.active_id_mismatch_count
              << ",\"dimension_mismatch_count\":"
              << differences.dimension_mismatch_count
              << ",\"candidate_covariance_asymmetry\":" << covariance_asymmetry
              << ",\"candidate_covariance_min_eigenvalue\":"
              << eigen.eigenvalues().minCoeff()
              << ",\"official_final_state_dimension\":" << final_official.dimP()
              << ",\"final_candidate_x\":" << jsonArray(final_candidate_x)
              << ",\"final_candidate_theta\":"
              << jsonArray(final_candidate_theta)
              << ",\"final_candidate_covariance\":"
              << jsonArray(candidate.stateCovariance())
              << "}\n";
    return pass ? 0 : 1;
  } catch (const std::exception& error) {
    std::cerr << "official regression error: " << error.what() << '\n';
    return 1;
  }
}
