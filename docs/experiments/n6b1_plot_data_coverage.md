# N6B1 Plot Data Coverage

Figure existence is not enough for N6B1. Mandatory figures must also report the
series count, plotted row count, x/y ranges, source IDs where relevant, and
reason codes for suspected empty plots.

Coverage rules:

- clean time-series figures require at least 1000 plotted rows and at least 200
  seconds of time-axis range;
- stress figures must include both no-source-aware and N6B series;
- weight trace figures must include at least four source IDs;
- spike zoom figures must include raw Doppler scale and residual or innovation
  evidence;
- any failed mandatory figure makes visual validation fail.

Coverage checks are diagnostic only. They do not tune weights, remove epochs,
or alter solver output.
