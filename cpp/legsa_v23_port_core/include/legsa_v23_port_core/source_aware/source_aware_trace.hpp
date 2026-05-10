// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference; LegSA-owned N6A extension.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: source-aware LSIM/OIM measurement weighting extension, not final_v23 output substitution.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：N6A trace 只作为 runtime-only 审计输出，不进入 solver 调权。
//
// LegSA-GINS N6A source-aware trace writer.
// 中文说明：trace 是事后审计输出，不允许反向进入 source-aware 调权。

#pragma once

#include "legsa_v23_port_core/source_aware/measurement_source.hpp"

#include <string>
#include <vector>

namespace legsa_v23_port_core::source_aware {

struct SourceAwareTraceRow {
  double time = 0.0;
  std::size_t update_index = 0;
  SourceWeightResult result;
};

class SourceAwareTrace {
 public:
  void add(double time, std::size_t update_index, const SourceWeightResult& result);
  bool empty() const;
  const std::vector<SourceAwareTraceRow>& rows() const;
  SourceAwareRuntimeStats stats() const;
  void writeCsv(const std::string& output_dir) const;

 private:
  std::vector<SourceAwareTraceRow> rows_;
};

}  // namespace legsa_v23_port_core::source_aware
