# Clean vs noisy replay comparison

N4H2G compares two provenance roles:

- noisy historical artifact: dual_final_v23 runtime evidence that likely
  contains Gaussian yaw noise;
- clean replay: reconstructed status-yaw input with no synthetic yaw noise,
  no outlier injection, and no outage injection.

The comparison reports metric deltas, clean/noisy input yaw differences, and
clean/noisy NAV yaw differences. It is not a paper performance claim and does
not modify solver output.

If clean replay remains close to the dual official reference, later experiments
should prefer the clean replay or explicitly label noisy replay as noisy/stress
provenance.
