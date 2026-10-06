# HX-07 EXT01–EXT03 接收机钟差只读核查

本文件核查当前登记源码的数据流，不执行这些实现，不评价文献方法本身是否适用。源码版本由 HX07_INPUT_SHA256.json 固定；外部 RTKLIB 为 180043ee24b6d2b168f98b64be15f69d50046b1a。

## 结论矩阵

| 实现 | (a) 双差卫星位置时刻 | (b) NAV-CLOCK / SPP 钟差 | (c) 两机物理时刻 | (d) SD/DD 中钟差项 |
|---|---|---|---|---|
| EXT01 C-LAMBDA | 接收机一的 week/TOW + 两机均值伪距，RTKLIB 扣传播时间及卫星钟差；不是直接在标签时刻取卫星位置；两机共用此状态 | GPS L1 SPP 估计 receiver_clock_bias_m，但调用者仅传位置给 DD；未用 NAV-CLOCK | exact week/TOW 配对，DD 按共同几何时刻处理；未分别以各自接收机钟差修正接收时刻 | SD 为两机观测相减、DD 再减 pivot；无显式接收机钟差或钟差引起的卫星运动项 |
| EXT02 C-WLS | 与 EXT01 同一 build_gps_l1_double_difference_model | 同一 SPP 估计钟差，但仅 spp.position_ecef_m 进入 DD；未用 NAV-CLOCK | 同一 exact 标签配对与共同卫星状态 | 同一 SD/DD；C-WLS 接收已构建的 code/phase/design |
| EXT03 Yang 2024 | receiver1 week/TOW + 两机第一频率均值伪距，按共同状态构造各系统双频块 | 两机分别调用 RTKLIB pntpos，dtr 被返回；build_epoch_blocks 仅接收 spp1/spp2 位置，未接收钟差；未用 NAV-CLOCK | 两机标签配对后每颗卫星仅一个 state_by_sv；未分别计算两机钟差修正时刻的卫星位置 | SD 扣两机各自对流层，DD 在系统内减 pivot；状态列只有基线和模糊度，无接收机钟差运动补偿列 |

“无显式接收机钟差项”不等于 SPP 不估计钟差，也不等于没有传播时间/卫星钟差校正。理想同物理时刻、同频同系统 DD 中的共同接收机钟差可相消；这里指出的是实际独立接收机标签配对后，几何构造未显式建模两机物理接收时刻差。RAWX clock-reset 标志用于弧段/周跳重置，不是连续 NAV-CLOCK clkB 修正。

## 共同后端证据

### 标签配对

(c) pair_epochs 只允许零容差，键为 gps_week/gps_tow_seconds；该判据没有两机钟差输入。

来源 `<W>/src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py`，L915–L929：

```text
915: def pair_epochs(left: Sequence[RawxEpoch], right: Sequence[RawxEpoch],
916:                 tolerance_seconds: float = 0.0) -> tuple[list[tuple[RawxEpoch, RawxEpoch]], list[dict]]:
917:     if tolerance_seconds != 0.0:
918:         raise RawBackendError("Phase 1 pairing tolerance is frozen at 0.0")
919:     def key(epoch: RawxEpoch) -> tuple[int, float]:
920:         return epoch.gps_week, epoch.gps_tow_seconds
921:
922:     left_counts = Counter(key(epoch) for epoch in left)
923:     right_groups: dict[tuple[int, float], list[tuple[int, RawxEpoch]]] = defaultdict(list)
924:     for index, epoch in enumerate(right):
925:         right_groups[key(epoch)].append((index, epoch))
926:
927:     used: set[int] = set()
928:     pairs: list[tuple[RawxEpoch, RawxEpoch]] = []
929:     failures: list[dict] = []
```

### SPP 钟差确实存在

(b) EXT01/02 的 SPP 预测含 clock_m，联合求解位置与钟差，返回 SppSolution。

来源 `<W>/src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py`，L1490–L1513：

```text
1490:             delta = corrected - position
1491:             geometric = float(np.linalg.norm(delta))
1492:             if not math.isfinite(geometric) or geometric <= 0:
1493:                 continue
1494:             los = delta / geometric
1495:             predicted = geometric + clock_m - _SPEED_OF_LIGHT_MPS * state.clock_bias_s
1496:             rows.append([-los[0], -los[1], -los[2], 1.0])
1497:             innovations.append(measurement.pr_mes_m - predicted)
1498:         design = np.asarray(rows, dtype=float)
1499:         residual = np.asarray(innovations, dtype=float)
1500:         if design.shape[0] < 4 or np.linalg.matrix_rank(design) < 4:
1501:             raise RawBackendError("GPS L1 SPP geometry is rank deficient")
1502:         correction, *_ = np.linalg.lstsq(design, residual, rcond=None)
1503:         position += correction[:3]
1504:         clock_m += correction[3]
1505:         if float(np.linalg.norm(correction[:3])) < 1e-4 and abs(correction[3]) < 1e-4:
1506:             break
1507:     else:
1508:         raise RawBackendError("GPS L1 SPP failed to converge")
1509:     postfit = residual - design @ correction
1510:     return SppSolution(position, float(clock_m), float(np.sqrt(np.mean(postfit ** 2))),
1511:                        design.shape[0], iteration)
1512:
1513:
```

### 共同卫星状态

(a)(c) EXT01/02 使用两机均值伪距与 receiver1 标签，生成一个卫星状态。

来源 `<W>/src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py`，L1643–L1658：

```text
1643:     for identity in accounting.common_integer_compatible_identities:
1644:         mean_range = 0.5 * (first[identity].pr_mes_m + second[identity].pr_mes_m)
1645:         if not math.isfinite(mean_range) or not 1.0e6 < mean_range < 1.0e8:
1646:             continue
1647:         try:
1648:             state = provider.state(
1649:                 identity, receiver1.gps_week, receiver1.gps_tow_seconds, mean_range
1650:             )
1651:         except RawBackendError:
1652:             continue
1653:         if state.health != 0:
1654:             continue
1655:         try:
1656:             corrected = earth_rotation_correct_satellite(
1657:                 state.position_ecef_m, mean_range / _SPEED_OF_LIGHT_MPS
1658:             )
```

### SD/DD 的实际构造

(d) EXT01/02 code/phase SD 与 DD、基线设计和模糊度设计在此直接构造，没有接收机时刻差项。

来源 `<W>/src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py`，L1695–L1717：

```text
1695:         )
1696:                   * wavelength_m(identity)
1697:         for identity in geometry
1698:     }
1699:     code_dd = np.asarray([code_sd[item] - code_sd[pivot] for item in satellites])
1700:     phase_dd = np.asarray([phase_sd[item] - phase_sd[pivot] for item in satellites])
1701:     observation = np.concatenate((code_dd, phase_dd))
1702:     baseline_rows = np.asarray([-(geometry[item] - geometry[pivot]) for item in satellites])
1703:     baseline_design = np.vstack((baseline_rows, baseline_rows))
1704:     ambiguity_design = np.zeros((2 * dimension, dimension), dtype=float)
1705:     ambiguity_design[dimension:, :] = np.diag([wavelength_m(item) for item in satellites])
1706:
1707:     def variances(identity: SignalIdentity) -> tuple[float, float]:
1708:         pr1, cp1, _ = rawx_standard_deviations(first[identity])
1709:         pr2, cp2, _ = rawx_standard_deviations(second[identity])
1710:         wavelength = wavelength_m(identity)
1711:         return pr1 * pr1 + pr2 * pr2, (cp1 * wavelength) ** 2 + (cp2 * wavelength) ** 2
1712:
1713:     pivot_code_variance, pivot_phase_variance = variances(pivot)
1714:     code_variances, phase_variances = zip(*(variances(item) for item in satellites))
1715:     code_covariance = correlated_dd_covariance(code_variances, pivot_code_variance)
1716:     phase_covariance = correlated_dd_covariance(phase_variances, pivot_phase_variance)
1717:     covariance = np.block([
```

### 传播时间与卫星钟差

(a) provider.state 的 C bridge 将标签时刻和伪距送给 RTKLIB satposs；不是忽略信号传播时间。Python 路由在 shared_raw_backend.py L744–772。

来源 `<EXTERNAL>/rtklib_bridge/legsa_rtklib_bridge.c`，L166–L182：

```text
166: int legsa_satpos_transmit_broadcast(void *handle, int receive_gps_week,
167:                                     double receive_tow, int sat,
168:                                     double pseudorange_m, double *rs6,
169:                                     double *dts2, double *variance, int *health)
170: {
171:     legsa_nav_context_t *ctx=(legsa_nav_context_t *)handle;
172:     obsd_t obs;
173:
174:     if (!ctx||sat<=0||!isfinite(pseudorange_m)||pseudorange_m<=0.0||
175:         !rs6||!dts2||!variance||!health) return 0;
176:     memset(&obs,0,sizeof(obs));
177:     obs.time=gpst2time(receive_gps_week,receive_tow);
178:     obs.sat=(uint8_t)sat;
179:     obs.rcv=1;
180:     obs.P[0]=pseudorange_m;
181:     satposs(obs.time,&obs,1,&ctx->nav,EPHOPT_BRDC,rs6,dts2,variance,health);
182:     return rs6[0]!=0.0||rs6[1]!=0.0||rs6[2]!=0.0;
```

### RTKLIB satposs

(a) 官方 satposs 先减 pr/c，再减广播卫星钟差。这里的 dt 是卫星钟差，不是 NAV-CLOCK 的接收机 clkB。

来源 `<RTKLIB>/src/ephemeris.c`，L774–L796：

```text
774:         /* search any pseudorange */
775:         for (j=0,pr=0.0;j<NFREQ;j++) if ((pr=obs[i].P[j])!=0.0) break;
776:
777:         if (j>=NFREQ) {
778:             trace(3,"no pseudorange %s sat=%2d\n",time_str(obs[i].time,3),obs[i].sat);
779:             continue;
780:         }
781:         /* transmission time by satellite clock */
782:         time[i]=timeadd(obs[i].time,-pr/CLIGHT);
783:
784:         /* satellite clock bias by broadcast ephemeris */
785:         if (!ephclk(time[i],teph,obs[i].sat,nav,&dt)) {
786:             trace(3,"no broadcast clock %s sat=%2d\n",time_str(time[i],3),obs[i].sat);
787:             continue;
788:         }
789:         time[i]=timeadd(time[i],-dt);
790:
791:         /* satellite position and clock at transmission time */
792:         if (!satpos(time[i],teph,obs[i].sat,ephopt,nav,rs+i*6,dts+i*2,var+i,
793:                     svh+i)) {
794:             trace(3,"no ephemeris %s sat=%2d\n",time_str(time[i],3),obs[i].sat);
795:             continue;
796:         }
```

## 各实现调用证据

### EXT01

(a)–(d) C-LAMBDA 的实际调用只把 SPP 位置交给共同 DD 模型；钟差估计没有传入该函数。

来源 `<W>/src/legsa_gins/paper_rebuild/horizontal_literature/phase1_runner.py`，L521–L528：

```text
521:         try:
522:             spp = gps_l1_code_spp(receiver1, provider, previous_position)
523:             previous_position = spp.position_ecef_m
524:             model = build_gps_l1_double_difference_model(
525:                 receiver1, receiver2, provider, previous_position,
526:                 previous_pivot=previous_pivot,
527:             )
528:             pivot_switched = previous_pivot is not None and model.pivot != previous_pivot
```

### EXT02

(a)–(d) C-WLS 复用相同 DD 模型，输入为观测、设计矩阵、协方差及基线长。

来源 `<W>/src/legsa_gins/paper_rebuild/horizontal_literature/phase2_runner.py`，L1934–L1960：

```text
1934:     model = None
1935:     try:
1936:         spp = gps_l1_code_spp(left, provider)
1937:         model = build_gps_l1_double_difference_model(
1938:             left, right, provider, spp.position_ecef_m,
1939:             minimum_elevation_rad=ELEVATION_MASK_RAD,
1940:             previous_pivot=None,
1941:         )
1942:         count = len(model.satellites)
1943:         if count < 2:
1944:             raise DoubleDifferenceStageError(
1945:                 "INSUFFICIENT_DD_DIMENSION", "C-WLS needs at least two DD rows",
1946:                 model.accounting,
1947:             )
1948:         gps_l1_wavelength = wavelength_m(model.satellites[0])
1949:         cwls_model = adapt_metric_double_differences(
1950:             code_m=model.observation_m[:count],
1951:             phase_m=model.observation_m[count:],
1952:             design_m_per_m=model.baseline_design[:count],
1953:             covariance_code_phase_m2=model.covariance_m2,
1954:             wavelength_m=gps_l1_wavelength,
1955:             baseline_length_m=BASELINE_LENGTH_M,
1956:         )
1957:         solution = solve_single_baseline_cwls(cwls_model)
1958:         search_complete = _candidate_search_complete(solution)
1959:         if not search_complete:
1960:             raise Phase2RunnerError(
```

### EXT03 SPP 到 DD

(b) 两机 pntpos 独立运行，但只提取 position_ecef_m，再交给 build_epoch_blocks。

来源 `<W>/src/legsa_gins/paper_rebuild/horizontal_literature/phase3_runner.py`，L739–L753：

```text
739:         spp_audit: dict[str, Any] = {}
740:         try:
741:             result1 = _pntpos_receiver(provider, receiver1, variant.system_mode, spp_previous[0], "GNSS1")
742:             spp_audit["GNSS1"] = _jsonable(result1)
743:             if not result1.accepted or result1.position_ecef_m is None:
744:                 raise SppReceiverError("GNSS1", "PNTPOS_REJECTED", f"solstat={result1.solution_status} valid={result1.valid_satellite_count} obs={result1.constructed_observation_count} message={result1.message}")
745:             spp1 = np.asarray(result1.position_ecef_m, dtype=float); spp_previous[0] = spp1
746:             result2 = _pntpos_receiver(provider, receiver2, variant.system_mode, spp_previous[1], "GNSS2")
747:             spp_audit["GNSS2"] = _jsonable(result2)
748:             if not result2.accepted or result2.position_ecef_m is None:
749:                 raise SppReceiverError("GNSS2", "PNTPOS_REJECTED", f"solstat={result2.solution_status} valid={result2.valid_satellite_count} obs={result2.constructed_observation_count} message={result2.message}")
750:             spp2 = np.asarray(result2.position_ecef_m, dtype=float); spp_previous[1] = spp2
751:             spp_baseline = _ecef_vector_to_ned(spp2 - spp1, spp1)
752:             blocks = build_epoch_blocks(receiver1, receiver2, provider, variant.system_mode, spp1, spp2)
753:             model = build_dd_observation(blocks)
```

### EXT03 共同状态

(a)(c) 两个 SPP 位置取平均确定几何，各星只计算一次 receiver1 标签和均值伪距对应状态。

来源 `<W>/src/legsa_gins/paper_rebuild/horizontal_literature/phase3_runner.py`，L574–L605：

```text
574: def build_epoch_blocks(receiver1: RawxEpoch, receiver2: RawxEpoch, provider: RtklibBroadcastProvider, system_mode: str, spp1_ecef_m: Sequence[float], spp2_ecef_m: Sequence[float]) -> tuple[DDObservationBlock, ...]:
575:     """Build within-system dual-frequency blocks with one pivot per constellation."""
576:     mean_receiver = 0.5 * (np.asarray(spp1_ecef_m) + np.asarray(spp2_ecef_m))
577:     blocks: list[DDObservationBlock] = []
578:     groups_by_constellation = {"GPS": ("GPS_L1", "GPS_L2"), "BDS": ("BDS_B1", "BDS_B2")}
579:     for constellation in _mode_constellations(system_mode):
580:         groups = groups_by_constellation[constellation]
581:         maps = {(receiver, group): _best_by_sv(epoch, group) for receiver, epoch in ((1, receiver1), (2, receiver2)) for group in groups}
582:         common = set.intersection(*(set(maps[(receiver, group)]) for receiver in (1, 2) for group in groups))
583:         if len(common) < 2:
584:             raise Phase3ObservationError(f"INSUFFICIENT_{constellation}_DUAL_FREQUENCY_COMMON_SATELLITES", f"common satellite count={len(common)}")
585:         state_by_sv: dict[int, np.ndarray] = {}
586:         elevation_by_sv: dict[int, float] = {}
587:         for sv in sorted(common):
588:             measurement = maps[(1, groups[0])][sv]
589:             mean_range = 0.5 * (measurement.pr_mes_m + maps[(2, groups[0])][sv].pr_mes_m)
590:             try:
591:                 state = provider.state(measurement.identity, receiver1.gps_week, receiver1.gps_tow_seconds, mean_range)
592:                 satellite = earth_rotation_correct_satellite(state.position_ecef_m, mean_range / 299792458.0)
593:                 _az, elevation = azimuth_elevation(mean_receiver, satellite)
594:             except RawBackendError:
595:                 continue
596:             if state.health == 0 and elevation >= math.radians(15.0):
597:                 state_by_sv[sv] = satellite; elevation_by_sv[sv] = elevation
598:         if len(state_by_sv) < 2:
599:             raise Phase3ObservationError(f"INSUFFICIENT_{constellation}_DUAL_FREQUENCY_SATELLITE_STATES", f"usable state count={len(state_by_sv)}")
600:         pivot_sv = min(state_by_sv, key=lambda sv: (-elevation_by_sv[sv], -min(maps[(receiver, group)][sv].locktime_ms for receiver in (1,2) for group in groups), sv))
601:         satellites = tuple(sv for sv in sorted(state_by_sv) if sv != pivot_sv)
602:         for group in groups:
603:             first, second = maps[(1, group)], maps[(2, group)]
604:             los = {rinex_satellite_id(first[sv].identity): _ecef_vector_to_ned((state_by_sv[sv] - mean_receiver) / np.linalg.norm(state_by_sv[sv] - mean_receiver), mean_receiver) for sv in state_by_sv}
605:             def corrected_sd(sv: int, phase: bool) -> float:
```

### EXT03 SD/DD

(d) corrected_sd 仅作相位单位/半周归一化及对流层修正，没有连续钟差/两接收时刻卫星运动项。

来源 `<W>/src/legsa_gins/paper_rebuild/horizontal_literature/phase3_runner.py`，L605–L620：

```text
605:             def corrected_sd(sv: int, phase: bool) -> float:
606:                 m1, m2 = first[sv], second[sv]
607:                 sat = state_by_sv[sv]
608:                 try:
609:                     trop1, trop2 = _saastamoinen_m(spp1_ecef_m, sat), _saastamoinen_m(spp2_ecef_m, sat)
610:                 except RawBackendError as exc:
611:                     raise Phase3ObservationError("DD_TROPOSPHERE_MODEL_FAILURE", str(exc)) from exc
612:                 value1 = integer_compatible_carrier_cycles(m1) * wavelength_m(m1.identity) if phase else m1.pr_mes_m
613:                 value2 = integer_compatible_carrier_cycles(m2) * wavelength_m(m2.identity) if phase else m2.pr_mes_m
614:                 return (value2 - trop2) - (value1 - trop1)
615:             code_pivot, phase_pivot = corrected_sd(pivot_sv, False), corrected_sd(pivot_sv, True)
616:             code = np.asarray([corrected_sd(sv, False) - code_pivot for sv in satellites])
617:             phase_values = np.asarray([corrected_sd(sv, True) - phase_pivot for sv in satellites])
618:             def variances(sv: int) -> tuple[float, float]:
619:                 # Pinned RTKLIB 180043ee varerr defaults at bl=0.350 m and
620:                 # dt=0: fact=1 for GPS/BDS, err[1]=err[2]=0.003 m,
```

### EXT03 状态列

(d) DDObservation 的列为三维基线与逐星模糊度，无两机钟差参数。

来源 `<W>/src/legsa_gins/paper_rebuild/horizontal_literature/ext03_yang2024.py`，L242–L264：

```text
242:     row_count = sum(2 * len(block.satellites) for block in blocks)
243:     design = np.zeros((row_count, 3 + len(identities)), dtype=np.float64)
244:     observation = np.empty(row_count, dtype=np.float64)
245:     covariance = np.zeros((row_count, row_count), dtype=np.float64)
246:     slices: list[tuple[str, str, slice]] = []
247:     initial_ambiguities: dict[AmbiguityIdentity, float] = {}
248:     cursor = 0
249:     for block in blocks:
250:         count = len(block.satellites)
251:         block_slice = slice(cursor, cursor + 2 * count)
252:         code = _finite_vector(block.code_dd_m, count, name="code DD")
253:         phase = _finite_vector(block.phase_dd_m, count, name="phase DD")
254:         observation[block_slice] = np.concatenate((code, phase))
255:         pivot_los = np.asarray(block.los_ned[block.pivot], dtype=float)
256:         baseline_rows = np.asarray(
257:             [-(np.asarray(block.los_ned[satellite], dtype=float) - pivot_los)
258:              for satellite in block.satellites],
259:             dtype=float,
260:         )
261:         design[cursor:cursor + count, :3] = baseline_rows
262:         design[cursor + count:cursor + 2 * count, :3] = baseline_rows
263:         for offset, satellite in enumerate(block.satellites):
264:             identity = AmbiguityIdentity(
```

### pntpos dtr 返回

(b) 接收机 SPP 钟差 dtr_value 确实经 bridge 返回；上面的调用链没有将它送入 DD。

来源 `<W>/src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py`，L898–L911：

```text
898:         rr_value = np.asarray(tuple(rr), dtype=float)
899:         qr_value = np.asarray(tuple(qr), dtype=float)
900:         dtr_value = np.asarray(tuple(dtr), dtype=float)
901:         if np.any(~np.isfinite(rr_value)) or np.any(~np.isfinite(qr_value)) or np.any(~np.isfinite(dtr_value)):
902:             raise PntPosBridgeError("PNTPOS_BRIDGE_NONFINITE_OUTPUT", -6, message)
903:         covariance = np.array([
904:             [qr_value[0], qr_value[3], qr_value[5]],
905:             [qr_value[3], qr_value[1], qr_value[4]],
906:             [qr_value[5], qr_value[4], qr_value[2]],
907:         ])
908:         return RtklibPntPosResult(
909:             True, status, rr_value[:3], rr_value[3:], covariance, dtr_value,
910:             solution_status.value, valid_satellite_count.value,
911:             constructed_observation_count.value, count, message,
```

## 与已有钟差诊断的关系及边界

与 DG-01R 一阶影响 2.2–2.5 周量级一致（该表述对应 BY2 与 BY2O）。逐序列登记值为 BY2 2.247626 周、BY2H 1.851675 周、BY2O 2.463785 周；BY2H 应单列，不能说三序列全部都在 2.2–2.5 周。来源 `<W>/docs/paper_rebuild/hext/DG01R/DG01R_CLOCK_OFFSET.csv`，scope=all_paired_RAWX，列 max_first_order_DD_cycles。

这是源码缺少相应时刻差几何项与独立诊断量级的并列事实，不是因果占比估计。没有在本任务修正 EXT01–03、重跑这些方法或把先前误差全归于钟差；判断留给作者。
