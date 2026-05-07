// 中文说明：standardized receiver reader 优先使用 algo_time_sec，不直接比较 GNSS/Go2 raw time；
// 不读取 trace/raw GNSS/final_v23 输出。
// English note: This reader constructs ReceiverNativeMeasurement candidates without velocity.

#pragma once

#include <filesystem>
#include <vector>

#include "legsa_gins/types/filter_types.hpp"

namespace legsa_gins::readers {

std::vector<types::ReceiverNativeMeasurement> readStandardReceiverStatusCsv(
    const std::filesystem::path& path);

}  // namespace legsa_gins::readers
