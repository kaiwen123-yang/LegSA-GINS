# Reference requests

These are unresolved author–year citations for the manuscript. The bibliography strings below are copied verbatim from the designated inventory; spelling, years, publication details, and embedded provenance have not been silently repaired. Only bibliographic fields are transcribed. Author confirmation and final journal formatting remain necessary.

## R01

Requested topic: Teunissen GNSS compass integer least squares.

Locations: MANUSCRIPT_GPSS_v0.md:25 — 2.1 Dual-antenna heading.

Existing inventory entry, `docs/paper_rebuild/hext/HX_INVENTORY.md:174` (verbatim):

```text
| reference | P. J. G. Teunissen (2006) 'The LAMBDA method for the GNSS compass', Artificial Satellites 41(3):89-103; P. J. G. Teunissen (2010) 'Integer least-squares theory for the GNSS compass', Journal of Geodesy 84:433-447; P. J. G. Teunissen, G. Giorgi, P. J. Buist (2011) 'Testing of a new single-frequency GNSS carrier phase attitude determination method', GPS Solutions 15:15-28（configs/paper_rebuild/horizontal_literature/EXTERNAL_METHOD_CONTRACTS_V1.yaml:32-58） |
```

## R02

Requested topic: Liu constrained wrapped least squares.

Locations: MANUSCRIPT_GPSS_v0.md:25 — 2.1 Dual-antenna heading.

Existing inventory entry, `docs/paper_rebuild/hext/HX_INVENTORY.md:193` (verbatim):

```text
| reference | Xing Liu, Tarig Ballal, Hui Chen, Tareq Y. Al-Naffouri (2022) 'Constrained Wrapped Least Squares: A Tool for High-Accuracy GNSS Attitude Determination', IEEE TIM 71, 8005315, doi 10.1109/TIM.2022.3193412（configs/paper_rebuild/horizontal_literature/PHASE2_EXT02_CWLS_CONTRACT_V1.yaml:9-20） |
```

## R03

Requested topic: Yang baseline-length-constrained ambiguity resolution.

Locations: MANUSCRIPT_GPSS_v0.md:25 — 2.1 Dual-antenna heading.

Existing inventory entry, `docs/paper_rebuild/hext/HX_INVENTORY.md:212` (verbatim):

```text
| reference | Hongli Yang, Yuanming Shu, Rongxin Fang, Lulu Qiao, Dong Ding, Guangxue Li (2024) 'GPS/BDS Dual-Antenna Attitude Determination With Baseline-Length Constrained Ambiguity Resolution: Method and Performance Evaluation', IEEE TIM 73, 1003414, doi 10.1109/TIM.2024.3374423（configs/paper_rebuild/horizontal_literature/PHASE3_EXT03_YANG2024_CONTRACT_V1.yaml:10-27） |
```

## R04

Requested topic: Wu constrained ambiguity and misalignment compensation.

Locations: MANUSCRIPT_GPSS_v0.md:25 — 2.1 Dual-antenna heading.

Existing inventory entry, `docs/paper_rebuild/hext/HX_INVENTORY.md:231` (verbatim):

```text
| reference | Jiaji Wu, Jinguang Jiang, Yuying Li, Tianci Tang, Jianghua Liu, Jingnan Liu (2025) 'Robust Dual-Antenna GNSS/INS Attitude Determination via Constrained Ambiguity Resolution and Misalignment Compensation', IEEE TIM 74, 9539914, doi 10.1109/TIM.2025.3626898（configs/paper_rebuild/horizontal_literature/PHASE4_EXT04_WU2025_CONTRACT_V1.yaml:13-29）；仅实现 Section II-A 航向模块 |
```

## R05

Requested topic: two-receiver invariant GNSS/INS filter and its experimental noise parameters.

Locations: MANUSCRIPT_GPSS_v0.md:31 — 2.2 GNSS/INS on ground and legged robots.

Existing inventory entry, `docs/paper_rebuild/hext/HX_INVENTORY.md:288` (verbatim):

```text
| reference | Natalia Pavlasek, Alex Walsh, James Richard Forbes (2021) 'Invariant Extended Kalman Filtering Using Two Position Receivers for Extended Pose Estimation', ICRA 2021, pp. 5582-5588, doi 10.1109/ICRA48506.2021.9561150, arXiv 2104.14711（configs/paper_rebuild/horizontal_literature/PHASE5_EXT05_PAVLASEK_CONTRACT_V1.yaml:5-15）；别名 EXT05A / EXT05A_PAVLASEK_TWO_RECEIVER_IEKF / LC01_EXT05A；活动登记 id LC01_PAVLASEK2021_TWO_RECEIVER_IEKF（docs/paper_rebuild/horizontal_literature/lc02_yin2023/stage_payload/00_ACTIVE_METHOD_REGISTRY/ACTIVE_SOLUTION_LEVEL_LC_REGISTRY.csv:2；configs/.../lc02_final_candidate_triage/stage_payload/00_REGISTRY/LC02_FINAL_CANDIDATE_REGISTRY.csv:2，status COMPLETED_ACTIVE_METHOD）；HORIZONTAL18_V2 身份 M01_EXT05_PAVLASEK_IEKF |
```

## R06

Requested topic: KF-GINS mechanization and error-state model.

Locations: MANUSCRIPT_GPSS_v0.md:29 — 2.2 GNSS/INS on ground and legged robots.

Primary bibliographic record independently identified on 2026-10-04: Niu X, Wang L, Chen Q, Tang H, Zhang Q, Zhang T (2025) KF-GINS: an open-sourced software for GNSS/INS integrated navigation. GPS Solutions 29:202. https://doi.org/10.1007/s10291-025-01967-w. The publisher and official i2Nav-WHU/KF-GINS repository agree on the authors/title/DOI and loosely coupled error-state implementation role. Publisher metadata also flags a correction, https://doi.org/10.1007/s10291-025-01993-8 (published 2025-12-05, volume 30:33, 2026); its full correction content was not accessible. This closes the absent R06 identity, while final author–year insertion and correction-content review remain necessary. This task read publisher metadata/abstract and official repository documentation, not the complete subscription article.

## R07

Requested topic: Chen Chang Chen GINav.

Locations: MANUSCRIPT_GPSS_v0.md:29 — 2.2 GNSS/INS on ground and legged robots.

Existing inventory entry, `docs/paper_rebuild/hext/HX_INVENTORY.md:402` (verbatim):

```text
| reference | Chen, Chang, Chen (2021) 'GINav: a MATLAB-based software for the data processing and analysis of a GNSS/INS integrated navigation system', GPS Solutions 25, 108, doi 10.1007/s10291-021-01144-9；官方软件 github.com/kaichen686/GINav @ bc6b3ab6c40db996a4fd8e8ca5b748fe21a23666（BSD-2-Clause，configs/paper_rebuild/horizontal_literature/ginav2021/GINAV2021_RUNTIME_CONTRACT.yaml:9-15）；别名 LC02C_GINAV2021_OFFICIAL_SPP_INS_LC、GINAV |
```

## R08

Requested topic: Hartley contact-aided invariant EKF.

Locations: MANUSCRIPT_GPSS_v0.md:35 — 2.3 Proprioceptive legged state estimation.

Existing inventory entry, `docs/paper_rebuild/hext/HX_INVENTORY.md:592` (verbatim):

```text
| reference | Ross Hartley, Maani Ghaffari, Ryan M. Eustice, Jessy W. Grizzle (2020) 'Contact-Aided Invariant Extended Kalman Filtering for Robot State Estimation', IJRR 39(4), doi 10.1177/0278364919894385, arXiv 1904.09251；Ross Hartley, Maani Ghaffari Jadidi, Jessy W. Grizzle, Ryan M. Eustice (2018) 'Contact-Aided Invariant Extended Kalman Filtering for Legged Robot State Estimation', RSS XIV, doi 10.15607/RSS.2018.XIV.050, arXiv 1805.10410（docs/paper_rebuild/horizontal_literature/hartley/stage_payload/00_SOURCE_REGISTRY/PAPER_SOURCE_REGISTRY.csv:2-3）；别名 LSE01 |
```

## R09

Requested topic: RTKLIB moving-base implementation and solution states.

Locations: Not cited in the compressed main draft; retained as a historical bibliography request for the software comparison in the supplement.

Existing inventory entry, `docs/paper_rebuild/hext/HX_INVENTORY.md:250` (verbatim):

```text
| reference | RTKLIB 开源软件 2.4.3_b34，commit 180043ee24b6d2b168f98b64be15f69d50046b1a，BSD-2-Clause（$CLEAN4/00_CONTRACTS/EXTERNAL_METHOD_CONTRACTS_V1.yaml:64-72）；记录中无论文 |
```

## R10

Requested topic: absolute heading and observability in low-cost ground-robot GNSS/INS.

Locations: MANUSCRIPT_GPSS_v0.md:13 — 1 Introduction.

Primary identity checked 2026-10-04: Teunissen PJG (2010) Integer least-squares theory for the GNSS compass. Journal of Geodesy 84:433–447. https://doi.org/10.1007/s00190-010-0380-8. Publisher abstract supports unaided single-epoch attitude; it does not justify every low-cost INS observability claim.

## R11

Requested topic: innovation-based fault detection and exclusion.

Locations: MANUSCRIPT_GPSS_v0.md:39 — 2.4 Quality-aware weighting and residual checks.

Primary identities checked 2026-10-04: Wang S, Zhan X, Zhai Y, Liu B (2020) Fault Detection and Exclusion for Tightly Coupled GNSS/INS System Considering Fault in State Prediction. Sensors 20:590. https://doi.org/10.3390/s20030590; open full text https://pmc.ncbi.nlm.nih.gov/articles/PMC7036913/. Zaminpardaz S, Teunissen PJG (2019) DIA-datasnooping and identifiability. Journal of Geodesy 93:85–101. https://doi.org/10.1007/s00190-018-1141-3. Supports prediction/measurement mixture and detect-versus-identify boundary. Publisher abstracts and selected fault-model sections were checked, not whole-paper reproduction.

## R12

Requested topic: Yin adaptive covariance monitoring and isolation.

Locations: MANUSCRIPT_GPSS_v0.md:39 — 2.4 Quality-aware weighting and residual checks.

Existing inventory entry, `docs/paper_rebuild/hext/HX_INVENTORY.md:421` (verbatim):

```text
| reference | Yin, Yang, Ma, Wang, Chai, Cui (2023) 'A Robust Adaptive Extended Kalman Filter Based on an Improved Measurement Noise Covariance Matrix for the Monitoring and Isolation of Abnormal Disturbances in GNSS/INS Vehicle Navigation', Remote Sensing 15:4125, doi 10.3390/rs15174125（docs/paper_rebuild/horizontal_literature/lc02_yin2023/stage_payload/00_ACTIVE_METHOD_REGISTRY/ACTIVE_SOLUTION_LEVEL_LC_REGISTRY.csv:3）；旧别名 EXT06_YIN2023_RAEKF_LC |
```

The RTKLIB entry identifies software rather than a paper. Retain a software citation or request the authors’ preferred primary publication. For the Hartley entry, distinguish the journal treatment and earlier conference paper. The Wu comparison concerns the recorded heading module and does not claim implementation of the complete published architecture.


## R13

Requested topic: Fixposition Vision-RTK 2 architecture, conditional specifications, and recorded fusion-status interpretation.

Locations: MANUSCRIPT_GPSS_v0.md:59 — 3.2 Observation streams and reference.

Primary supplied source: Fixposition AG (2024), Quick Start Guide, Vision-RTK 2, version 2024.05. Supplied PDF: C:/Users/ykw/Desktop/快速开启保姆级教程.pdf; SHA256 8b337d994a6523c6258727f08755a12e9b1db1b3054575d537afdeec74fba415. The tutorial is a product guide, not the experimental device configuration.

Current primary documentation (accessed 2026-10-04): https://docs.fixposition.com/fd/fp_a-odomstatus and https://docs.fixposition.com/fd/generating-a-log-of-the-vision-rtk-2. Camera use is supported by each experiment's recorded status, not inferred from the guide. Publisher text should be cited in final author–year/web-source form; do not present manufacturer specifications as calibrated reference confidence bounds.

## Corrected FGO references and experiment binding

Corrected selected paper branches and the nine accepted runs are bound in manuscript Section 6.6 and Supplement S22, with exact source identity in evidence/RESULT_IDENTITY_MAP.json and STEP1_FGO_FINAL_IMPLEMENTATION_AND_REPRODUCTION.md. Author-program/full-original-experiment equivalence remains unestablished. Exact paper citation strings must be finalized from the primary contracts; no new author, date or title is invented here.
