from legsa_gins.paper_rebuild.canonical541.matrix_spec import PRESERVED_SOURCE_COMMIT, PRESERVED_SOURCE_SHA256, parameter_provenance_rows


def test_preserved_generator_identity_is_full():
    assert PRESERVED_SOURCE_COMMIT == "2f02424237071444dc54406c6437209b528948ec"
    assert len(PRESERVED_SOURCE_SHA256) == 64
    rows = parameter_provenance_rows()
    assert all(row["fallback_used"] is False for row in rows)
