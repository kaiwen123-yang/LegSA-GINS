# N5C Raw Doppler Factor Diagnostics

The factor diagnostics report checks whether the N5B raw Doppler velocity factor is internally usable before comparing solver variants.

Reported fields include:

- epoch and valid-epoch counts;
- time range and clean replay overlap;
- satellite-count min, median, and max;
- `std_vn/std_ve/std_vd` p50, p95, and max;
- NED velocity ranges;
- gap statistics;
- quality-flag counts;
- suspicious velocity or standard-deviation spikes.

These checks do not establish paper performance. They only decide whether the factor is stable enough for the N5C diagnostic ablation matrix.
