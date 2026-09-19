#!/usr/bin/env python3
"""V3-01 step 0: read sealed prior results; never launch scientific processes.

All source files are read-only. Outputs are small, exclusive-create audit files.
The prerequisite fact conflict is reported, not silently resolved.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys

import pandas as pd
import yaml

CODE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE_ROOT / "src"))
from legsa_gins.paper_rebuild.hext.aggregate import segment_rows  # noqa: E402

BASE_COMMIT = "6257a4fa46efd11a8b8888c5e466cf923a45336e"
OUTPUT_ALIAS = "<CLEAN_ROOT>/stages/CLEAN8_PROTOCOL_V3/00_PREREQUISITES"
T5A_ALIAS = "<CLEAN_ROOT>/stages/CLEAN7_T5A_HEADING_SENSITIVITY/T5A_R"
STATUS = "BLOCKED_PREREQUISITE_FACT_CONFLICT_PENDING_USER_RESOLUTION"
METRICS = ("yaw_rmse_deg", "h_rmse_m")


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def git(*args):
    return subprocess.check_output(["git", "-C", str(CODE_ROOT), *args])


def finite(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def md_table(rows, fields):
    return "\n".join([
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
        *("| " + " | ".join(str(row[field]) for field in fields) + " |" for row in rows),
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-config", type=Path, default=CODE_ROOT / "configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml")
    args = parser.parse_args()
    paths = yaml.safe_load(args.local_config.read_text())["paths"]
    clean_root = Path(paths["clean_root"])
    aliases = {"<CODE_ROOT>": CODE_ROOT, "<CLEAN_ROOT>": clean_root}
    output = clean_root / "stages/CLEAN8_PROTOCOL_V3/00_PREREQUISITES"
    report_root = CODE_ROOT / "docs/paper_rebuild/v3"
    if output.exists() or report_root.exists():
        raise FileExistsError("Step-0 output/report directory already exists; no overwrite")
    head = git("rev-parse", "HEAD").decode().strip()
    if head != BASE_COMMIT:
        raise ValueError("Step 0 requires the exact authorized starting commit")
    pins = []

    def resolve(alias):
        for prefix, root in aliases.items():
            if alias.startswith(prefix + "/"):
                return root / alias[len(prefix) + 1:]
        if alias.startswith("<") or Path(alias).is_absolute():
            raise ValueError("Unregistered source alias")
        return CODE_ROOT / alias

    def verified(alias, expected, authority):
        payload = resolve(alias).read_bytes()
        actual = digest(payload)
        if actual != expected:
            raise ValueError(f"HARD_STOP_SOURCE_HASH_MISMATCH: {alias}")
        pins.append(dict(path=alias, sha256=actual, expected_sha256=expected,
                         authority=authority, status="PASS", size_bytes=len(payload)))
        return payload

    def tracked(path):
        committed = git("show", f"{BASE_COMMIT}:{path}")
        return verified(path, digest(committed), f"git:{BASE_COMMIT}:{path}")

    index_path = "configs/paper_rebuild/hext/T5BC_FROZEN_SOURCE_INDEX.yaml"
    index = yaml.safe_load(tracked(index_path))
    contract_path = "configs/paper_rebuild/hext/T5A_CONTRACT_V1.yaml"
    contract = yaml.safe_load(tracked(contract_path))
    segment_source = "src/legsa_gins/paper_rebuild/hext/aggregate.py"
    tracked(segment_source)

    def indexed(pin, authority):
        return verified(pin["path"], pin["sha256"], authority)

    def rows(payload):
        return list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))

    binary_checks = []
    for role in ("executable", "evaluator"):
        pin = contract["frozen"][role]
        indexed(pin, contract_path + ":frozen." + role)
        binary_checks.append(dict(role=role, path=pin["path"], sha256=pin["sha256"], status="PASS"))

    t5a_tables = {}
    for name, pin in index["t5a_r"]["tables"].items():
        payload = indexed(pin, index_path + ":t5a_r.tables." + name)
        t5a_tables[name] = json.loads(payload) if name.endswith(".json") else rows(payload)
    t5a_manifest = t5a_tables["AGGREGATE_MANIFEST.json"]
    indexed(index["t5a_r"]["final_summary"], index_path + ":t5a_r.final_summary")
    selected_cases = index["subset_case_source"]["selected_case_ids"]
    if len(selected_cases) != 61 or len(set(selected_cases)) != 61:
        raise ValueError("Subset case identity mismatch")
    indexed(index["subset_case_source"], index_path + ":subset_case_source")

    sums, comparisons, counts, failures = [], [], [], []
    for version in ("v3", "v2"):
        frozen_pin = index["subset_tables"][version]
        frozen_all = rows(indexed(frozen_pin, index_path + ":subset_tables." + version))
        frozen = {row["case_id"]: row for row in frozen_all
                  if row["case_id"] in selected_cases and row["method_id"] == "F04"}
        if len(frozen) != 61:
            raise ValueError("Frozen F04 subset does not have exactly 61 unique cases")
        for row in frozen.values():
            row["h_rmse_m"] = row["horizontal_rmse_m"]
        pilot = rows(tracked(f"docs/paper_rebuild/hext/t5bcr/PILOT_TABLE_{version.upper()}.csv"))
        subset = rows(tracked(f"docs/paper_rebuild/hext/t5bcr/SUBSET61_TABLE_{version.upper()}.csv"))
        r5 = {row["case_id"]: row for row in subset if row["variant"] == "R5"}
        if set(r5) != set(selected_cases):
            raise ValueError("Candidate R5 subset case identity mismatch")
        for row in subset:
            if row["variant"] == "FROZEN_V21":
                reference = frozen[row["case_id"]]
                for field in (*METRICS, "evaluation_status"):
                    missing_alias = field in METRICS and row[field] == "UNAVAILABLE" and reference[field] == ""
                    if row[field] != reference[field] and not missing_alias:
                        raise ValueError("Tracked frozen comparator differs from pinned original table")
        sum_by_variant = {}
        for variant in ("T5A_R5", "R5SIGMA", "R5W"):
            group = [row for row in pilot if row["configuration_id"] == "F04" and row["variant"] == variant]
            if len(group) != 3 or {row["sequence_id"] for row in group} != {"BY2", "BY2H", "BY2O"}:
                raise ValueError("Three-sequence F04 identity mismatch")
            if any(row["evaluation_status"] != "COMPLETED" or not finite(row["yaw_rmse_deg"]) for row in group):
                raise ValueError("Nonfinite three-sequence prerequisite row")
            if variant == "T5A_R5":
                authority = t5a_tables[f"SENSITIVITY_TABLE_{version.upper()}.csv"]
                for row in group:
                    match = [r for r in authority if r["sequence_id"] == row["sequence_id"]
                             and r["configuration_id"] == "F04" and r["variant"] == "R5"]
                    if len(match) != 1 or match[0]["yaw_rmse_deg"] != row["yaw_rmse_deg"]:
                        raise ValueError("T5bc-R R5 pilot token differs from pinned T5a-R source")
            sum_by_variant[variant] = sum(Decimal(row["yaw_rmse_deg"]) for row in group)
        for variant, total in sum_by_variant.items():
            sums.append(dict(evaluator=version, variant=variant, sequence_count=3,
                             yaw_rmse_sum_deg=str(total),
                             improvement_from_R5_deg=str(sum_by_variant["T5A_R5"] - total),
                             reaches_0p3_deg=(sum_by_variant["T5A_R5"] - total >= Decimal("0.3"))))
        for metric in METRICS:
            fset = {case for case, row in frozen.items() if row["evaluation_status"] == "COMPLETED" and finite(row[metric])}
            rset = {case for case, row in r5.items() if row["evaluation_status"] == "COMPLETED" and finite(row[metric])}
            counts.append(dict(evaluator=version, metric=metric, total_cases=61, frozen_finite=len(fset),
                               R5_finite=len(rset), paired_finite=len(fset & rset),
                               frozen_nonfinite=len(set(selected_cases) - fset),
                               R5_nonfinite=len(set(selected_cases) - rset),
                               R5_failed_on_frozen_completed=len(fset - rset)))
        for case in selected_cases:
            frow, rrow = frozen[case], r5[case]
            comparison = dict(evaluator=version, case_id=case,
                frozen_status=frow["evaluation_status"], frozen_terminal=frow["solver_terminal_status"],
                frozen_yaw_rmse_deg=frow["yaw_rmse_deg"] or "UNAVAILABLE",
                frozen_h_rmse_m=frow["horizontal_rmse_m"] if "horizontal_rmse_m" in frow else frow["h_rmse_m"],
                R5_status=rrow["evaluation_status"], R5_failure_classification=rrow["failure_classification"],
                R5_yaw_rmse_deg=rrow["yaw_rmse_deg"], R5_h_rmse_m=rrow["h_rmse_m"],
                paired_finite=finite(frow["yaw_rmse_deg"]) and finite(rrow["yaw_rmse_deg"]),
                R5_failed_on_frozen_completed=frow["evaluation_status"] == "COMPLETED" and rrow["evaluation_status"] != "COMPLETED")
            comparisons.append(comparison)
            if not comparison["paired_finite"]:
                failures.append(comparison)

    segments = []
    for version in ("v3", "v2"):
        for profile in ("F02", "F04"):
            for variant in ("R5", "R5F"):
                relative = f"04_EVAL/{version}/BY2O/{profile}/{variant}"
                seal_relative = relative + "/OUTPUT_SEAL.json"
                seal_hash = t5a_manifest["source_hashes"]["<T5A_SCRATCH>/" + seal_relative]
                seal = json.loads(verified(T5A_ALIAS + "/" + seal_relative, seal_hash,
                                          "T5a-R pinned AGGREGATE_MANIFEST.source_hashes"))
                if seal["status"] != "SEALED":
                    raise ValueError("T5a-R error-series seal not SEALED")
                error_name = "FROZEN_EVALUATOR/error_series.csv"
                error_alias = T5A_ALIAS + "/" + relative + "/" + error_name
                payload = verified(error_alias, seal["files"][error_name], T5A_ALIAS + "/" + seal_relative)
                if digest(payload) != t5a_manifest["source_hashes"]["<T5A_SCRATCH>/" + relative + "/" + error_name]:
                    raise ValueError("T5a-R aggregate versus seal error-series hash mismatch")
                frame = pd.read_csv(io.BytesIO(payload))
                derived = segment_rows(frame, sequence_id="BY2O", method_id=profile,
                    start_convention="FROZEN_V21_RUNTIME_CONFIG", version=version,
                    window=(3186.0, 3563.0), source=error_alias)
                for row in derived:
                    row.update(configuration_id=profile, variant=variant,
                               data_mode="real_raw_heading_sensitivity_outside_v21",
                               synthetic_data_used=False, semisynthetic_data_used=False,
                               source_sha256=digest(payload), evaluator_invoked=False)
                segments.extend(derived)
    selected = {row["variant"]: row["yaw_rmse_deg"] for row in segments
                if row["evaluator_contract"] == "evaluator_contract_v3" and row["method_id"] == "F04"
                and row["segment_id"] == "occlusion_primary"}
    selected_rule = "BOTH_CARRIER_PHASE_FIXED_OR_FLOAT" if selected["R5F"] <= selected["R5"] else "BOTH_FIXED"
    gates = [dict(gate=key, status="NOT_RUN") for key in ("2a_NON_HEADING_BYTE_IDENTITY", "2b_BY2_T5A_TABLE_HASH", "2c_ALL_CONFIGS_LINE_AND_211_ECHO", "2d_THREE_SEQUENCE_F01_NAV", "2e_BY2_F04_C00_NAV")]
    manifest = dict(schema_version="v3.prerequisites.v1", task="V3-01", status=STATUS,
        step0a_status="FACT_CONFLICT", step0b_status="COMPUTED_FROM_SEALED_EXISTING_ERROR_SERIES",
        code_commit=head, requested_start_commit=BASE_COMMIT,
        script_sha256=digest(Path(__file__).read_bytes()),
        data_mode="read_only_prior_real_raw_and_semisynthetic_cohorts_separate",
        synthetic_data_used=False, semisynthetic_data_used=True,
        semisynthetic_scope="0a degradation subset only; 0b is real-raw prior evaluation evidence",
        trace_used_online=False, receiver_imu_as_body_imu=False,
        final_v23_output_solver_input=False, LegSA_output_solver_input=False,
        per_case_tuning=False, output_only_correction=False, epoch_deleted_for_metric=False,
        old_runtime_input_count=0, config_hash=digest(resolve(contract_path).read_bytes()),
        config_hash_role="existing_T5A_CONTRACT_read_only_not_v3_runtime_config",
        native_invocations=0, evaluator_invocations=0, provider_invocations=0,
        trace_open_count=0, raw_payload_open_count=0, source_files_mutated=0,
        preregistration_approved=False, code_freeze="NOT_CREATED", full_matrix_status="NOT_RUN",
        selected_rule=selected_rule, selection_primary_evaluator="v3",
        selection_rule="F04 R5F primary yaw RMSE <= F04 R5 primary yaw RMSE implies both fixed/float; otherwise both fixed",
        selection_values_deg=selected, binary_identity_checks=binary_checks,
        sums=sums, finite_counts=counts, five_identity_gates=gates,
        fact_conflicts=["User stated frozen finite=57/nonfinite=4; pinned frozen F04 has finite=60/nonfinite=1.",
                        "User requested confirmation R5 has no failures on frozen-completed cases; D27/D57/D60 are all frozen COMPLETED and R5 failed."],
        source_hashes=pins)

    report = """# V3-01 第 0 步只读前置检查

状态：`BLOCKED_PREREQUISITE_FACT_CONFLICT_PENDING_USER_RESOLUTION`。0b 已计算，0a 中的冻结有限数与“无新增失败”前提同原始封存表冲突。此记录不批准预注册或全量执行，五个身份门均为 `NOT_RUN`。

起点与代码基线：`{head}`。用户授权的单项变更为原始 HPPOSECEF 5 Hz 标量航向；std 标记保持 `2.933193`。C++、参数、冻结二进制、评估器、IMU/位置/速度/RD/RP、全部工况 HV 文件均未改动。HV 保持 status 航向旋转的冻结文件，不用新航向重生成。既有草稿和冻结结果均保留。

## 0a：三序列与 61 例原始表回查

主评估器 v3 的 F04 三序列 yaw RMSE 之和及相对 R5 的下降量如下。0.3° 仅为用户指定的既有 T5bc-R 记录核对条件，不是后续 v3 结果筛选阈值。

{sums_table}

两版评估器均按相同 61 个 case ID 配对。有限要求原评价状态 `COMPLETED` 且对应指标有限；缺失不填零。

{count_table}

以下列出 v3 任一侧失败或非有限的全部四个 case，并排保留两侧原状态。**四个是两侧失败集合的并集，不是冻结 F04 的四个失败。** 冻结 F04 唯一非有限为 D37；R5 失败为 D27、D57、D60，这三例冻结均完成。R5 在 D37 有有限结果，所以 60 与 58 的交集是 57。不能确认“R5 未在冻结完成的工况上失败”。平行 v2 的逐例值见 CSV。

{failure_table}

0a 的这项冲突改变失败比较的科学含义，保留事实并等待用户裁定；没有改写既有表、删除工况或替换来源。

## 0b：BY2O 主段与次段

读取 T5a-R 已封存的 BY2O F02/F04 × R5/R5F error_series；先验证 T5BC 源索引 pin，再验证 T5a-R 聚合清单 → OUTPUT_SEAL → error_series 哈希链。直接调用原 `hext.aggregate.segment_rows`，主段闭区间 `[3369.94, 3411.95]` s、次段 `[3495.94, 3508.94]` s、全窗 `[3186, 3563]` s。未启动 evaluator 或 native，没有读取 trace。

{segment_table}

用户规则：若 F04-R5F 主段 yaw RMSE ≤ F04-R5 主段，则两接收机均载波相位解（fixed 或 float）；否则两接收机均 fixed。主评估器 v3 实算 `{r5f}` > `{r5}` deg，因此选定 **两台接收机均 fixed（R5）**。v2 平行值完整保留；这只是 0b 条件计算结果，不解除 0a 冲突。

## 身份与执行状态

{binary_table}

这两项是既有文件哈希的只读核验；不等同于 v3 的五个身份门通过。

{gate_table}

本步骤 native / evaluator / provider 调用均为 **0**，raw payload / trace 读取均为 **0**。未生成 v3 provider、runtime config、NAV 或全量结果。F01 完整 NAV 的封存哈希和 T5a-R BY2 F04 R5 NAV 是后续门的目标；当前没有执行比较。

## 产物和复算

外部原件目录：`{output_alias}`。本目录保存同字节的小型交接副本：

- `V3_01_PREREQUISITES.json`：状态、完整来源 SHA256、代码基线和调用计数；
- `F04_THREE_SEQUENCE_SUMS.csv`：两版三序列求和；
- `SUBSET61_FINITE_COUNTS.csv`、`SUBSET61_F04_R5_COMPARISON.csv`、`SUBSET61_FAILURE_COMPARISON.csv`：有限计数及逐例比较；
- `BY2O_T5AR_SEGMENTS.csv`：两版、四个配置/变体组合、全窗/主段/次段共 24 行。

实现：`scripts/paper_rebuild/v3_prerequisites.py`。运行 `/usr/bin/python3 -B scripts/paper_rebuild/v3_prerequisites.py`，从 ignored local config 解析路径，输出采用独占新建；已存在时拒绝覆盖。脚本只允许在以上起点 HEAD 执行，保证本次前置检查身份明确。无新增科学运行；0a 引用的 61 例退化队列含半合成工况，与 0b 原始三序列证据分别报告。
""".format(head=head, sums_table=md_table([r for r in sums if r["evaluator"] == "v3"], list(sums[0])),
        count_table=md_table(counts, list(counts[0])),
        failure_table=md_table([r for r in failures if r["evaluator"] == "v3"],
            ["case_id", "frozen_terminal", "frozen_yaw_rmse_deg", "R5_failure_classification", "R5_yaw_rmse_deg", "R5_failed_on_frozen_completed"]),
        segment_table=md_table([r for r in segments if r["segment_id"] != "full"],
            ["evaluator_contract", "configuration_id", "variant", "segment_id", "count", "yaw_rmse_deg"]),
        r5f=selected["R5F"], r5=selected["R5"], binary_table=md_table(binary_checks, ["role", "sha256", "status"]),
        gate_table=md_table(gates, ["gate", "status"]), output_alias=OUTPUT_ALIAS)
    artifacts = {
        "F04_THREE_SEQUENCE_SUMS.csv": csv_bytes(sums),
        "SUBSET61_FINITE_COUNTS.csv": csv_bytes(counts),
        "SUBSET61_F04_R5_COMPARISON.csv": csv_bytes(comparisons),
        "SUBSET61_FAILURE_COMPARISON.csv": csv_bytes(failures),
        "BY2O_T5AR_SEGMENTS.csv": csv_bytes(segments),
        "V3_01_PREREQUISITES.md": report.encode(),
    }
    manifest["artifact_sha256"] = {name: digest(payload) for name, payload in artifacts.items()}
    artifacts["V3_01_PREREQUISITES.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    output.mkdir(parents=True, exist_ok=False)
    report_root.mkdir(exist_ok=False)
    for root in (output, report_root):
        for name, payload in artifacts.items():
            with (root / name).open("xb") as handle:
                handle.write(payload)
    print(json.dumps(dict(status=STATUS, selected_rule=selected_rule, selection_values_deg=selected,
                          finite_counts=counts, verified_source_files=len(pins),
                          artifact_count=len(artifacts), native_invocations=0, evaluator_invocations=0), indent=2))


if __name__ == "__main__":
    main()
