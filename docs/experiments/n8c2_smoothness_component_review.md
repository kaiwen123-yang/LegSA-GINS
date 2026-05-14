# N8C2 smoothness component review

N8C2 splits SmoothnessFactor residual proxies into:

- position smoothness;
- velocity smoothness;
- yaw smoothness;
- roll/pitch smoothness;
- other attitude smoothness when available.

The review identifies spike components and records whether yaw smoothness still
dominates after weak-yaw policy.  It may recommend splitting smoothness weights
or redesigning smoothness as physical process/kinematic factors, but it must not
delete smoothness as a final shortcut.
