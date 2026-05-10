# N4H4E1 STD Unit Consistency

N4H4E1 audits STD units for the source-backed port visual validation.

The expected KF-GINS `writeSTD` common-unit convention is:

- position STD in meters;
- velocity STD in meters per second;
- roll, pitch, and yaw STD in degrees;
- gyro bias STD in degrees per hour;
- accelerometer bias STD in mGal;
- scale STD in ppm.

The source-backed port writer must match this output convention even when the
internal covariance uses SI or radian units. In particular, attitude covariance
is internal `rad^2`, while visual plots and `KF_GINS_STD.txt` comparisons use
degrees.

N4H4E1 does not edit runtime data, delete epochs, tune by trace, or make a
paper performance claim. Corrected 3sigma plots are consistency diagnostics
only.
