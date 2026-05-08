"""process_data-compatible input reconstruction helpers.

中文说明：本包只重建 final_v23-style `.gnss` / `.imu` runtime 输入，
不实现 solver、不解析 raw Doppler，也不做数值性能结论。
"""

from legsa_gins.input_generation.process_data_compat import (
    generate_process_data_compat_inputs,
)

__all__ = ["generate_process_data_compat_inputs"]
