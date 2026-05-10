# N5A Raw GNSS Message Scan

The raw GNSS scan distinguishes UBX-NAV-PVT, UBX-RXM-RAWX, UBX-RXM-SFRBX, RTCM/correction rows, and unknown messages in `gnss1-raw.csv`, `gnss2-raw.csv`, and `corr-raw.csv`.

NAV-PVT velocity is not raw Doppler. `.gnss vn/ve/vd` remains baseline receiver-native velocity. RAWX `doMes` is the only N5A satellite-level Doppler source.

The scan report must keep `pvt_velocity_not_raw_doppler=true`. If RAWX is absent, readiness must report `rawx_missing`; it must not fall back to NAV-PVT velocity or `.gnss vn/ve/vd`.

No trace solver input. No final_v23 output solver input. No paper performance claim.
