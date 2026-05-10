"""Raw GNSS utilities for N5A.

中文说明：N5A 只把卫星级 RAWX Doppler 作为 raw Doppler 证据；NAV-PVT 速度和
15 列 .gnss 速度仍属于 receiver-native baseline velocity，不能冒充 raw Doppler。
"""
