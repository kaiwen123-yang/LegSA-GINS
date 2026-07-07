from pathlib import Path


def test_da01_code_does_not_reference_forbidden_old_evidence():
    root = Path("src/legsa_gins/da_repro")
    text = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    for forbidden in ["PAPER7R2E", "DA2R2", "PAPER1F", "PAPER0M2"]:
        assert forbidden not in text
