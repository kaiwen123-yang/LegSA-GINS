# Paper claim boundary

Yin et al. report land-vehicle experiments in which their paper-native `RAKF` branch improves robustness/stability under abnormal disturbances relative to EKF, AKF, and RKF. Those figures and RMS tables establish only the paper's reported experiment claims. None is a BY2 result, current provider result, or parameter-selection target.

The paper uses a single GNSS antenna and a 21-state conventional error-state filter. It does not provide the two-receiver rigid relative-position information used by LC01. Its output includes navigation position, velocity, and attitude, but output evaluation does not prove GNSS velocity is an online measurement; the explicit measurement equations are position-only.

The paper's data are available from the corresponding author on request because of privacy or ethical restrictions. Software is attributed to Z.Y.; no source or supplement is supplied. The acknowledged KF-GINS repository is a cited base-model source, not official Yin branch code.

No paper performance number is imported. No claim is made that BY2 will reproduce the paper's accuracy, disturbance distribution, initialization, sensor grade, or environment. Y0–Y3 audit closure passes, while formal RAEKF admission remains false because `L_k` versus `Z_k` and the robust covariance input are not uniquely executable.
