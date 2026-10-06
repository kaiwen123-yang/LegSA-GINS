"""Read-only manuscript/source audit. No solver, evaluator, raw records or Monte Carlo."""
from pathlib import Path
import csv
import hashlib
import json
import math
import re

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/paper_rebuild/TIM_AR_DEVELOPMENT_20261006"
MS = OUT / "manuscript"
OLD = ROOT / "docs/paper_rebuild/TIM_EVIDENCE_20261005/manuscript/manuscript_tim_r3.md"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    old = OLD.read_text()
    new_path = MS / "manuscript_tim_r4.md"
    new = new_path.read_text()
    body, references = new.split("## References\n\n")
    original_entries = [p.strip() for p in old.split("## References\n\n")[1].split("\n\n") if p.strip()]
    numbered = re.findall(r"^\[(\d+)\] (.+)$", references, re.MULTILINE)
    tags = [int(x) for x in re.findall(r"\\tag\{(\d+)\}", new)]
    citations = [int(x) for x in re.findall(r"\[(\d+)\]", body)]
    with (OUT / "evidence-catalog.csv").open(newline="") as f:
        sources = list(csv.DictReader(f))
    with (OUT / "claims-evidence-map.csv").open(newline="") as f:
        claims = list(csv.DictReader(f))
    ids = {x["evidence_id"] for x in sources}
    checks = {
        "original_source_unchanged": sha(OLD) == "3415c6380110b44bd55db36642b7e4f82372853b98be943e64a65bede4007843",
        "original_primary_results_verbatim": old[old.index("### 4.1"):old.index("## 5 Discussion")] in new,
        "original_primary_table_verbatim": old[old.index("**Table 1"):old.index("### 3.2")] in new,
        "reference_facts_preserved": sorted(original_entries) == sorted(x[1] for x in numbered),
        "reference_count_15": len(numbered) == 15,
        "references_in_first_appearance_order": list(dict.fromkeys(citations)) == list(range(1, 16)),
        "all_references_cited": sorted(set(citations)) == list(range(1, 16)),
        "eq_tags_1_to_13": tags == list(range(1, 14)),
        "display_equations_single_line": all(line.startswith("$$") and line.endswith("$$") for line in new.splitlines() if r"\tag{" in line),
        "new_inline_math_tokens_empty": not (set(re.findall(r"(?<!\$)\$([^$\n]+)\$(?!\$)", new)) - set(re.findall(r"(?<!\$)\$([^$\n]+)\$(?!\$)", old))),
        "claim_evidence_ids_all_resolve": all(set(x["evidence_ids"].split(";")) <= ids for x in claims),
        "source_pins_match": all(sha(ROOT / x["repository_path"]) == x["sha256"] for x in sources),
        "csv_line_endings_lf": all(b"\r" not in (OUT / p).read_bytes() for p in ["evidence-catalog.csv", "claims-evidence-map.csv"]),
        "main_excludes_new_carrier_algorithm_claim": "The exploratory alternatives are not components of the V3 filter evaluated here." in body,
        "working_covariance_not_full_joint_model": "they are not supplied by the implemented working covariance" in body,
    }
    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "source_count": len(sources),
        "claim_count": len(claims),
        "source_sha256": sha(OLD),
        "manuscript_sha256": sha(new_path),
        "body_paragraph_blocks": len([p for p in body.split("\n\n") if p.strip()]),
        "budget_example_calculation_mm": {"1_degree": 1000*.35*math.radians(1), "0.5_degree": 1000*.35*math.radians(.5)},
        "execution_environment": "Ubuntu-22.04 WSL",
        "solver_calls": 0,
        "evaluator_calls": 0,
        "raw_or_reference_reads": 0,
        "new_Monte_Carlo_calls": 0,
        "script_sha256": sha(Path(__file__)),
        "supporting_files": {p: sha(MS / p) for p in ["supplement_measurement_and_ar_r4.md", "manuscript_measurement_sections_zh.md", "CITATION_FORMAT_MAP.json"]},
        "scope": "Manuscript preservation, source pins, numeric citation structure and support mapping. Not independent solver reproduction or submission-readiness certification.",
    }
    (MS / "MANUSCRIPT_SOURCE_AUDIT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    prior = json.loads((MS / "MANUSCRIPT_SUPPORT_CHECK.json").read_text())
    prior["repeatable_source_audit"] = "MANUSCRIPT_SOURCE_AUDIT.json"
    prior["repeatable_source_audit_status"] = result["status"]
    prior["manuscript_sha256"] = sha(new_path)
    (MS / "MANUSCRIPT_SUPPORT_CHECK.json").write_text(json.dumps(prior, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"status": result["status"], "failed": [k for k,v in checks.items() if not v], "sources": len(sources), "claims": len(claims)}))
    if not all(checks.values()):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
