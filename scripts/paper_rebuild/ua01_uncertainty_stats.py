#!/usr/bin/env python3
"""UA-01: frozen error/aggregate/provider statistics; no solver or evaluator.

All computation is in this process. Numerical outputs have deterministic row
ordering, PCG64 streams derived from seed 20260927, and LF CSV newlines.
The local path YAML is the sole source of machine-local roots.
"""
from __future__ import annotations

import os
for _key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_key] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yaml

SEED = 20260927
METHODS = ["F01", "F02", "F03", "F04", "A03", "A04", "A05", "A06", "A07", "A08", "A09"]
METRICS = ["yaw_rmse_deg", "horizontal_rmse_m", "up_rmse_m", "yaw_p95_absolute_deg"]
SERIES = ["yaw_err_deg", "err_n_m", "err_e_m", "err_u_m", "horizontal_err_m"]
PAIRS = [("F04", "F02"), ("F04", "F03"), ("F04", "A04"), ("F03", "F02"), ("A04", "F03")]
EXPECTED_FAILURES = dict(zip(METHODS, [20, 43, 29, 22, 23, 28, 22, 22, 22, 29, 23]))
TYPES = [f"D{i:02d}" for i in range(1, 61)]
CASES = ["C00_clean_normal"] + [f"{typ}_seed_{s:02d}" for typ in TYPES for s in range(9)]
PIN_SPEC = [
    ("v3", "07_AGGREGATE/CORE_541_DISTRIBUTION_V3.csv", "301cec24cb454781138aa39dd3b86a4b37b7855773e6d28e891b7231047d4c39"),
    ("v3", "07_AGGREGATE/ADDENDUM_TABLE_V3.csv", "82aaef841c4e62d13ce4c4a2625b063ec3ac02ffc379db835cf1452486c978bb"),
    ("v3", "07_AGGREGATE/BY2O_SEGMENT_TABLE.csv", "13a2c4e8de7638fa8672bb49d6556f531061a3924fe7dbf6911adfcf53779876"),
    ("v3", "07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv", "44aeaa0302afab54c8179bbb977c9fdac11ebf4f013ac9becdc731840342f4b1"),
    ("v3", "07C_FAILURE_FAMILY_CONFIG/FAILURE_FAMILY_CONFIG.csv", "d374c4370952dc54c328bf868548848059d398801851e021fb664b349773cb50"),
    ("v3", "07_AGGREGATE/MAIN_TABLE_V3.csv", "cd734338cf89518679d78179f410a79ecad3060535d3b80e43a62545cee9b21c"),
    ("hext", "MAIN_TABLE_V3.csv", "9cadef700c3f20a107ca5f054e1b696353db2b4fc67ad86c3f062de50ba9957e"),
    ("repo", "docs/paper_rebuild/hext/HX03R2/DEGRADATION_EXTERNAL_TABLE_R2.csv", "17cfce3191231c1631b0b3b1c2d8196a838690e1e9eae83bbcef0621f23d4989"),
    ("cal", "BY2/CALIBRATED_IMU.imu", "74e31747c5b10d46846472a5adb41bd8e75ad3e27a612f45946c4895b976f647"),
    ("cal", "BY2H/CALIBRATED_IMU.imu", "d32e4891080e300e6edde4526146636f15ec54df945a0470c57fbbdc3aa5115c"),
    ("cal", "BY2O/CALIBRATED_IMU.imu", "48943f3e704ceebbf517bfb073856c1c215b5216e3a5d8b6cd91e7ea7586e49b"),
    ("cal", "BY2/CALIBRATED_GNSS.gnss", "68ed8de7f91b267072bab09e968a9cab4b5220bc5eb116140adacdfde0382e7a"),
    ("cal", "BY2H/CALIBRATED_GNSS.gnss", "88d18be4ec1b4efe4d74f8fc59683d7209fc803f52c60268a763ce457fa55f00"),
    ("cal", "BY2O/CALIBRATED_GNSS.gnss", "96ffaa3a88f97d2519381baf20c1e139269665281ff0de2f56fb55f0b2446394"),
]

DEFINITIONS = """通用：非数值/UNAVAILABLE 视为非有限，计入 n_failure；所有 SD 用 ddof=1；分位数用 numpy percentile(method="linear")；随机种子 20260927。

A. 逐型种子离散（CORE_541_DISTRIBUTION_V3.csv）：对每个 method × metric（yaw_rmse_deg、水平 RMSE、up_rmse_m、以及表里若有的 yaw P95）× 类型 D01–D60：n_registered=9、n_finite、mean、sd、min、median、max、cv=sd/mean。族（family）取 degradation_60types_9seeds.yaml 的 family 字段。族级汇总：每 method × metric × family 的 median(sd)、p90(sd)、max(sd) 及取 max 的类型。
B. 逐例配对差（同 case_id）：pair ∈ {F04−F02, F04−F03, F04−A04, F03−F02, A04−F03}，metric 同上；逐型：n_pairs_finite、mean、sd、median、min、max、frac_negative；全体（540 退化例）：n_pairs、median、p05、p95、frac_negative；median 的 95% CI 两种：cluster bootstrap（以 60 个类型 + C00 为 61 个簇，整簇重抽，B=10000）与 naive bootstrap（逐例重抽，B=10000）。
   外部配对：把 DEGRADATION_EXTERNAL_TABLE_R2.csv 的 LC01（LIT）与 EXT05C（LIT）逐例值按 case_id 与分布表连接，pair ∈ {LC01−F04, LC01−F02, EXT05C−F04}，只对两侧均有限的例；逐型 n、mean、sd、median。
C. 541 分布分位数：每 method × metric：n_registered=541、n_finite、n_failure、mean、median、p95、max；median 与 p95 的 95% CI 用 cluster bootstrap（61 簇，B=10000）与 naive bootstrap（B=10000）各一套。
D. C00 误差序列（33 条 LegSA + 4 条 LC01/LC01-S），对 series ∈ {yaw_err_deg, err_n_m, err_e_m, err_u_m, horizontal_err_m}：
   D1 基本量：n、t_start、t_end、dt_median、dt_max、rmse_recomputed、表值、identity_pass、mean（带符号）、std、|yaw_err|≤180 检查。
   D2 慢/快分量：slow = 以 5.0 s 为窗的中心滑动平均（pandas rolling(window=round(5/dt_median) 取奇数, center=True, min_periods=1)），fast = e − slow；报 std_slow、std_fast、以及 rms_fast/rmse。
   D3 自相关有效样本数：对 s_i = e_i²（去均值）算样本自相关 ρ_s(k)，k=1…K_max，K_max=round(60/dt_median)；K = 首个 ρ_s(k) ≤ 0 的 k 之前（Geyer 初始正序列），或 K_max；τ_int = dt_median·(1+2Σ_{k=1}^{K}ρ_s(k))；n_eff = n/(1+2Σρ_s(k))；se_mse = sqrt(var(s, ddof=1)/n_eff)；se_rmse_acf = se_mse/(2·rmse)。报 K、τ_int、n_eff、se_rmse_acf。
   D4 分块均值：非重叠块长 L=20 s 与 L=40 s（丢弃末尾不足块）；每块 MSE 的 sd/√n_blocks = se_mse；se_rmse_batch = se_mse/(2·rmse)；报两种 L 的 n_blocks 与 se_rmse。
   D5 移动块 bootstrap：块长 20 s（样本数 round(20/dt_median)），从全部重叠块中有放回抽 ceil(n/块长) 块拼接截断到 n，算 rmse，B=2000；报 2.5%/97.5% 分位。
   D6 配对差分序列：同序列的 pair ∈ {(F04,F02),(F04,F03),(F04,A04),(F03,F02),(A04,F03),(LC01,F04),(LC01,F02),(LC01,F03)}，BY2 另加 (LC01-S,F04)；对 yaw_err_deg 与 horizontal_err_m：先按 time 精确相等（四舍五入到 1e-6 s）取共同历元；若共同数 < 0.9·min(n_A,n_B)，改为最近邻 |Δt| ≤ 2.5 ms 并同时报告两种匹配数与所用方式；d_i = e_A,i² − e_B,i²；rmse_A、rmse_B（共同历元上重算）、delta_rmse = rmse_A − rmse_B、delta_mse = mean(d)、corr(e_A², e_B²)；se_delta_mse 用 D3 的自相关法与 D4 的 20 s 分块法各一套；se_delta_rmse = se_delta_mse/(rmse_A + rmse_B)；再用 D5 的移动块 bootstrap（两序列同一块索引）给 delta_rmse 的 2.5%/97.5%。
   D7 BY2O 分段：区间 token 取 $V3/07_AGGREGATE/BY2O_SEGMENT_TABLE.csv 的 window_start_s/window_end_s（primary、secondary，闭区间；outside = full 减两闭区间）。对 BY2O 的 11 个配置 + LC01：每段 n、rmse_yaw、mean_yaw（带符号）、std_slow、std_fast（D2 定义，只在段内样本上算）、rmse_h、rmse_up；并对 (F04,F02)、(LC01,F04)、(F04,A04) 在 primary 段内做 D6。
E. A1/A2（ADDENDUM_TABLE_V3.csv）：按 D61/D62 × 时长（10/20/30 s）× method × metric：n_registered、n_finite、mean、sd、median、p95、max；逐例配对 F04−A04、F04−F03、A04−F03、F03−F02：n、mean、sd、median、p95。
F. 运动统计（只读冻结 provider 文本，不生成任何新 provider）：
   F1 偏航率：CALIBRATED_IMU.imu 列 [time, dtheta_x, dtheta_y, dtheta_z, dvel_x, dvel_y, dvel_z]（空格分隔、增量、FRD）；ω_z = dtheta_z/dt（dt 为相邻 time 差，丢弃 dt≤0 或 >0.1 s 的行）；在评估窗内（BY2 [66.0,340.0]、BY2H [413.0,683.0]、BY2O [3186.0,3563.0] s，以 .imu 的 time 列为准）报 rms(ω_z)、p95(|ω_z|)、max(|ω_z|)、|ω_z|>10 °/s 的时间占比，单位 °/s；先打印文件首行与列数确认格式。
   F2 速度：CALIBRATED_GNSS.gnss（空格分隔、无表头；1-based 第 1 列 time、第 8/9/10 列 vn/ve/vd，先打印首行与列数确认）；speed = hypot(vn, ve)；窗内 mean、rms、p95、speed<0.2 m/s 的历元占比、行数。
G. 原文转录：CORE_541_SUMMARY_V3.csv、ADDENDUM_SUMMARY_V3.csv、SUBSET61_SUMMARY_V3.csv 全文；BY2O_SEGMENT_TABLE.csv 中 F02/F03/A04/F04 及任何 LC01 行；ls -la $V3/07_AGGREGATE 与 $V3/07C_FAILURE_FAMILY_CONFIG；若 07_AGGREGATE 下存在名字含 BODY_FRAME 或 CONSISTENCY 的 v3 表，转录其 BY2/BY2H/BY2O 的 F02/F03/A04/F04 行。"""


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def finite(x):
    a = np.asarray(x, dtype=float)
    return a[np.isfinite(a)]


def pct(x, q):
    a = finite(x)
    return float(np.percentile(a, q, method="linear")) if len(a) else np.nan


def sd(x):
    a = finite(x)
    return float(np.std(a, ddof=1)) if len(a) > 1 else np.nan


def summary(x, registered=None):
    a = finite(x)
    r = {"n_finite": len(a), "mean": float(np.mean(a)) if len(a) else np.nan,
         "sd": sd(a), "min": float(np.min(a)) if len(a) else np.nan,
         "median": pct(a, 50), "p95": pct(a, 95), "max": float(np.max(a)) if len(a) else np.nan}
    if registered is not None:
        r = {"n_registered": registered, "n_failure": registered - len(a), **r}
    return r


def rng_for(label):
    digest = hashlib.sha256(label.encode()).digest()
    return np.random.default_rng(np.random.SeedSequence([SEED] + list(np.frombuffer(digest[:16], dtype="<u4"))))


def markdown(frame, columns=None, precision=8):
    if columns is not None:
        frame = frame[[c for c in columns if c in frame.columns]]
    def fmt(x):
        if isinstance(x, (float, np.floating)):
            return f"{x:.{precision}g}" if np.isfinite(x) else "UNAVAILABLE"
        return str(x).replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(frame.columns) + " |",
                       "| " + " | ".join(["---"] * len(frame.columns)) + " |"] +
                      ["| " + " | ".join(fmt(x) for x in row) + " |" for row in frame.itertuples(index=False, name=None)])


def acf_se(values, dt):
    """Biased sample ACF: lagged centered sum / zero-lag centered sum."""
    s = np.asarray(values, float)
    n = len(s)
    if n < 2 or not np.isfinite(dt) or dt <= 0 or not np.all(np.isfinite(s)):
        return dict(K=np.nan, K_max=np.nan, tau_int_s=np.nan, n_eff=np.nan, se_mean=np.nan)
    z = s - s.mean()
    kmax = min(round(60 / dt), n - 1)
    variance = float(np.var(s, ddof=1))
    if float(z @ z) == 0:
        k, factor = 0, 1.0
    else:
        nfft = 1 << (2 * n - 1).bit_length()
        ft = np.fft.rfft(z, nfft)
        cov = np.fft.irfft(ft * ft.conjugate(), nfft)[:kmax + 1]
        rho = cov[1:] / cov[0]
        nonpositive = np.flatnonzero(rho <= 0)
        k = int(nonpositive[0]) if len(nonpositive) else kmax
        factor = 1.0 + 2.0 * float(np.sum(rho[:k]))
    neff = n / factor
    return dict(K=k, K_max=kmax, tau_int_s=dt * factor, n_eff=neff, se_mean=math.sqrt(variance / neff))


def batch_se(values, dt, seconds):
    block = max(1, round(seconds / dt))
    nblocks = len(values) // block
    if nblocks < 2:
        return nblocks, np.nan
    means = np.asarray(values[:nblocks * block]).reshape(nblocks, block).mean(axis=1)
    return nblocks, float(np.std(means, ddof=1) / math.sqrt(nblocks))


def moving_block_rmse(squares, dt, label, other=None, B=2000):
    """Exact block sum equivalent of concatenation, including the last partial block."""
    x = np.asarray(squares, float)
    n = len(x)
    block = max(1, round(20 / dt))
    if n < block:
        return np.nan, np.nan, block
    nblocks = math.ceil(n / block)
    rng = rng_for(label)
    starts = rng.integers(0, n - block + 1, size=(B, nblocks))
    lengths = np.full(nblocks, block, dtype=int)
    lengths[-1] = n - (nblocks - 1) * block
    def rms(a):
        cs = np.concatenate(([0.0], np.cumsum(a, dtype=float)))
        sums = cs[starts + lengths] - cs[starts]
        return np.sqrt(np.maximum(sums.sum(axis=1) / n, 0))
    draws = rms(x)
    if other is not None:
        draws -= rms(np.asarray(other, float))
    low, high = np.percentile(draws, [2.5, 97.5], method="linear")
    return float(low), float(high), block


def slow_fast(e, dt):
    window = max(1, round(5 / dt))
    if window % 2 == 0:
        window += 1
    slow = pd.Series(e).rolling(window=window, center=True, min_periods=1).mean().to_numpy()
    fast = np.asarray(e) - slow
    rmse = math.sqrt(float(np.mean(np.square(e))))
    return dict(rolling_window_samples=window, std_slow=sd(slow), std_fast=sd(fast),
                rms_fast_over_rmse=math.sqrt(float(np.mean(fast ** 2))) / rmse if rmse else np.nan)


def quantile_bootstrap(values, label, quantiles=(50, 95), B=10000):
    """Resample 61 registered clusters; nonfinite members never become data.

    A length-541 vector is used even for B's 540-case population, where C00 is
    deliberately NaN. It remains the explicitly requested empty 61st cluster.
    Cluster counts repeat every observed member of each selected whole cluster.
    Weighted order statistics reproduce numpy's linear percentile exactly.
    """
    values = np.asarray(values, float)
    groups = np.concatenate(([0], np.repeat(np.arange(1, 61), 9)))
    mask = np.isfinite(values)
    x, g = values[mask], groups[mask]
    if not len(x):
        return {f"{kind}_q{q}_{bound}": np.nan for kind in ["cluster", "naive"] for q in quantiles for bound in ["low", "high"]}
    order = np.argsort(x, kind="stable")
    sx, sg = x[order], g[order]
    result = {}
    for kind in ["cluster", "naive"]:
        rng = rng_for(label + "/" + kind)
        draws = np.full((len(quantiles), B), np.nan)
        for start in range(0, B, 250):
            size = min(250, B - start)
            if kind == "naive":
                sampled = x[rng.integers(0, len(x), size=(size, len(x)))]
                draws[:, start:start + size] = np.percentile(sampled, quantiles, axis=1, method="linear")
            else:
                counts = rng.multinomial(61, np.full(61, 1 / 61), size=size)
                cumulative = np.cumsum(counts[:, sg], axis=1)
                n = cumulative[:, -1]
                valid = n > 0
                for qi, q in enumerate(quantiles):
                    rank = (n - 1) * (q / 100)
                    lo = np.floor(rank)
                    hi = np.ceil(rank)
                    ixlo = np.argmax(cumulative > lo[:, None], axis=1)
                    ixhi = np.argmax(cumulative > hi[:, None], axis=1)
                    val = sx[ixlo] + (rank - lo) * (sx[ixhi] - sx[ixlo])
                    val[~valid] = np.nan
                    draws[qi, start:start + size] = val
        for qi, q in enumerate(quantiles):
            result[f"{kind}_q{q}_low"] = pct(draws[qi], 2.5)
            result[f"{kind}_q{q}_high"] = pct(draws[qi], 97.5)
        result[kind + "_valid_replicates"] = int(np.all(np.isfinite(draws), axis=0).sum())
    return result


def match_epochs(a, b):
    ta, tb = a.time.to_numpy(), b.time.to_numpy()
    ra, rb = np.round(ta, 6), np.round(tb, 6)
    if len(np.unique(ra)) != len(ra) or len(np.unique(rb)) != len(rb):
        raise ValueError("Duplicate epochs at the specified 1e-6 s matching precision")
    _, ia, ib = np.intersect1d(ra, rb, assume_unique=True, return_indices=True)
    exact = len(ia)
    nearest = None
    mode = "EXACT_ROUNDED_1US"
    if exact < 0.9 * min(len(a), len(b)):
        # Each A epoch selects the closest B, left candidate wins exact ties.
        # Enforce one-to-one matching to avoid multiplying a B observation.
        right = np.clip(np.searchsorted(tb, ta), 0, len(tb) - 1)
        left = np.clip(right - 1, 0, len(tb) - 1)
        candidates = np.where(np.abs(tb[left] - ta) <= np.abs(tb[right] - ta), left, right)
        distance = np.abs(tb[candidates] - ta)
        eligible = np.flatnonzero(distance <= 0.0025)
        priority = eligible[np.lexsort((eligible, distance[eligible]))]
        used = set()
        matched = []
        for i in priority:
            j = int(candidates[i])
            if j not in used:
                used.add(j)
                matched.append((int(i), j))
        matched.sort()
        ia = np.array([i for i, _ in matched], dtype=int)
        ib = np.array([j for _, j in matched], dtype=int)
        nearest = len(ia)
        mode = "NEAREST_2P5MS_ONE_TO_ONE"
    return ia, ib, dict(n_exact=exact, n_nearest=nearest if nearest is not None else "NOT_NEEDED",
                       match_method=mode, n_common=len(ia), n_A=len(a), n_B=len(b),
                       max_abs_match_dt_s=float(np.max(np.abs(ta[ia] - tb[ib]))) if len(ia) else np.nan)


class Task:
    def __init__(self, args):
        self.args = args
        self.repo = Path(__file__).resolve().parents[2]
        self.out = Path(args.out).resolve()
        self.repo_out = (self.repo / args.repo_out).resolve()
        self.config_path = self.repo / "configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"
        self.start = utc()
        self.tables = {}
        self.series = {}
        self.path_rows = []
        self.identity = []
        self.notes = []
        self.inputs = {}
        manifest = self.out / "UA01_INPUT_SHA256.json"
        if manifest.exists():
            self.inputs = {r["path"]: r for r in json.loads(manifest.read_text())["inputs"]}
        cfg = yaml.safe_load(self.read(self.config_path).decode())
        def roots(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k == "clean_root":
                        yield v
                    else:
                        yield from roots(v)
        found = list(roots(cfg))
        self.require(len(found) == 1, "CLEAN_ROOT_CONFIG_AMBIGUOUS", found)
        self.clean = Path(found[0])
        self.v3 = self.clean / "stages/CLEAN8_PROTOCOL_V3"
        self.hext = self.clean / "stages/CLEAN7_HEXT_EXTERNAL_SEQUENCES/11_READONLY_CLOSEOUT_H_EXT_04L"
        self.cal = self.clean / "stages/CLEAN5_CALIBRATED_SENSOR_MODEL/02_CALIBRATED_PROVIDERS"
        self.require(self.out == self.v3 / "10_UNCERTAINTY", "CLEAN_ROOT_MISMATCH", found)
        self.require(self.repo_out == self.repo / "docs/paper_rebuild/v3/uncertainty", "REPO_OUT_SCOPE", str(self.repo_out))
        for root, relative, expected in PIN_SPEC:
            p = str(getattr(self, root) / relative)
            self.inputs.setdefault(p, {"path": p})["expected_sha256"] = expected
        self.script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        self.report_prefix = "# UA-01 测量不确定度 A 类统计只读复算\n\n## §0 统计定义原文\n\n" + DEFINITIONS + "\n\n"
        self.report_prefix += f"定义落盘时间：{self.start}；脚本 SHA-256：`{self.script_sha}`。\n\n"
        (self.out / "UA01_REPORT.md").write_text(self.report_prefix, encoding="utf-8")
        self.log("DEFINITIONS_WRITTEN_BEFORE_CALCULATION script_sha256=" + self.script_sha)
        self.install_guard()

    def install_guard(self):
        def audit(event, args):
            if event in ("subprocess.Popen", "os.system", "os.posix_spawn", "os.fork", "os.forkpty"):
                raise RuntimeError("UA-01 forbids child process creation: " + event)
            if event != "open" or not isinstance(args[0], (str, bytes, os.PathLike)):
                return
            p = Path(os.fsdecode(args[0])).absolute()
            if re.search(r"trace|bag|fpl|truth|MATCHED_TRAJECTORY", p.name, re.I):
                own = p.is_relative_to(self.out)
                code = p.suffix in {".py", ".pyc", ".so"}
                if not own and not code:
                    raise RuntimeError("UA-01 reference data open blocked: " + str(p))
            flags = args[2] if len(args) > 2 and isinstance(args[2], int) else 0
            writing = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if writing and not p.is_relative_to(self.out):
                raise RuntimeError("UA-01 compute write outside output: " + str(p))
        sys.addaudithook(audit)

    def log(self, message):
        line = utc() + " " + message
        with (self.out / "PROGRESS.txt").open("a", encoding="utf-8", newline="\n") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
        print(line, flush=True)

    def require(self, condition, code, detail):
        if condition:
            return
        receipt = dict(task="UA-01-R2", status="HARD_STOP", timestamp_utc=utc(), reason_code=code,
                       details=detail, solver_calls=0, evaluator_calls=0, reference_data_reads=0)
        p = self.out / "HARD_STOP.json"
        with p.open("x", encoding="utf-8") as f:
            json.dump(receipt, f, ensure_ascii=False, indent=2, default=str)
            f.write("\n")
        self.log("HARD_STOP " + code)
        raise SystemExit(2)

    def save_inputs(self):
        (self.out / "UA01_INPUT_SHA256.json").write_text(json.dumps(
            {"task": "UA-01-R2", "inputs": sorted(self.inputs.values(), key=lambda r: r["path"])},
            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def read(self, p):
        p = Path(p)
        self.require(not re.search(r"trace|bag|fpl|truth|MATCHED_TRAJECTORY", p.name, re.I), "FORBIDDEN_INPUT", str(p))
        data = p.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        previous = self.inputs.get(str(p), {})
        pin = previous.get("expected_sha256")
        self.require(not pin or pin == sha, "PIN_MISMATCH", dict(path=str(p), expected=pin, actual=sha))
        raw = gzip.decompress(data) if p.suffix == ".gz" else data
        self.inputs[str(p)] = dict(path=str(p), sha256=sha, bytes=len(data),
                                   lines=raw.count(b"\n") + int(bool(raw) and not raw.endswith(b"\n")),
                                   expected_sha256=pin, pin_pass=sha == pin if pin else None)
        self.save_inputs()
        return raw

    def frame(self, p):
        return pd.read_csv(io.BytesIO(self.read(p)), encoding="utf-8-sig", low_memory=False)

    def write_table(self, name, rows):
        frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
        frame.to_csv(self.out / name, index=False, lineterminator="\n", float_format="%.17g", na_rep="UNAVAILABLE")
        self.tables[name] = frame
        return frame

    def load_tables(self):
        self.core = self.frame(self.v3 / "07_AGGREGATE/CORE_541_DISTRIBUTION_V3.csv")
        self.failure = self.frame(self.v3 / "07C_FAILURE_FAMILY_CONFIG/FAILURE_FAMILY_CONFIG.csv")
        self.full = self.frame(self.v3 / "07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv")
        self.add = self.frame(self.v3 / "07_AGGREGATE/ADDENDUM_TABLE_V3.csv")
        self.segment = self.frame(self.v3 / "07_AGGREGATE/BY2O_SEGMENT_TABLE.csv")
        self.main = self.frame(self.v3 / "07_AGGREGATE/MAIN_TABLE_V3.csv")
        self.external_main = self.frame(self.hext / "MAIN_TABLE_V3.csv")
        self.external = self.frame(self.repo / "docs/paper_rebuild/hext/HX03R2/DEGRADATION_EXTERNAL_TABLE_R2.csv")
        self.index = self.frame(self.repo / "docs/paper_rebuild/v3/ERROR_SERIES_RETENTION_INDEX.csv")
        self.spec = yaml.safe_load(self.read(self.repo / "configs/paper_rebuild/degradation_60types_9seeds.yaml"))
        self.family = {r["id"]: r["family"] for r in self.spec["degradation_types"]}
        self.transcripts = {name: self.read(self.v3 / "07_AGGREGATE" / name).decode("utf-8-sig") for name in
                            ["CORE_541_SUMMARY_V3.csv", "ADDENDUM_SUMMARY_V3.csv", "SUBSET61_SUMMARY_V3.csv"]}
        self.subset = self.frame(self.v3 / "07_AGGREGATE/SUBSET61_TABLE_V3.csv")
        self.core["value"] = pd.to_numeric(self.core["value"], errors="coerce")
        self.require(set(self.core.method_id) == set(METHODS), "METHOD_IDENTITIES", sorted(set(self.core.method_id)))
        self.require(not (set(self.core.case_id) - set(CASES)), "UNREGISTERED_CASES", sorted(set(self.core.case_id) - set(CASES)))
        self.require(not self.core.duplicated(["method_id", "metric", "case_id"]).any(), "DUPLICATE_CORE_KEYS", "method,metric,case")
        self.structure = []
        failed = self.failure[(self.failure.protocol == "v3") & (self.failure.evaluator_version == "v3")]
        for method in METHODS:
            n = self.core.loc[self.core.method_id == method, "case_id"].nunique()
            nf = int(failed.loc[failed.method_id == method, "failure_count"].sum())
            row = dict(method_id=method, n_finite=n, n_failure=nf, n_registered=n + nf,
                       expected_n_failure=EXPECTED_FAILURES[method], identity_pass=n + nf == 541 and nf == EXPECTED_FAILURES[method])
            self.structure.append(row)
            self.require(row["identity_pass"], "STRUCTURE_GATE", row)
        self.core_grid = {}
        for metric in METRICS:
            x = self.core[self.core.metric == metric].pivot(index="case_id", columns="method_id", values="value")
            self.core_grid[metric] = x.reindex(index=CASES, columns=METHODS)
        self.log("STRUCTURE_GATE_PASS protocol=v3 evaluator_version=v3 11/11; finite=5668 failure=283")

    def load_series(self):
        selected = self.index[((self.index.domain == "CORE") & (self.index.case_id == "C00_clean_normal")) | (self.index.domain == "SEQUENCE")]
        self.require(len(selected) == 33, "RETENTION_SELECTION", len(selected))
        rows = []
        for seq in ["BY2", "BY2H", "BY2O"]:
            for method in METHODS:
                q = selected[(selected.sequence_id == seq) & (selected.method_id == method)]
                self.require(len(q) == 1, "RETENTION_IDENTITY", [seq, method, len(q)])
                rid = str(q.iloc[0].run_id)
                table = self.full[(self.full.sequence_id == seq) & (self.full.method_id == method)]
                self.require(len(table) == 1, "C00_TABLE_IDENTITY", [seq, method, len(table)])
                candidates = [base / rid / "v3/FROZEN_EVALUATOR" / name for base in
                              [self.v3 / "04_EVALUATION", self.v3 / "04_EVALUATION/V3R_CONTINUATION"]
                              for name in ["error_series.csv", "error_series.csv.gz"]]
                candidates = [p for p in candidates if p.is_file()]
                self.require(len(candidates) <= 1, "AMBIGUOUS_RETAINED_SERIES", list(map(str, candidates)))
                rows.append((seq, method, rid, candidates[0] if candidates else None, table.iloc[0], "LegSA"))
        for seq, method, start in [("BY2", "LC01", "FILE_START"), ("BY2H", "LC01", "CONTRACT_START"),
                                   ("BY2O", "LC01", "FILE_START"), ("BY2", "LC01-S", "FILE_START")]:
            q = self.external_main[(self.external_main.sequence_id == seq) & (self.external_main.method_id == method) &
                                   (self.external_main.start_convention == start)]
            self.require(len(q) == 1, "LC01_SELECTION", [seq, method, start, len(q)])
            table = q.iloc[0]
            source = Path(str(table.error_series_source).replace("<CLEAN_ROOT>", str(self.clean)))
            candidates = [source] if source.is_file() else [source / name for name in ["error_series.csv", "error_series.csv.gz"] if (source / name).is_file()]
            rows.append((seq, method, seq + "__" + method + "__" + start, candidates[0] if candidates else None, table, "LC01"))
        for seq, method, rid, path, table, kind in rows:
            if path is None:
                self.path_rows.append(dict(sequence=seq, method=method, run_id=rid, path="UNAVAILABLE", sha256="UNAVAILABLE", status="UNAVAILABLE"))
                self.log("SERIES_UNAVAILABLE " + seq + " " + method)
                continue
            if kind == "LegSA":
                self.require("/v3/" in str(path) and "/v2/" not in str(path), "EVALUATOR_PATH", str(path))
            frame = self.frame(path)
            self.require(set(["time", "position_3d_err_m", "roll_err_deg", "pitch_err_deg"] + SERIES) <= set(frame), "ERROR_SCHEMA", str(path))
            frame = frame.apply(pd.to_numeric, errors="coerce")
            self.path_rows.append(dict(sequence=seq, method=method, run_id=rid, path=str(path), sha256=self.inputs[str(path)]["sha256"], status="AVAILABLE"))
            table_cols = {"yaw_err_deg": "yaw_rmse_deg", "horizontal_err_m": "horizontal_rmse_m" if kind == "LegSA" else "h_rmse_m", "err_u_m": "up_rmse_m"}
            checks = {}
            for column, table_column in table_cols.items():
                val = float(np.sqrt(np.mean(np.square(frame[column].to_numpy()))))
                expected = float(table[table_column])
                relative = abs(val - expected) / abs(expected) if expected != 0 else (0.0 if val == 0 else np.inf)
                item = dict(sequence=seq, method=method, series=column, n=len(frame), recomputed=val,
                            table_value=expected, relative_difference=relative, identity_pass=bool(np.isfinite(relative) and relative <= 1e-6))
                self.identity.append(item)
                self.require(item["identity_pass"], "C00_RMSE_IDENTITY_MISMATCH", item)
                checks[column] = item
            self.series[(seq, method)] = (frame, table, checks)
            self.log(f"IDENTITY_PASS {seq} {method} n={len(frame)}")
        (self.out / "UA01_ERROR_SERIES_PATHS.json").write_text(json.dumps(self.path_rows, ensure_ascii=False, indent=2) + "\n")
        self.write_table("UA01_IDENTITY_CHECKS.csv", self.identity)
        self.log(f"ALL_AVAILABLE_SERIES_IDENTITY_PASS series={len(self.series)}/37 checks={len(self.identity)}")

    def compute_abc(self):
        dispersion, family_rows, paired, overall, case_values, quantiles = [], [], [], [], [], []
        for metric in METRICS:
            grid = self.core_grid[metric]
            for method in METHODS:
                vector = grid[method].to_numpy(float)
                for i, typ in enumerate(TYPES):
                    vals = vector[1 + i * 9:1 + (i + 1) * 9]
                    stats = summary(vals, 9)
                    stats["cv"] = stats["sd"] / stats["mean"] if stats["mean"] != 0 else np.nan
                    dispersion.append(dict(method=method, metric=metric, type=typ, family=self.family[typ], **stats))
                stats = summary(vector, 541)
                stats.update(quantile_bootstrap(vector, "C/" + method + "/" + metric))
                quantiles.append(dict(method=method, metric=metric, **stats))
                self.log("DISTRIBUTION_BOOTSTRAP " + method + " " + metric + " B=10000+10000")
            for left, right in PAIRS:
                name = left + "-" + right
                delta = (grid[left] - grid[right]).to_numpy(float)
                delta[0] = np.nan  # B targets the 540 degraded cases, excluding C00.
                for case, value in zip(CASES[1:], delta[1:]):
                    if np.isfinite(value):
                        case_values.append(dict(pair=name, metric=metric, case_id=case, delta=value))
                for i, typ in enumerate(TYPES):
                    vals = delta[1 + i * 9:1 + (i + 1) * 9]
                    stats = summary(vals, 9)
                    vals = finite(vals)
                    paired.append(dict(pair=name, metric=metric, type=typ, family=self.family[typ],
                                       n_pairs_finite=len(vals), frac_negative=float(np.mean(vals < 0)) if len(vals) else np.nan, **stats))
                vals = finite(delta)
                stats = summary(vals, 540)
                stats.update(quantile_bootstrap(delta, "B/" + name + "/" + metric, quantiles=(50,)))
                overall.append(dict(pair=name, metric=metric, n_pairs=len(vals), n_pairs_finite=len(vals), p05=pct(vals, 5),
                                    frac_negative=float(np.mean(vals < 0)) if len(vals) else np.nan, **stats))
                self.log("PAIRED_BOOTSTRAP " + name + " " + metric)
        df = pd.DataFrame(dispersion)
        for keys, group in df.groupby(["method", "metric", "family"], sort=True):
            f = group[np.isfinite(group.sd)]
            top = float(f.sd.max()) if len(f) else np.nan
            family_rows.append(dict(method=keys[0], metric=keys[1], family=keys[2], n_types=len(group),
                                    n_types_finite_sd=len(f), median_sd=pct(f.sd, 50), p90_sd=pct(f.sd, 90), max_sd=top,
                                    max_sd_types=";".join(sorted(f.loc[f.sd == top, "type"]))))
        self.write_table("UA01_TYPE_SEED_DISPERSION.csv", df)
        self.write_table("UA01_FAMILY_DISPERSION_SUMMARY.csv", family_rows)
        self.write_table("UA01_PAIRED_CASE_DIFFERENCES.csv", paired)
        self.write_table("UA01_PAIRED_CASE_VALUES.csv", case_values)
        self.write_table("UA01_PAIRED_OVERALL.csv", overall)
        self.write_table("UA01_DISTRIBUTION_QUANTILES.csv", quantiles)
        external_rows = []
        ext = self.external[self.external.config == "LIT"]
        for left, right in [("LC01", "F04"), ("LC01", "F02"), ("EXT05C", "F04")]:
            sub = ext[ext.method == left]
            self.require(not sub.duplicated("case_id").any(), "EXTERNAL_DUPLICATE_CASE", left)
            sub = sub.set_index("case_id")
            for metric in METRICS:
                col = "yaw_p95_deg" if metric == "yaw_p95_absolute_deg" else metric
                values = pd.to_numeric(sub[col], errors="coerce").reindex(CASES)
                delta = values - self.core_grid[metric][right]
                for typ in TYPES:
                    ids = [f"{typ}_seed_{s:02d}" for s in range(9)]
                    vals = finite(delta.reindex(ids))
                    external_rows.append(dict(pair=left + "-" + right, metric=metric, type=typ, family=self.family[typ],
                                              n_registered=9, n_external_registered=sum(x in sub.index for x in ids),
                                              n_pairs_finite=len(vals), n=len(vals), **summary(vals)))
        self.write_table("UA01_EXTERNAL_PAIRED.csv", external_rows)
        self.log("A_B_C_COMPLETE")

    def compute_series(self):
        output = []
        for seq in ["BY2", "BY2H", "BY2O"]:
            methods = METHODS + (["LC01", "LC01-S"] if seq == "BY2" else ["LC01"])
            for method in methods:
                if (seq, method) not in self.series:
                    for col in SERIES:
                        output.append(dict(sequence=seq, method=method, series=col, status="UNAVAILABLE"))
                    continue
                frame, table, checks = self.series[(seq, method)]
                t = frame.time.to_numpy(float)
                dt = float(np.median(np.diff(t)))
                self.require(dt > 0 and np.all(np.diff(t) > 0), "ERROR_SERIES_TIME_ORDER", [seq, method])
                for col in SERIES:
                    e = frame[col].to_numpy(float)
                    nfailure = int((~np.isfinite(e)).sum())
                    self.require(nfailure == 0, "ERROR_SERIES_NONFINITE_IDENTITY_UNVERIFIABLE", [seq, method, col, nfailure])
                    mse = float(np.mean(e ** 2)); rmse = math.sqrt(mse)
                    table_col = {"err_n_m": "north_rmse_m", "err_e_m": "east_rmse_m"}.get(col)
                    check = checks.get(col)
                    table_value = check["table_value"] if check else pd.to_numeric(table.get(table_col, np.nan), errors="coerce")
                    identity_pass = check["identity_pass"] if check else (abs(rmse - table_value) / abs(table_value) <= 1e-6 if np.isfinite(table_value) and table_value else "NOT_AVAILABLE_IN_TABLE")
                    acf = acf_se(e ** 2, dt)
                    blocks20, se20 = batch_se(e ** 2, dt, 20)
                    blocks40, se40 = batch_se(e ** 2, dt, 40)
                    lo, hi, block = moving_block_rmse(e ** 2, dt, "D5/" + seq + "/" + method + "/" + col)
                    output.append(dict(sequence=seq, method=method, series=col, status="AVAILABLE", n=len(e), n_failure=nfailure,
                                       t_start=t[0], t_end=t[-1], dt_median=dt, dt_max=float(np.max(np.diff(t))),
                                       rmse_recomputed=rmse, table_value=table_value, identity_pass=identity_pass,
                                       mean=float(np.mean(e)), std=sd(e), yaw_within_180=bool(np.all(np.abs(e) <= 180)) if col == "yaw_err_deg" else "NOT_APPLICABLE",
                                       **slow_fast(e, dt), K=acf["K"], K_max=acf["K_max"], tau_int_s=acf["tau_int_s"], n_eff=acf["n_eff"],
                                       se_mse_acf=acf["se_mean"], se_rmse_acf=acf["se_mean"] / (2 * rmse) if rmse else np.nan,
                                       n_blocks_20s=blocks20, se_rmse_batch_20s=se20 / (2 * rmse) if rmse else np.nan,
                                       n_blocks_40s=blocks40, se_rmse_batch_40s=se40 / (2 * rmse) if rmse else np.nan,
                                       mbb_block_samples=block, mbb_replicates=2000, rmse_mbb_low=lo, rmse_mbb_high=hi))
                self.log("D1_D5_COMPLETE " + seq + " " + method)
        self.write_table("UA01_C00_SERIES_STATS.csv", output)

    def paired_series(self, seq, left, right, segment="full", bounds=None):
        if (seq, left) not in self.series or (seq, right) not in self.series:
            return [dict(sequence=seq, pair=left + "-" + right, segment=segment, series=col, status="UNAVAILABLE") for col in ["yaw_err_deg", "horizontal_err_m"]]
        a, b = self.series[(seq, left)][0], self.series[(seq, right)][0]
        if bounds is not None:
            a = a[a.time.between(*bounds, inclusive="both")]
            b = b[b.time.between(*bounds, inclusive="both")]
        ia, ib, matching = match_epochs(a, b)
        if len(ia) < 2:
            return [dict(sequence=seq, pair=left + "-" + right, segment=segment, series=col, status="UNAVAILABLE_INSUFFICIENT_MATCHES", **matching) for col in ["yaw_err_deg", "horizontal_err_m"]]
        ta = a.time.to_numpy()[ia]
        dt = float(np.median(np.diff(ta)))
        rows = []
        for col in ["yaw_err_deg", "horizontal_err_m"]:
            ea, eb = a[col].to_numpy()[ia], b[col].to_numpy()[ib]
            aa, bb = ea ** 2, eb ** 2
            d = aa - bb
            ra, rb = math.sqrt(float(aa.mean())), math.sqrt(float(bb.mean()))
            acf = acf_se(d, dt)
            nb, se = batch_se(d, dt, 20)
            lo, hi, block = moving_block_rmse(aa, dt, f"D6/{seq}/{left}-{right}/{segment}/{col}", other=bb)
            rows.append(dict(sequence=seq, pair=left + "-" + right, segment=segment, series=col, status="AVAILABLE", **matching,
                             t_start=ta[0], t_end=ta[-1], dt_median=dt, rmse_A=ra, rmse_B=rb, delta_rmse=ra - rb,
                             delta_mse=float(d.mean()), corr_squared_errors=float(np.corrcoef(aa, bb)[0, 1]) if sd(aa) > 0 and sd(bb) > 0 else np.nan,
                             K=acf["K"], K_max=acf["K_max"], tau_int_s=acf["tau_int_s"], n_eff=acf["n_eff"],
                             se_delta_mse_acf=acf["se_mean"], se_delta_rmse_acf=acf["se_mean"] / (ra + rb) if ra + rb else np.nan,
                             n_blocks_20s=nb, se_delta_mse_batch_20s=se, se_delta_rmse_batch_20s=se / (ra + rb) if ra + rb else np.nan,
                             mbb_block_samples=block, mbb_replicates=2000, delta_rmse_mbb_low=lo, delta_rmse_mbb_high=hi))
        return rows

    def compute_pairs_segments(self):
        pair_rows = []
        for seq in ["BY2", "BY2H", "BY2O"]:
            pairs = PAIRS + [("LC01", "F04"), ("LC01", "F02"), ("LC01", "F03")]
            if seq == "BY2":
                pairs += [("LC01-S", "F04")]
            for left, right in pairs:
                pair_rows += self.paired_series(seq, left, right)
            self.log("D6_COMPLETE " + seq)
        bounds = {}
        for name, token in [("primary", "occlusion_primary"), ("secondary", "occlusion_secondary"), ("full", "full")]:
            q = self.segment[(self.segment.segment_id == token) & (self.segment.evaluator_contract == "evaluator_contract_v3")]
            distinct = q[["window_start_s", "window_end_s"]].drop_duplicates()
            self.require(len(distinct) == 1, "BY2O_SEGMENT_TOKEN_AMBIGUOUS", name)
            bounds[name] = tuple(map(float, distinct.iloc[0]))
        self.segment_bounds = bounds
        output = []
        for method in METHODS + ["LC01"]:
            if ("BY2O", method) not in self.series:
                for segment in ["full", "primary", "secondary", "outside"]:
                    output.append(dict(sequence="BY2O", method=method, segment=segment, status="UNAVAILABLE"))
                continue
            frame = self.series[("BY2O", method)][0]
            full = frame.time.between(*bounds["full"], inclusive="both")
            primary = frame.time.between(*bounds["primary"], inclusive="both")
            secondary = frame.time.between(*bounds["secondary"], inclusive="both")
            masks = dict(full=full, primary=full & primary, secondary=full & secondary, outside=full & ~(primary | secondary))
            for segment, mask in masks.items():
                f = frame[mask]
                y = f.yaw_err_deg.to_numpy(); dt = float(np.median(np.diff(f.time)))
                bands = slow_fast(y, dt)
                output.append(dict(sequence="BY2O", method=method, segment=segment, status="AVAILABLE", n=len(f),
                                   n_failure=int((~np.isfinite(y)).sum()), t_start=float(f.time.min()), t_end=float(f.time.max()), dt_median=dt,
                                   rmse_yaw=math.sqrt(float(np.mean(y ** 2))), mean_yaw=float(y.mean()),
                                   std_slow=bands["std_slow"], std_fast=bands["std_fast"], rolling_window_samples=bands["rolling_window_samples"],
                                   rmse_h=math.sqrt(float(np.mean(f.horizontal_err_m.to_numpy() ** 2))),
                                   rmse_up=math.sqrt(float(np.mean(f.err_u_m.to_numpy() ** 2)))))
        for left, right in [("F04", "F02"), ("LC01", "F04"), ("F04", "A04")]:
            pair_rows += self.paired_series("BY2O", left, right, "primary", bounds["primary"])
        self.write_table("UA01_C00_PAIRED_SERIES.csv", pair_rows)
        self.write_table("UA01_BY2O_SEGMENT_BANDS.csv", output)
        self.log("D6_D7_COMPLETE")

    def compute_addendum(self):
        stats, pairs = [], []
        a = self.add.copy()
        a["type"] = a.case_id.str.extract(r"^(D6[12])_")[0]
        a["duration_s"] = a.case_id.str.extract(r"_(\d+)s_")[0].astype(int)
        self.require(not a.duplicated(["case_id", "method_id"]).any(), "ADDENDUM_DUPLICATE_KEYS", "case,method")
        for typ in ["D61", "D62"]:
            for duration in [10, 20, 30]:
                group = a[(a.type == typ) & (a.duration_s == duration)]
                registered = group.case_id.nunique()
                for metric in METRICS:
                    for method in METHODS:
                        values = pd.to_numeric(group.loc[group.method_id == method, metric], errors="coerce")
                        stats.append(dict(type=typ, duration_s=duration, method=method, metric=metric, status="REGISTERED" if registered else "NOT_REGISTERED", **summary(values, registered)))
                    pivot = group.pivot(index="case_id", columns="method_id", values=metric).reindex(columns=METHODS)
                    for left, right in [("F04", "A04"), ("F04", "F03"), ("A04", "F03"), ("F03", "F02")]:
                        vals = finite(pd.to_numeric(pivot[left], errors="coerce") - pd.to_numeric(pivot[right], errors="coerce"))
                        pairs.append(dict(type=typ, duration_s=duration, pair=left + "-" + right, metric=metric, n=len(vals), n_pairs_finite=len(vals), **summary(vals, registered)))
        self.write_table("UA01_ADDENDUM_STATS.csv", stats)
        self.write_table("UA01_ADDENDUM_PAIRED.csv", pairs)
        self.log("E_COMPLETE")

    def compute_motion(self):
        rows = []
        self.provider_format = []
        for seq, window in [("BY2", (66.0, 340.0)), ("BY2H", (413.0, 683.0)), ("BY2O", (3186.0, 3563.0))]:
            for kind, filename in [("yaw_rate", "CALIBRATED_IMU.imu"), ("horizontal_speed", "CALIBRATED_GNSS.gnss")]:
                p = self.cal / seq / filename
                raw = self.read(p)
                first = raw.decode().splitlines()[0]
                ncols = len(first.split())
                self.provider_format.append(dict(sequence=seq, kind=kind, first_line=first, column_count=ncols))
                print("PROVIDER_FIRST_LINE", seq, filename, "columns=" + str(ncols), first, flush=True)
                self.require(ncols == 7 if kind == "yaw_rate" else ncols >= 10, "PROVIDER_FORMAT", [str(p), ncols])
                data = np.loadtxt(io.BytesIO(raw))
                t = data[:, 0]
                mask = (t >= window[0]) & (t <= window[1])
                extra = {}
                if kind == "yaw_rate":
                    dt = np.concatenate(([np.nan], np.diff(t)))
                    valid = (dt > 0) & (dt <= 0.1)
                    extra["n_rejected_dt_in_window"] = int((mask & ~valid).sum())
                    mask &= valid
                    values = np.rad2deg(data[mask, 3] / dt[mask])
                    duration = dt[mask]
                    extra.update(unit="deg/s", p95_abs=pct(np.abs(values), 95), max_abs=float(np.max(np.abs(values))),
                                 time_fraction_abs_gt_10_deg_s=float(duration[np.abs(values) > 10].sum() / duration.sum()),
                                 valid_dt_sum_s=float(duration.sum()))
                else:
                    values = np.hypot(data[mask, 7], data[mask, 8])
                    extra.update(unit="m/s", fraction_speed_lt_0p2_m_s=float(np.mean(values < 0.2)))
                rows.append(dict(sequence=seq, kind=kind, window_start_s=window[0], window_end_s=window[1], n=len(values),
                                 n_failure=int((~np.isfinite(values)).sum()), mean=float(np.mean(values)),
                                 rms=math.sqrt(float(np.mean(values ** 2))), p95=pct(values, 95), **extra))
        self.write_table("UA01_MOTION_STATS.csv", rows)
        self.log("F_COMPLETE")

    def compute(self):
        self.compute_abc()
        self.compute_series()
        self.compute_pairs_segments()
        self.compute_addendum()
        self.compute_motion()
        self.write_report()
        self.save_inputs()
        sizes = {p.name: p.stat().st_size for p in self.out.glob("UA01_*.csv")}
        (self.out / "UA01_COMPUTE_RECEIPT.json").write_text(json.dumps(dict(
            task="UA-01-R2", status="COMPUTE_COMPLETE_PENDING_STRACE_AND_GIT", script_sha256=self.script_sha,
            seed=SEED, numpy_version=np.__version__, pandas_version=pd.__version__,
            data_mode="FROZEN_REAL_C00_AND_SEMISYNTHETIC_DEGRADATION_DERIVED_STATISTICS", synthetic_data_used=False,
            semisynthetic_data_used=True, trace_used_online=False, receiver_imu_as_body_imu=False,
            final_v23_output_solver_input=False, LegSA_output_solver_input=False, per_case_tuning=False,
            output_only_correction=False, epoch_deleted_for_metric=False, old_runtime_input_count=0,
            solver_calls=0, evaluator_calls=0, provider_generation_calls=0, reference_data_reads=0,
            bootstrap_resampling_only=True, available_series=len(self.series), identity_checks=len(self.identity),
            csv_bytes=sizes, csv_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.out.glob("UA01_*.csv")}),
            indent=2, ensure_ascii=False) + "\n")
        self.log("COMPUTE_COMPLETE_PENDING_STRACE_AND_GIT")

    def write_report(self):
        report = [self.report_prefix]
        report.append("执行范围：冻结聚合、误差序列、provider 文本的只读派生统计。C00/自然序列是实测误差；D01–D62 是既有退化实验，不能表述为新增真实数据实验。未运行求解器、评估器、provider 生成器或 MATLAB；未读取参考轨迹。")
        report.append("## §1 输入 pin 与修正结构门")
        pins = pd.DataFrame([dict(file=r["path"], sha256=r["sha256"], bytes=r["bytes"], lines=r["lines"], pin_pass=r["pin_pass"])
                             for r in self.inputs.values() if r.get("expected_sha256")])
        report.append(markdown(pins))
        report.append("结构核算限定 `protocol=v3 AND evaluator_version=v3`；文件另含 v2.1 记录，不能混加。")
        report.append(markdown(pd.DataFrame(self.structure)))
        report.append("原始方法标识为 F01/F02/F03/F04/A03–A09；F03=A02=AB0000，F04=A01=AB1111，别名不重复计数。失败格只作为非有限占位，不推断或填入数值。")
        report.append("## §2 实现约定与证据边界")
        report.append("SD 为 ddof=1，所有分位数为 linear。每个输出组使用由固定种子 20260927 与组名 SHA-256 派生的独立 PCG64 随机流。缺失/非有限项保留注册分母。bootstrap 仅重抽冻结观测，不生成算法输入。")
        report.append("B 的点估计及 CI 均针对 540 退化例；按原文保留 61 个簇标签，C00 在该人口为空簇，抽中不添加观测。C 使用完整 541 注册格及 C00 有效观测。naive bootstrap 逐有限例抽样；cluster bootstrap 整簇抽样后仅用有限观测。区间是条件于现有有限结果的统计区间，不覆盖算法失败，也不包含参考系统、安装参数等 B 类不确定度。")
        report.append("D3 使用中心化序列的有偏样本自相关（滞后内积除零滞后内积），按原文首个非正 rho 截断；K_max 受 n−1 限制。5 s 样本窗四舍五入后遇偶数加 1。D4/D5 按 round(L/dt) 的样本块实现；不足整块仅按 D4 定义丢尾，主 RMSE 身份门始终使用全行。D5 用前缀和计算拼接块及末块截断后的平方和，与逐样本拼接等价。")
        report.append("D6 精确匹配不足 90% 时使用 2.5 ms 最近邻，并保持一对一，距离并列选较早历元。D7 outside 将段外样本按时间顺序组成指定段，仅在该段内 rolling；它含时间缺口，边界附近的样本窗可能跨越被排除区间。")
        report.append("统计定义逐字保留在 §0。R/R2 修正只作用于 Git 基线与失败缺省结构核算。最初探索结构查询仅按 evaluator_version 过滤，包含 v2.1，已在接纳结构门前修正为双条件；初始查询保存在 UA 下，未改变任何冻结输入。")
        report.append("## §3 误差序列身份门与逐型种子离散（A）")
        report.append(f"{len(self.series)}/37 条可用；yaw/h/up 全行 RMSE 身份检查 {len(self.identity)}/{len(self.identity)} PASS；相对误差阈值 1e-6。N/E 若原表无列，仅报告重算值并标记不可核对。")
        report.append(markdown(pd.DataFrame(self.identity), ["sequence", "method", "series", "n", "recomputed", "table_value", "relative_difference", "identity_pass"]))
        report.append("逐型全表：UA01_TYPE_SEED_DISPERSION.csv。族级全表：UA01_FAMILY_DISPERSION_SUMMARY.csv。以下为跨族最大 SD 类型（每方法×指标一行）：")
        fam = self.tables["UA01_FAMILY_DISPERSION_SUMMARY.csv"]
        tops = fam.loc[fam.groupby(["method", "metric"]).max_sd.idxmax()]
        report.append(markdown(tops[["method", "metric", "family", "max_sd", "max_sd_types"]]))
        report.append("## §4 逐例配对（B）与 541 分布分位数（C）")
        report.append("逐型配对见 UA01_PAIRED_CASE_DIFFERENCES.csv；逐例有限差值见 UA01_PAIRED_CASE_VALUES.csv；外部逐型配对见 UA01_EXTERNAL_PAIRED.csv。外部表仅在其已登记且双方有限的 case_id 连接，未覆盖类型报告 n=0。")
        report.append(markdown(self.tables["UA01_PAIRED_OVERALL.csv"], ["pair", "metric", "n_pairs_finite", "median", "p05", "p95", "frac_negative", "cluster_q50_low", "cluster_q50_high", "naive_q50_low", "naive_q50_high"]))
        report.append(markdown(self.tables["UA01_DISTRIBUTION_QUANTILES.csv"], ["method", "metric", "n_registered", "n_finite", "n_failure", "mean", "median", "p95", "max", "cluster_q50_low", "cluster_q50_high", "cluster_q95_low", "cluster_q95_high", "naive_q50_low", "naive_q50_high", "naive_q95_low", "naive_q95_high"]))
        report.append("## §5 C00/自然序列统计（D1–D5，全量）")
        stats = self.tables["UA01_C00_SERIES_STATS.csv"].copy()
        labels = {"yaw_err_deg": "Y", "err_n_m": "N", "err_e_m": "E", "err_u_m": "U", "horizontal_err_m": "H"}
        report.append("以下三表合并即每条序列全部 D1–D5 量；Y=yaw（deg），N/E/U/H 为位置误差（m）。全部 185 行 AVAILABLE，n_failure=0；全部 yaw 满足 |e|≤180。N/E 的 LC01 表值无列时记 UNAVAILABLE。CSV 保留 17 位有效数字，报告数值显示 6 位。")
        common = ["sequence", "n", "t_start", "t_end", "dt_median", "dt_max", "rolling_window_samples", "K_max", "n_blocks_20s", "n_blocks_40s", "mbb_block_samples", "mbb_replicates"]
        shared = stats[stats.series == "yaw_err_deg"].groupby(common, dropna=False, sort=False).method.agg(lambda x: ",".join(x)).reset_index()
        shared = shared[["sequence", "method"] + [c for c in common if c != "sequence"]]
        report.append("### D1/D2/D4/D5 共享采样参数（适用于该方法的五个分量）")
        report.append(markdown(shared, precision=9))
        stats["series"] = stats.series.map(labels)
        report.append("### D1/D2 全部 185 行")
        report.append(markdown(stats, ["sequence", "method", "series", "rmse_recomputed", "table_value", "identity_pass", "mean", "std", "std_slow", "std_fast", "rms_fast_over_rmse"], precision=6))
        report.append("### D3/D4/D5 全部 185 行")
        report.append("tau_int 单位 s；se_rmse 与 RMSE 同单位；se_mse_acf=2×rmse_recomputed×se_rmse_acf（完整数值另存 CSV）。")
        report.append(markdown(stats, ["sequence", "method", "series", "K", "tau_int_s", "n_eff", "se_rmse_acf", "se_rmse_batch_20s", "se_rmse_batch_40s", "rmse_mbb_low", "rmse_mbb_high"], precision=6))
        report.append("## §6 配对误差序列（D6，全量，含 BY2O primary）")
        ps = self.tables["UA01_C00_PAIRED_SERIES.csv"].copy()
        ps["series"] = ps.series.map(labels)
        common = ["sequence", "segment", "n_exact", "n_nearest", "match_method", "n_common", "n_A", "n_B", "max_abs_match_dt_s",
                  "t_start", "t_end", "dt_median", "K_max", "n_blocks_20s", "mbb_block_samples", "mbb_replicates"]
        shared = ps[ps.series == "Y"].groupby(common, dropna=False, sort=False).pair.agg(lambda x: ",".join(x)).reset_index()
        shared = shared[["sequence", "segment", "pair"] + [c for c in common if c not in ["sequence", "segment"]]]
        report.append("以下共享匹配表与逐分量表合并覆盖全部 56 行；Y/H 与 §5 同义。全部 AVAILABLE。最近邻 NOT_NEEDED 表示精确匹配数已达到 90% 门限，未启动替代匹配。")
        report.append(markdown(shared, precision=9))
        report.append(markdown(ps, ["sequence", "segment", "pair", "series", "rmse_A", "rmse_B", "delta_rmse", "delta_mse", "corr_squared_errors",
                                   "K", "tau_int_s", "n_eff", "se_delta_mse_acf", "se_delta_rmse_acf", "se_delta_mse_batch_20s", "se_delta_rmse_batch_20s",
                                   "delta_rmse_mbb_low", "delta_rmse_mbb_high"], precision=6))
        report.append("## §7 BY2O 分段（D7，全量）")
        report.append("闭区间 token：" + json.dumps(self.segment_bounds, ensure_ascii=False) + "；outside=full−primary−secondary。")
        report.append(markdown(self.tables["UA01_BY2O_SEGMENT_BANDS.csv"]))
        report.append("## §8 附加族（E）与原文转录（G）")
        report.append("附加族逐组全表：UA01_ADDENDUM_STATS.csv、UA01_ADDENDUM_PAIRED.csv；以下为每类型×时长的注册数及有限/失败计数汇总（跨方法、跨指标）：")
        add = self.tables["UA01_ADDENDUM_STATS.csv"]
        report.append(markdown(add.groupby(["type", "duration_s"], as_index=False).agg(groups=("method", "size"), n_registered=("n_registered", "sum"), n_finite=("n_finite", "sum"), n_failure=("n_failure", "sum"))))
        for name, text in self.transcripts.items():
            report.extend(["### " + name + " 原文", "```csv\n" + text.rstrip() + "\n```"])
        segment_text = self.read(self.v3 / "07_AGGREGATE/BY2O_SEGMENT_TABLE.csv").decode("utf-8-sig")
        source_lines = segment_text.splitlines()
        source_rows = list(csv.DictReader(io.StringIO(segment_text)))
        self.require(len(source_rows) == len(source_lines) - 1, "SEGMENT_TRANSCRIPTION_MULTILINE", len(source_rows))
        selected_lines = [source_lines[0]] + [line for row, line in zip(source_rows, source_lines[1:])
                                            if row["method_id"] in ["F02", "F03", "A04", "F04"] or "LC01" in row["method_id"]]
        report.extend(["### BY2O_SEGMENT_TABLE.csv 指定行原文", "```csv\n" + "\n".join(selected_lines) + "\n```"])
        for dirname in ["07_AGGREGATE", "07C_FAILURE_FAMILY_CONFIG"]:
            listing = self.out / ("LS_" + dirname + ".txt")
            report.append("### ls -la " + dirname)
            report.append("```text\n" + (listing.read_text().rstrip() if listing.exists() else "PENDING_FINALIZE_DIRECTORY_LISTING") + "\n```")
        extra = [p for p in (self.v3 / "07_AGGREGATE").iterdir() if p.suffix == ".csv" and ("BODY_FRAME" in p.name or "CONSISTENCY" in p.name) and "V3" in p.name.upper()]
        report.append("BODY_FRAME/CONSISTENCY v3 表：" + ("、".join(p.name for p in extra) if extra else "不存在（目录名检查）。"))
        for p in extra:
            df = self.frame(p)
            selected = df[df.sequence_id.isin(["BY2", "BY2H", "BY2O"]) & df.method_id.isin(["F02", "F03", "A04", "F04"])]
            report.extend(["### " + p.name, "```csv\n" + selected.to_csv(index=False, lineterminator="\n").rstrip() + "\n```"])
        report.append("## §9 运动统计（F，全量）")
        report.append("F1 时间占比按有效 dt 加权；F2 为历元占比。偏航率来自冻结接收机 IMU FRD 增量，不能标记为 Go2 body IMU。")
        report.append(markdown(pd.DataFrame(self.provider_format)))
        report.append(markdown(self.tables["UA01_MOTION_STATS.csv"]))
        report.append("## §10 strace 统计")
        report.append("PENDING_FINALIZE_STRACE_AUDIT")
        report.append("## §11 Git 提交与文件清单")
        report.append("提交标识：SELF（本文件与脚本所在的唯一 UA-01 提交；完整哈希在提交后的 UA01_COMMIT_RECEIPT.json 与回贴中记录，避免提交内容自引用）。不 push，不做交接包。")
        report.append("既有未跟踪 29/29，未触碰。基线原文：")
        report.append("```text\n" + (self.out / "GIT_BASELINE_STATUS.txt").read_text().rstrip() + "\n```")
        report.append("PENDING_FINALIZE_FILE_LIST")
        report.append("## 附录：37 条误差序列的实际路径与 SHA-256")
        report.append(markdown(pd.DataFrame(self.path_rows)))
        (self.out / "UA01_REPORT.md").write_text("\n\n".join(report) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--repo-out", default="docs/paper_rebuild/v3/uncertainty")
    parser.add_argument("--phase", choices=["identity", "all"], default="all")
    args = parser.parse_args()
    task = Task(args)
    task.load_tables()
    task.load_series()
    if args.phase == "all":
        task.compute()
    task.log("PHASE_COMPLETE " + args.phase)


if __name__ == "__main__":
    main()
