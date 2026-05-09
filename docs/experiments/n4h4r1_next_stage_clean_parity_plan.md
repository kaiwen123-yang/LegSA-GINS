# N4H4R1 Next Stage Clean Parity Plan

## N4H4R2

Complete the source-backed mathematical port if R1 remains a skeleton:

- full KF-GINS-style mechanization
- F/G/Phi/Qd
- EKFPredict
- GNSS position/velocity/yaw update
- EKFUpdate
- stateFeedback
- IMU compensation timing
- config/noise/covariance units

## N4H4R3

Run clean replay parity with the source-backed port-core backbone. If parity
fails, write a gap report. Do not tune, delete epochs, use trace as solver
input, or perform output-only correction.

## N4H4E

Run visual validation only after numerical clean replay parity has passed.

## N5

Raw Doppler factor work starts only after backbone parity. It is not part of R1.

