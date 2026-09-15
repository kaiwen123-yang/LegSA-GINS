# LC02 full method card

## Identity and source

- Canonical ID: `LC02_YIN2023_RAEKF`; compatibility alias: `EXT06_YIN2023_RAEKF_LC`.
- Authors: Zhihui Yin, Jichao Yang, Yue Ma, Shengli Wang, Dashuai Chai, Haonan Cui.
- Title: *A Robust Adaptive Extended Kalman Filter Based on an Improved Measurement Noise Covariance Matrix for the Monitoring and Isolation of Abnormal Disturbances in GNSS/INS Vehicle Navigation*.
- Journal: *Remote Sensing* 2023, 15, 4125. DOI `10.3390/rs15174125`.
- Official MDPI v2 PDF: 24 pages, 21,097,265 bytes, SHA-256 `198da0283cabddc97446bf9cf9138d8b7ee0b1d1a78f9bdbbe8265c711302f0c`.
- License: Creative Commons Attribution 4.0 (`CC BY 4.0`).
- Source URL: `https://mdpi-res.com/d_attachment/remotesensing/remotesensing-15-04125/article_deploy/remotesensing-15-04125-v2.pdf`.

## Complete-review proof

All 24 pages were text-extracted and rendered. Pages 1–24 were inspected visually in six four-page contact sheets; equation/flow pages 4–10 and experiment/conclusion/source pages 17–24 were also inspected at full-page resolution. Equations (1)–(14), Figures 1–20, Tables 1–10, the two vehicle experiments, satellite-system comparison, disturbance injections, discussion, conclusion, references, author/software attribution, and data-availability statement were checked. The task anticipated Tables 1–9; the published v2 PDF also contains Table 10, which is included here.

Figure 3 was transcribed from the rendered page. Both AKF and RKF are computed, `omega` is selected by the residual statistic (`0.85` below/at `c`, `0.15` above `c`), and state and covariance are fused. The printed flow does not resolve the RKF standardized-residual denominator or how a zero IGGIII weight is inverted.

## Method identity

The paper uses a conventional 21-state NED error-state GNSS/INS EKF. The explicit measurement is a three-dimensional antenna-position residual with a lever-arm attitude Jacobian. The improved measurement covariance uses `PDOP^2 Q r^2`. Its four branches—EKF, AKF, RKF, and paper-native `RAKF` (canonical `RAEKF`)—are one paper family, not four independent literature methods.

## Scientific closure

The base state order, sign convention, full continuous `F/G`, process-noise structure, mechanization, feedback, and position measurement are closed from paper equations plus the paper-acknowledged, paper-contemporaneous KF-GINS source. Exact Yin initialization/IMU numeric values are not printed and remain `CURRENTLY_UNKNOWN` for a future BY2 physical instantiation.

The input contract is source-closed, but the formal RAEKF reproduction is not: Yin does not define how RKF observation symbol `L_k` relates to the earlier measurement `Z_k`, does not define the standardized innovation `V_tilde_i`, and `w_i=0` makes the printed equivalent precision singular before an inverse. Setting `L_k=Z_k` and row omission/infinite variance are defensible `PAPER_DERIVED_POLICY_BASELINE` choices, not a faithful reproduction. These limitations do not block Y0–Y3 audit closure, but they keep formal admission and execution gates false.
