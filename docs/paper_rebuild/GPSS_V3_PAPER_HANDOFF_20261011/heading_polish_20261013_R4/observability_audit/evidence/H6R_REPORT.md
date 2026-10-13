# LSE01 H6R full-precision recovery

Terminal: `PASS_LSE01_H6R_REAL_DATA_GAUGE_AND_OBSERVABILITY_CONFIRMED`

The original blocked H6 transaction and its 0.0005 m tolerance remain unchanged. The exact old
six-significant-digit compatibility stream reproduced all six blocked maxima before the float64
NPZ files were opened. The authoritative float64 comparison passed every epoch, active leg and coordinate.

## Full-precision contact maxima

- H6R_YAW_M150: 1.3724919198563842e-07 m
- H6R_YAW_M100: 6.7140574340601526e-08 m
- H6R_YAW_M050: 3.9206810879312983e-08 m
- H6R_YAW_P050: 6.5125661292082978e-08 m
- H6R_YAW_P100: 6.6403764006735442e-08 m
- H6R_YAW_P150: 1.8977692824628012e-07 m

The five frozen windows WIN000--WIN004 were reused byte-identically; no window was reselected.
Ideal bias-free nullity is four (three translations and gravity-axis rotation), and the known
four-dimensional gauge is confirmed in the bias-augmented real-trajectory model.

NIS is conditioned by contact count, exact identity set, and static/dynamic four-contact periods.
Low NIS is interpreted only as conservative and/or correlated proxy statistics, not accuracy.

All reference, trace, GNSS, onboard pose/yaw, LegSA-output and EXT-output access counters are zero.
H7 and EXT06 remain unexecuted.
