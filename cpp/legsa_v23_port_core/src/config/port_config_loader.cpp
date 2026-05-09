// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/config/port_config_loader.hpp"

#include "legsa_v23_port_core/common/earth.hpp"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <unordered_map>

namespace legsa_v23_port_core {
namespace {

std::string trim(std::string value) {
  auto not_space = [](unsigned char ch) { return !std::isspace(ch); };
  value.erase(value.begin(), std::find_if(value.begin(), value.end(), not_space));
  value.erase(std::find_if(value.rbegin(), value.rend(), not_space).base(), value.end());
  return value;
}

std::string normalizeLine(std::string line) {
  const auto hash = line.find('#');
  if (hash != std::string::npos) {
    line = line.substr(0, hash);
  }
  std::replace(line.begin(), line.end(), '[', ' ');
  std::replace(line.begin(), line.end(), ']', ' ');
  std::replace(line.begin(), line.end(), ',', ' ');
  return trim(line);
}

std::vector<double> parseVector(std::string value) {
  value = normalizeLine(value);
  std::istringstream stream(value);
  std::vector<double> out;
  double x = 0.0;
  while (stream >> x) {
    out.push_back(x);
  }
  return out;
}

Vec3 vecOrDefault(const std::unordered_map<std::string, std::string>& kv, const std::string& key, Vec3 fallback) {
  auto it = kv.find(key);
  if (it == kv.end()) {
    return fallback;
  }
  const std::vector<double> values = parseVector(it->second);
  if (values.size() < 3) {
    return fallback;
  }
  return makeVec3(values[0], values[1], values[2]);
}

Vec3 vecOrDefault(const std::unordered_map<std::string, std::string>& kv,
                  const std::string& key,
                  const std::string& alias,
                  Vec3 fallback) {
  auto it = kv.find(key);
  if (it == kv.end()) {
    it = kv.find(alias);
  }
  if (it == kv.end()) {
    return fallback;
  }
  const std::vector<double> values = parseVector(it->second);
  if (values.size() < 3) {
    return fallback;
  }
  return makeVec3(values[0], values[1], values[2]);
}

double scalarOrDefault(const std::unordered_map<std::string, std::string>& kv, const std::string& key, double fallback) {
  auto it = kv.find(key);
  if (it == kv.end()) {
    return fallback;
  }
  std::istringstream stream(it->second);
  double value = fallback;
  stream >> value;
  return value;
}

std::string stringOrDefault(const std::unordered_map<std::string, std::string>& kv,
                            const std::string& key,
                            const std::string& fallback) {
  auto it = kv.find(key);
  return it == kv.end() ? fallback : trim(it->second);
}

std::unordered_map<std::string, std::string> readKeyValues(const std::string& path) {
  std::ifstream input(path);
  if (!input) {
    throw std::runtime_error("failed to open config: " + path);
  }
  std::unordered_map<std::string, std::string> kv;
  std::string line;
  while (std::getline(input, line)) {
    line = normalizeLine(line);
    if (line.empty()) {
      continue;
    }
    auto pos = line.find('=');
    if (pos == std::string::npos) {
      pos = line.find(':');
    }
    if (pos == std::string::npos) {
      continue;
    }
    kv[trim(line.substr(0, pos))] = trim(line.substr(pos + 1));
  }
  return kv;
}

}  // namespace

PortOptions PortConfigLoader::loadKeyValue(const std::string& path) {
  return loadYamlLike(path);
}

// 中文说明：轻量 YAML-like parser 支持 R2 所需字段；不读取 trace，也不读取 final_v23 输出。
PortOptions PortConfigLoader::loadYamlLike(const std::string& path) {
  const auto kv = readKeyValues(path);
  PortOptions options;
  options.run_label = stringOrDefault(kv, "run_label", "N4H4R2_config_run");
  options.imu_path = stringOrDefault(kv, "imupath", stringOrDefault(kv, "imu_path", ""));
  options.gnss_path = stringOrDefault(kv, "gnsspath", stringOrDefault(kv, "gnss_path", ""));
  options.clean_input_provenance_label =
      stringOrDefault(kv, "clean_input_provenance_label", options.clean_input_provenance_label);
  options.config_policy_evidence_status =
      stringOrDefault(kv, "config_policy_evidence_status", options.config_policy_evidence_status);

  Vec3 initpos = vecOrDefault(kv, "initpos", options.init_pos_blh_rad_m);
  initpos[0] *= D2R;
  initpos[1] *= D2R;
  options.init_pos_blh_rad_m = initpos;
  options.init_vel_ned_mps = vecOrDefault(kv, "initvel", options.init_vel_ned_mps);
  options.init_att_rad = scale(vecOrDefault(kv, "initatt", options.init_att_rad), D2R);
  options.antlever_m = vecOrDefault(kv, "antlever", options.antlever_m);
  options.init_pos_std_m = vecOrDefault(kv, "initposstd", options.init_pos_std_m);
  options.init_vel_std_mps = vecOrDefault(kv, "initvelstd", options.init_vel_std_mps);
  options.init_att_std_rad = scale(vecOrDefault(kv, "initattstd", scale(options.init_att_std_rad, R2D)), D2R);

  options.init_imu_error.gyrbias = scale(vecOrDefault(kv, "initgyrbias", options.init_imu_error.gyrbias), D2R / 3600.0);
  options.init_imu_error.accbias = scale(vecOrDefault(kv, "initaccbias", options.init_imu_error.accbias), 1.0e-5);
  options.init_imu_error.gyrscale = scale(vecOrDefault(kv, "initgyrscale", options.init_imu_error.gyrscale), 1.0e-6);
  options.init_imu_error.accscale = scale(vecOrDefault(kv, "initaccscale", options.init_imu_error.accscale), 1.0e-6);

  options.imunoise.gyr_arw = scale(vecOrDefault(kv, "arw", scale(options.imunoise.gyr_arw, 60.0 / D2R)), D2R / 60.0);
  options.imunoise.acc_vrw = scale(vecOrDefault(kv, "vrw", scale(options.imunoise.acc_vrw, 60.0)), 1.0 / 60.0);
  options.imunoise.gyrbias_std = scale(vecOrDefault(kv, "gbstd", scale(options.imunoise.gyrbias_std, 3600.0 / D2R)), D2R / 3600.0);
  options.imunoise.accbias_std = scale(vecOrDefault(kv, "abstd", scale(options.imunoise.accbias_std, 1.0e5)), 1.0e-5);
  options.imunoise.gyrscale_std = scale(vecOrDefault(kv, "gsstd", scale(options.imunoise.gyrscale_std, 1.0e6)), 1.0e-6);
  options.imunoise.accscale_std = scale(vecOrDefault(kv, "asstd", scale(options.imunoise.accscale_std, 1.0e6)), 1.0e-6);
  options.imunoise.corr_time = scalarOrDefault(kv, "corrtime", options.imunoise.corr_time / 3600.0) * 3600.0;

  options.init_imu_error_std.gyrbias =
      scale(vecOrDefault(kv, "initgyrbiasstd", "initbgstd", scale(options.imunoise.gyrbias_std, 3600.0 / D2R)),
            D2R / 3600.0);
  options.init_imu_error_std.accbias =
      scale(vecOrDefault(kv, "initaccbiasstd", "initbastd", scale(options.imunoise.accbias_std, 1.0e5)), 1.0e-5);
  options.init_imu_error_std.gyrscale =
      scale(vecOrDefault(kv, "initgyrscalestd", "initsgstd", scale(options.imunoise.gyrscale_std, 1.0e6)),
            1.0e-6);
  options.init_imu_error_std.accscale =
      scale(vecOrDefault(kv, "initaccscalestd", "initsastd", scale(options.imunoise.accscale_std, 1.0e6)),
            1.0e-6);

  options.starttime = scalarOrDefault(kv, "starttime", options.starttime);
  options.endtime = scalarOrDefault(kv, "endtime", options.endtime);
  options.imudatalen = static_cast<int>(scalarOrDefault(kv, "imudatalen", options.imudatalen));
  options.imudatarate = scalarOrDefault(kv, "imudatarate", options.imudatarate);
  return options;
}

}  // namespace legsa_v23_port_core
