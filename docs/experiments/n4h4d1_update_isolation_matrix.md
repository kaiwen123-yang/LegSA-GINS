# N4H4D1 Update-Isolation Matrix

N4H4D1 runs diagnostic variants to separate propagation, measurement update, and state feedback failure modes:

- all updates current
- propagation only
- position only
- velocity only
- yaw only
- position and velocity only
- position and yaw only
- velocity and yaw only
- all updates without state feedback

These variants intentionally change solver switches and therefore are not performance results. They exist only to classify likely failure sources such as mechanization/initialization, update sign or lever-arm issues, yaw convention issues, covariance issues, or state feedback sign issues.
