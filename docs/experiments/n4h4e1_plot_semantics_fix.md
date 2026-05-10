# N4H4E1 Plot Semantics Fix

The legacy N4H4E XY error-vector figures connected error samples with lines.
That made the error cloud easy to misread as a trajectory.

N4H4E1 changes vector-cloud views to scatter plots with an origin cross. Time
series remain line plots when the horizontal axis is time.

The port-minus-final_v23 up-difference diagnostic keeps the full series, marks
the first sample, and adds a first-5-second zoom. It does not crop, delete, or
reweight samples.

These fixes improve visual semantics only. They are not solver changes, output
corrections, factor implementations, or paper performance claims.
