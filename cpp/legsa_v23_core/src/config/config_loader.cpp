#include "legsa_v23_core/config/config_loader.hpp"

#include "legsa_v23_core/common/constants.hpp"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace legsa_v23_core {
namespace {

// 中文说明：最小 parser 只处理 key: value 或 key=value，复杂 YAML 暂记为 evidence_missing。
std::string trim(const std::string& input) {
  const auto first = input.find_first_not_of(" \t\r\n");
  if (first == std::string::npos) {
    return "";
  }
  const auto last = input.find_last_not_of(" \t\r\n");
  return input.substr(first, last - first + 1);
}

std::string lower(std::string input) {
  std::transform(input.begin(), input.end(), input.begin(), [](unsigned char value) {
    return static_cast<char>(std::tolower(value));
  });
  return input;
}

std::string stripQuotes(const std::string& input) {
  std::string value = trim(input);
  if (value.size() >= 2 && ((value.front() == '"' && value.back() == '"') ||
                            (value.front() == '\'' && value.back() == '\''))) {
    return value.substr(1, value.size() - 2);
  }
  return value;
}

std::vector<double> parseVector3(const std::string& value, const std::string& key) {
  std::string normalized = value;
  for (char& ch : normalized) {
    if (ch == '[' || ch == ']' || ch == ',') {
      ch = ' ';
    }
  }
  std::istringstream parser(normalized);
  std::vector<double> values;
  double number = 0.0;
  while (parser >> number) {
    values.push_back(number);
  }
  if (values.size() != 3) {
    throw std::runtime_error("expected 3 values for key: " + key);
  }
  return values;
}

Vector3 toVector3(const std::vector<double>& values) {
  return {values[0], values[1], values[2]};
}

Vector3 degreesVectorToRadians(const std::vector<double>& values) {
  return {values[0] * kDegToRad, values[1] * kDegToRad, values[2] * kDegToRad};
}

}  // namespace

GINSOptions ConfigLoader::load(const std::string& path) {
  // 中文说明：配置 loader 只读取 proposed runtime 输入路径和初始状态，不读取 trace 或 final_v23 输出。
  std::ifstream input(path);
  if (!input) {
    throw std::runtime_error("failed to open config: " + path);
  }

  GINSOptions options;
  std::string line;
  int line_number = 0;
  while (std::getline(input, line)) {
    ++line_number;
    const auto comment_pos = line.find('#');
    const std::string cleaned = trim(comment_pos == std::string::npos ? line : line.substr(0, comment_pos));
    if (cleaned.empty()) {
      continue;
    }

    const auto colon_pos = cleaned.find(':');
    const auto equal_pos = cleaned.find('=');
    const auto split_pos = colon_pos == std::string::npos ? equal_pos : colon_pos;
    if (split_pos == std::string::npos) {
      options.clean_input_provenance_label = "evidence_missing_minimal_config_parser_skipped_complex_yaml";
      continue;
    }

    const std::string key = lower(trim(cleaned.substr(0, split_pos)));
    const std::string value = stripQuotes(cleaned.substr(split_pos + 1));
    if (key.find("trace") != std::string::npos || key.find("final_v23_output") != std::string::npos) {
      throw std::runtime_error("forbidden solver input key in N4H4A config at line " + std::to_string(line_number));
    }

    if (key == "imupath") {
      options.imu_path = value;
    } else if (key == "gnsspath") {
      options.gnss_path = value;
    } else if (key == "outputpath") {
      options.output_path = value;
    } else if (key == "starttime") {
      options.start_time = std::stod(value);
    } else if (key == "endtime") {
      options.end_time = std::stod(value);
    } else if (key == "imudatalen") {
      options.imu_data_len = std::stoi(value);
    } else if (key == "imudatarate") {
      options.imu_data_rate = std::stod(value);
    } else if (key == "initpos") {
      const auto values = parseVector3(value, key);
      options.init_state.pos_blh_rad_m = {values[0] * kDegToRad, values[1] * kDegToRad, values[2]};
    } else if (key == "initvel") {
      options.init_state.vel_ned_mps = toVector3(parseVector3(value, key));
    } else if (key == "initatt") {
      options.init_state.euler_rpy_rad = degreesVectorToRadians(parseVector3(value, key));
    } else if (key == "initposstd") {
      options.init_pos_std = toVector3(parseVector3(value, key));
    } else if (key == "initvelstd") {
      options.init_vel_std = toVector3(parseVector3(value, key));
    } else if (key == "initattstd") {
      options.init_att_std = degreesVectorToRadians(parseVector3(value, key));
    } else if (key == "antlever") {
      options.antlever = toVector3(parseVector3(value, key));
    } else if (key == "clean_input_provenance_label") {
      options.clean_input_provenance_label = value.empty() ? "evidence_missing" : value;
    }
  }

  return options;
}

}  // namespace legsa_v23_core
