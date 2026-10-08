# Physical phase errors in the common navigation state

The BY development working M2 model now enters the same R/p/v/b/contact/integer navigation graph. It does not produce an independent heading observation. The optional configuration is `configs/paper_rebuild/joint_navigation/BY_PHASE_NOISE_M2_WORKING.json`; its parameters and qualification limits come from `BY_NOISE_CALIBRATION.json`.

For each physical receiver-differenced signal, the graph estimates a meter-valued beta process. The observation is `y = B R b + A N + D beta`, with observation covariance `Q_original + sigma_white^2 D D^T`. The stationary OU transition uses the actual signal time interval. Integer slips and changing reference satellites do not reset this physical error process. Missing signals retain their latest state for later propagation. Old coordinates can be eliminated with their full joint information.

The pre-consumption external prediction contains existing beta means, the full cross covariance with pose/velocity/bias/integer states, and the new OU innovations. Previously unseen signals contribute their stationary prior; rows involving unknown integer coordinates remain unscored. Checkpoints and shared linearization anchors identify beta by physical signal and epoch, not by branch-local key numbers.

The candidate proposal integrates out this same stationary process, retaining complete cross-epoch covariance. Original raw epochs remain unchanged. A correlated fixed-integer length problem cannot use the sum of independent epoch sphere costs. The implemented profile uses the maximum of marginal sphere lower bounds and a feasible product-sphere upper bound. A candidate between those bounds remains unresolved and retained. Raw enumeration completeness and length-support completeness are separate. No local optimizer failure or high feasible cost establishes exclusion.

Necessary mathematical checks:

- Explicit beta/OU graph elimination matches the dense original-plus-white-plus-OU covariance, including pivot changes, slips and missing signals.
- An independently assembled future observation graph, with full initial beta/state cross covariance, matches the prediction: maximum mean difference 8.26e-11 and covariance difference 6.85e-13. The Gaussian shared-anchor case gives 1.97e-11 and 3.91e-13.
- In the correlated two-sphere example, adding marginal costs incorrectly gives 40; the valid lower bound is 20 and the feasible joint value is 22.2222. A second example has lower 24, upper 26.6667 and budget 26.1245; its identity remains unresolved, and active support is not declared complete.
- Without an optional noise model, the existing graph path remains in use. The independent-epoch candidate numerical path remains unchanged.

These checks establish the likelihood implementation, not correct integer acceptance or improved navigation. The BY likelihood calibration had a correlation-time boundary optimum and low validation residual energy, so the model remains conditional and probability calibration remains incomplete. The next comparisons are the same continuous 90-second support-failure scene with the future separator and the same native-increment BY 96–106 second interval used by the existing U1 result. Existing full-duration runs continue under their recorded source snapshots. Frozen BYO/BYH and adverse XB/NMB tests have not been started for this model.

The user supplied an approximate reference-to-IMU installation: IMU vertically below VRTK by 30–35 cm, camera facing forward and antenna baseline transverse to the robot. This information belongs only to offline reference-point evaluation. It is not a calibrated extrinsic and does not change the online algorithm or frozen position/heading evaluator. The velocity evaluator will report the 32.5 cm center and both endpoints, retaining the unbounded approximate horizontal/alignment assumptions.
