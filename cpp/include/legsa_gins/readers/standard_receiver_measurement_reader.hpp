// 中文说明：N4E standardized receiver reader 只读取 receiver-native status CSV，不读取 trace/raw GNSS/final_v23 输出。
// English note: This reader constructs ReceiverNativeMeasurement candidates without velocity.

#pragma once

#include <filesystem>
#include <vector>

#include "legsa_gins/types/filter_types.hpp"

namespace legsa_gins::readers {

std::vector<types::ReceiverNativeMeasurement> readStandardReceiverStatusCsv(
    const std::filesystem::path& path);

}  // namespace legsa_gins::readers
