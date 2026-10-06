#!/usr/bin/env python3
"""Check D01 display edits; never import/execute the whole manuscript assembler.

Reads only small local CSV/JSON/Markdown/source files. Writes checks and correction
receipts beside this script. No scientific payload, bootstrap, plot, or process.
"""
import ast
import csv
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / "AGENTS.md").is_file())
PACKAGE = ROOT / "paper_package/gpss_v0"
UNC = ROOT / "docs/paper_rebuild/v3/uncertainty"
BASELINE = json.loads((HERE / "BASELINE.json").read_text())
CHECKS = []


def check(name, passed, detail=""):
    CHECKS.append(dict(check=name, status="PASS" if passed else "FAIL", detail=detail))


def read_csv(path):
    with Path(path).open(newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def locator(path, text):
    hits = [i for i, line in enumerate(path.read_text().splitlines(), 1) if text in line]
    return ";".join(f"<CODE_ROOT>/{path.relative_to(ROOT)}:{i}" for i in hits)


def main():
    for rel, expected in BASELINE["protected"].items():
        check("protected:" + rel, hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == expected)
    ledger = read_csv(PACKAGE / "NUMBER_LEDGER.csv")
    old = {r["claim_id"]: r for r in BASELINE["original_ledger"]}
    current = {r["claim_id"]: r for r in ledger}
    appended = {"N00208", "N00209", "N00210", "N00211"}
    changed = {"N00149", "N00157", "N00199"}
    check("211 unique ledger IDs", len(ledger) == len(current) == 211)
    check("original ID order unchanged", [r["claim_id"] for r in ledger if r["claim_id"] not in appended] == list(old))
    for cid, before in old.items():
        if cid not in changed:
            check("original numeric provenance unchanged:" + cid, all(current[cid][k] == v for k, v in before.items() if k != "quoted_text"))
    manuscript = (PACKAGE / "MANUSCRIPT_GPSS_v0.md").read_text()
    source = (PACKAGE / "manuscript_source.md").read_text()
    for name in ["MANUSCRIPT_GPSS_v0.md", "manuscript_source.md", "SUPPLEMENT_GPSS_v0.md", "supplement_source.md"]:
        text = (PACKAGE / name).read_text()
        check("no original-algorithm byte claim:" + name, "bit-for-bit" not in text)
    check("old rounded displays removed", "30.800" not in manuscript and "-10.50" not in manuscript)
    check("511 in explicit 540 fault domain", "511 common finite pairs from the 540 registered fault cases (excluding C00)" in manuscript)
    check("A1 whole-window nine-case mean", "mean whole-window horizontal RMSE across the nine cases is 30.806 m" in manuscript)
    check("A2 corrected in both paragraphs", manuscript.count("-10.51") == 2 and source.count("[[UA|a2_20_h_delta]]") == 2)
    for cid in changed | appended:
        row = current[cid]
        loc = json.loads(row["source_locator"])
        matches = [x for x in read_csv(ROOT / row["source_path"]) if all(x[k] == v for k, v in loc["where"].items())]
        check("unique direct source:" + cid, len(matches) == 1 and row["check_mode"] == "CSV")
        actual = f"{Decimal(matches[0][loc['column']]):.{loc['display_digits']}f}"
        check("source rounding:" + cid, actual == row["value"], matches[0][loc["column"]] + " -> " + actual)
        check("current paragraph:" + cid, row["quoted_text"] in manuscript)
    low, high = (Decimal(current[c]["value"]) for c in ["N00210", "N00211"])
    check("median interval strictly positive width", high > low and f"{low:.3f}" == f"{high:.3f}")
    verdicts = read_csv(UNC / "UNC_DISTINGUISHABILITY.csv")
    for seq in ["BY2", "BY2H"]:
        row = next(r for r in verdicts if r["sequence"] == seq and r["segment"] == "full" and r["pair_A_minus_B"] == "F04-F02" and r["metric"] == "horizontal")
        check("retained verdict:" + seq, row["verdict"] == "RESOLVED_NEGLIGIBLE")
    for name in ["supplement_source.md", "SUPPLEMENT_GPSS_v0.md"]:
        text = (PACKAGE / name).read_text()
        check("current verdict and median wording:" + name, "retained CSV verdict is `RESOLVED_NEGLIGIBLE`" in text and "equal rounded endpoints do not imply zero width" in text)

    # Extract only selected definitions and in-memory constants, skipping imports,
    # the top-level source-reading loop, main(), and all write paths.
    script_path = PACKAGE / "figures/scripts/assemble_manuscript.py"
    tree = ast.parse(script_path.read_text())
    constants = {"UA_CSV_TOKENS", "DISPLAY_APPENDED_IDS", "UNC_DISPLAY_REPLACEMENTS", "DOCS"}
    functions = {"claim_id", "ua_csvspec", "docspec", "emit", "required_unc", "render"}
    nodes = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in functions) or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in n.targets))]
    specs = json.loads((PACKAGE / "CLAIM_SPECS.json").read_text())
    env = dict(W=ROOT, P=PACKAGE, U=UNC, H=ROOT / "docs/paper_rebuild/hext/HX05", V=Path("<V3>"), re=re, csv=csv, json=json, Decimal=Decimal, SPECS=specs, LEDGER=[], record=lambda p: Path(p), readcsv=read_csv)
    def use_existing_csv_spec(key, *_args):
        if key not in specs:
            raise AssertionError("Unchanged token has no retained specification: " + key)
    env["csvspec"] = use_existing_csv_spec
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(script_path), "exec"), env)
    starts = ["Across the fault cases", "F04's finite-case heading P95", "Family A2 exposes", "Under A1,", "The second claim is supported"]
    for prefix in starts:
        raw = next(line for line in source.splitlines() if line.startswith(prefix))
        before_rows = [r for r in old.values() if r["quoted_text"].startswith(prefix)]
        start = min(int(r["claim_id"][1:]) for r in before_rows)
        env["LEDGER"] = [dict(claim_id=f"N{i:05d}") for i in range(1, start)]
        rendered = env["render"](raw, before_rows[0]["section"]).strip()
        check("isolated paragraph render:" + prefix, rendered in manuscript)
        generated = env["LEDGER"][start - 1:]
        check("isolated old IDs preserved:" + prefix, [r["claim_id"] for r in generated if r["claim_id"] not in appended] == [r["claim_id"] for r in before_rows])
        check("isolated values and units:" + prefix, all(r["value"] == current[r["claim_id"]]["value"] and r["unit"] == current[r["claim_id"]]["unit"] for r in generated))
    for section in ["1", "3"]:
        env["LEDGER"] = []
        text = env["render"]("{{UNC:" + section + "}}", "UNC display test").strip()
        check("UNC overlay regenerates current prose:" + section, text in manuscript and "bit-for-bit" not in text)
    for token in env["UA_CSV_TOKENS"]:
        check("portable new specification:" + token, not Path(specs[token]["path"]).is_absolute())
    fig = (PACKAGE / "figures/scripts/fig06.py").read_text()
    check("Fig06 is existing-case scatter", "ax.scatter(xs,ys" in fig and "ys.append(float(x['horizontal_rmse_m']))" in fig)
    check("Fig06 has no corrected scalar label", all(x not in fig for x in ["30.800", "30.806", "10.50", "10.51"]))
    for rel, expected in BASELINE["protected"].items():
        check("protected after isolated tests:" + rel, hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == expected)

    corrections = []
    for cid in ["N00149", "N00199", "N00157", "N00208", "N00209", "N00210", "N00211"]:
        row = current[cid]; loc = json.loads(row["source_locator"])
        match = next(x for x in read_csv(ROOT / row["source_path"]) if all(x[k] == v for k, v in loc["where"].items()))
        corrections.append(dict(correction_id="D01_" + cid, old_value=old.get(cid, {}).get("value", "NOT_DISPLAYED"), new_value=row["value"], unit=row["unit"], source_path="<CODE_ROOT>/" + row["source_path"], row_key=json.dumps(loc["where"], sort_keys=True), column=loc["column"], source_value=match[loc["column"]], display_digits=loc["display_digits"], new_location=locator(PACKAGE / "MANUSCRIPT_GPSS_v0.md", row["quoted_text"]), ledger_id=cid, change_kind="existing_value_display_or_denominator", check="PASS"))
    for seq in ["BY2", "BY2H"]:
        corrections.append(dict(correction_id="D01_VERDICT_" + seq, old_value="RESOLVED in historical prose", new_value="RESOLVED_NEGLIGIBLE", unit="classification", source_path="<CODE_ROOT>/docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv", row_key=json.dumps(dict(sequence=seq, segment="full", pair_A_minus_B="F04-F02", metric="horizontal")), column="verdict;wording_for_A_vs_B", source_value="RESOLVED_NEGLIGIBLE;comparable (difference below reporting resolution)", display_digits="not_applicable", new_location=locator(PACKAGE / "SUPPLEMENT_GPSS_v0.md", "retained CSV verdict"), ledger_id="not_numeric", change_kind="current_explanation_preserves_historical_source", check="PASS"))
    repro_phrases = ["The retained V3 error-series exports match their recorded hashes;", "The retained V3 error-series exports match their recorded hashes,", "Values are the retained statistics for the evaluated windows"]
    for i, phrase in enumerate(repro_phrases, 1):
        corrections.append(dict(correction_id=f"D01_REPRO_{i}", old_value="bit-for-bit reproducibility claim", new_value=phrase, unit="claim_scope", source_path="<CODE_ROOT>/docs/paper_rebuild/audit_xbpg_20261001/v3_interpretation/RETAINED_SERIES_REVIEW.md", row_key="Completeness and validation scope", column="hash_identity;supported_statistics;limitations", source_value="retained export hashes and supported statistics; no original-input algorithm reproduction", display_digits="not_applicable", new_location=locator(PACKAGE / "MANUSCRIPT_GPSS_v0.md", phrase), ledger_id="not_numeric", change_kind="narrow_claim_to_completed_validation", check="PASS"))
    write_csv(HERE.parent / "DISPLAY_CORRECTIONS.csv", corrections)
    write_csv(HERE / "CHECKS.csv", CHECKS)
    failed = sum(r["status"] != "PASS" for r in CHECKS)
    receipt = dict(status="PASS" if not failed else "FAIL", checks=len(CHECKS), failures=failed, baseline_commit=BASELINE["baseline_commit"], data_mode="mixed_existing_records_display_only", synthetic_data_used=False, semisynthetic_data_used=True, semisynthetic_data_generated=False, original_assembler_imported=False, original_assembler_main_calls=0, original_assembler_controller_calls=0, selected_render_functions_tested_in_memory=True, original_ledger_ids_preserved=207, appended_ledger_ids=sorted(appended), solver_calls=0, provider_calls=0, evaluator_calls=0, bootstrap_calls=0, payload_opens=0, figure_redraws=0, original_performance_csv_writes=0, git_mutations=0, protected_small_files=len(BASELINE["protected"]), targets={rel:hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() for rel in BASELINE["targets"]})
    (HERE / "CHECK_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(dict(status=receipt["status"], checks=len(CHECKS), failures=failed, correction_rows=len(corrections))))
    for row in CHECKS:
        if row["status"] != "PASS":
            print(json.dumps(row))
    return bool(failed)


if __name__ == "__main__":
    raise SystemExit(main())
