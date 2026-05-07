// 中文说明：writer 只写合同化输出给后续验证或 evaluator；不做 output-only correction，不删除 bad epochs，也不参与 solver。
// English note: comments define module responsibility and safety boundaries only.

#include "legsa_gins/io/eval_nav_writer_bridge.hpp"

#include <iomanip>
#include <stdexcept>
#include <utility>

namespace legsa_gins::io {

EvalNavWriterBridge::EvalNavWriterBridge(std::filesystem::path output_dir)
    : path_(std::move(output_dir) / "EVAL_NAV.csv") {
  std::filesystem::create_directories(path_.parent_path());
  stream_.open(path_);
  if (!stream_) {
    throw std::runtime_error("Failed to open EVAL_NAV output: " + path_.string());
  }
  stream_ << "timestamp,lat_deg,lon_deg,height_m,vn_mps,ve_mps,vd_mps,roll_deg,"
             "pitch_deg,yaw_deg,status,source_role\n";
}

EvalNavWriterBridge::~EvalNavWriterBridge() { close(); }

void EvalNavWriterBridge::write(const types::NavState& state) {
  if (has_last_timestamp_ && state.tow < last_timestamp_) {
    throw std::runtime_error("EVAL_NAV timestamp must be monotonically non-decreasing.");
  }
  has_last_timestamp_ = true;
  last_timestamp_ = state.tow;

  // EVAL_NAV 字段必须稳定，后续 evaluator 依赖这个格式；writer 不参与 solver。
  // EVAL_NAV columns stay stable for evaluator compatibility; writer is not solver logic.
  stream_ << std::fixed << std::setprecision(9) << state.tow << ','
          << std::setprecision(12) << state.lat_deg << ',' << state.lon_deg << ','
          << std::setprecision(6) << state.height_m << ',' << state.vn_mps << ','
          << state.ve_mps << ',' << state.vd_mps << ',' << state.roll_deg << ','
          << state.pitch_deg << ',' << state.yaw_deg << ',' << state.status << ','
          << state.source_role << '\n';
}

void EvalNavWriterBridge::close() {
  if (stream_.is_open()) {
    stream_.flush();
    stream_.close();
  }
}

const std::filesystem::path& EvalNavWriterBridge::path() const { return path_; }

}  // namespace legsa_gins::io
