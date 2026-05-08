# N4H0 Measurement Floor Sanity Prompt Summary

Stage N4H0 adds a receiver-native BY2 measurement-floor sanity check. It directly evaluates standardized `gnss1` and `gnss2` status position and transverse heading candidates against trace evaluation-only reference, without running proposed solver logic or making performance claims.

No local BY2 absolute paths are stored in this prompt summary.
