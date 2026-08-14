from pathlib import Path

import yaml

from legsa_gins.paper_rebuild.horizontal_literature.contracts import (
    load_compatibility,
    load_phase1_contract,
    required_manifest_fields,
)


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/paper_rebuild/horizontal_literature"


def test_phase1_contract_is_exactly_ext01_c00_and_physical_transform():
    contract = load_phase1_contract(CONFIG)
    assert contract.methods == ("EXT01_CLAMBDA",)
    assert contract.cases == ("C00",)
    assert contract.baseline_length_m == 0.350
    assert contract.trace_mode == "disabled"
    assert load_compatibility(CONFIG / "CASE_METHOD_COMPATIBILITY_V1.csv")[0]["evaluation_status"] == "NOT_EVALUATED"


def test_literature_identity_hashes_and_no_code_reuse_are_locked():
    doc = yaml.safe_load((CONFIG / "EXTERNAL_METHOD_CONTRACTS_V1.yaml").read_text())
    assert doc["literature"]["P01"]["sha256"] == "e9e19c60d1f651994c878678f530d288a82eb707e26770ce48b449774317aec4"
    assert doc["literature"]["P23"]["sha256"] == "734e256229dada2bb1c10a3f290527681a2d2bfa14b3540dd00473e927848546"
    assert doc["literature"]["P25"]["sha256"] == "11a514002e93bf659ee0245de55030a2d2d614768838dced64de8621670b407a"
    assert doc["literature"]["UBX_ZED_F9T_R02"]["sha256"] == "3d6539cd5ab3efe1254c54e4dba25d17421bfe48ac96e633e602d8d214c13668"
    assert doc["source_policy"] == {
        "papers_are_theory_and_specification_only": True,
        "paper_pdfs_copied_into_repository": False,
        "third_party_code_copied": False,
        "external_runtime_dependency": True,
    }
    assert doc["external_dependency"]["commit"] == (
        "180043ee24b6d2b168f98b64be15f69d50046b1a"
    )
    assert doc["external_dependency"]["license"] == "BSD-2-Clause"
    assert doc["external_dependency"]["upstream_source_patch"] == "none"
    fields = required_manifest_fields(CONFIG)
    assert {"raw_source_hashes", "trace_used_online", "old_runtime_input_count",
            "paired_epoch_count", "failure_row_count"} <= fields
    runtime_files = set(doc["runtime_topology"]["files"].values())
    intermediate_files = set(doc["runtime_topology"]["intermediate_files"].values())
    assert len(runtime_files) == 18
    assert len(intermediate_files) == 6
    assert runtime_files.isdisjoint(intermediate_files)
    assert "01_SHARED_RAW_BACKEND/STOCHASTIC_MODEL_CONTRACT.yaml" in runtime_files
    assert "11_REPORT/PHASE1_STATUS.json" in runtime_files
    assert not any("seal" in value.lower() for value in runtime_files)
