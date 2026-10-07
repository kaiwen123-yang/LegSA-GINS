"""Eight synthetic preparation cases; no real observations, file output or native run."""
import hashlib
import importlib.util
from pathlib import Path
import struct

import pytest

SPEC = importlib.util.spec_from_file_location(
    "hv_dependency_prepare",
    Path(__file__).resolve().parents[2] / "scripts/paper_rebuild/carrier_phase/hv_dependency_prepare.py",
)
prepare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare)

FIELDS = (
    "time", "vn", "ve", "std_vn", "std_ve", "valid", "update_flag",
    "go2_source_valid", "a1_heading_valid", "frame_candidate", "prior_policy", "note",
)
HEADER = ",".join(FIELDS).encode()
FRAME = "FLU_to_FRD_Go2_RP_injected_A1_NED"
POLICY = "SENSOR_MODEL_V21_horizontal_weak_prior"


def _row(time, *, support=True, source=True, overrides=None):
    values = dict(time=str(time), vn="+1.230000e+00", ve="-0.000000", std_vn="0.132838",
                  std_ve="1.32838e-1", valid=str(int(source and support)),
                  update_flag=str(source and support), go2_source_valid=str(source),
                  a1_heading_valid=str(support), frame_candidate=FRAME,
                  prior_policy=POLICY, note='"kept, literally"')
    values.update(overrides or {})
    return ",".join(values[k] for k in FIELDS).encode()


def _gnss(times, *, valid=True):
    rows = []
    for time in times:
        values = ["0"] * 18
        values[0], values[13], values[17] = repr(float(time)), "12.345", str(int(valid))
        rows.append(" ".join(values))
    return ("\n".join(rows) + "\n").encode()


def _pin(data, name):
    return dict(path="SYNTHETIC:" + name, sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=len(data))


def _run(hv, gnss, **kwargs):
    return prepare.prepare_bytes(
        hv, gnss, hv_pin=_pin(hv, "HV"), gnss_pin=_pin(gnss, "GNSS"),
        source_pins={"synthetic.py": "a" * 64},
        plan_pin={"path": "SYNTHETIC:PLAN", "sha256": "b" * 64}, **kwargs)


def _metadata(line):
    return line.rstrip(b"\r\n").rsplit(b",", 5)[1:]


def test_lf_blanks_and_original_measurement_text_are_preserved():
    first, second = _row(.25), _row(.75, source=False)
    original = HEADER + b"\n\n" + first + b"\n\n" + second + b"\n\n"
    result, manifest = _run(original, _gnss([0., 1.]), expected_rows=2, expected_helper_calls=1)
    lines = result.splitlines(keepends=True)
    assert lines[1] == lines[3] == lines[5] == b"\n"
    assert lines[2].startswith(first + b",") and lines[4].startswith(second + b",")
    assert _metadata(lines[2])[1] == b"0" and _metadata(lines[4])[1] == b"1"
    assert manifest["supported_rows"] == 2 and manifest["original_valid_rows"] == 1
    assert manifest["prefix_preserved_rows"] == 2
    assert manifest["preserved_bare_lf_blank_lines"] == 3
    assert original == HEADER + b"\n\n" + first + b"\n\n" + second + b"\n\n"
    assert manifest["derived_csv"] == dict(sha256=hashlib.sha256(result).hexdigest(),
                                         size_bytes=len(result))


def test_nonempty_crlf_mixed_endings_and_no_final_newline_are_preserved():
    rows = [_row(.25), _row(.5), _row(.75)]
    original = HEADER + b"\r\n" + rows[0] + b"\r\n" + rows[1] + b"\n" + rows[2]
    result, manifest = _run(original, _gnss([0., 1.]), expected_rows=3, expected_helper_calls=1)
    lines = result.splitlines(keepends=True)
    assert lines[0].endswith(b"\r\n") and lines[1].endswith(b"\r\n")
    assert lines[2].endswith(b"\n") and not lines[3].endswith(b"\n")
    assert all(lines[i+1].startswith(row + b",") for i, row in enumerate(rows))
    assert manifest["line_endings"] == {"\r\n": 2, "\n": 1, "": 1}


def test_unsupported_gap_outside_and_no_endpoints_have_empty_ready():
    original = HEADER + b"\n" + b"\n".join(
        [_row(-.1, support=False), _row(.5, support=False), _row(2.)]) + b"\n"
    result, manifest = _run(original, _gnss([0., 2.]), expected_helper_calls=1)
    metadata = [_metadata(line) for line in result.splitlines()[1:]]
    assert [row[3] for row in metadata] == [b"0", b"0", b"1"]
    assert [row[4] for row in metadata] == [b"", b"", b"2.0"]
    assert manifest["ready_empty_rows"] == 2
    result, manifest = _run(HEADER+b"\n"+_row(.5, support=False)+b"\n",
                            _gnss([0.], valid=False), expected_helper_calls=1)
    assert _metadata(result.splitlines()[1])[3:] == [b"0", b""]
    assert manifest["dependency_kinds"] == {"NO_ENDPOINTS": 1}


def test_bits_row_identity_and_unrounded_endpoint_ready_are_bound():
    original = HEADER+b"\n"+_row(0.)+b"\n"+_row(.25)+b"\n"
    result, manifest = _run(original, _gnss([.00000005, .99999995]), expected_helper_calls=1)
    metadata = [_metadata(line) for line in result.splitlines()[1:]]
    for i, time in enumerate((0., .25)):
        assert metadata[i][:4] == [prepare.SCHEMA.encode(), str(i).encode(),
                                   struct.pack(">d", time).hex().encode(), b"1"]
    assert float(metadata[0][4]) == .00000005
    assert float(metadata[1][4]) == .99999995
    assert manifest["valid_a1_endpoint_rows"] == [0, 1]


def test_existing_flag_conflicts_fail_without_repair():
    for changed in ({"a1_heading_valid": "False"}, {"valid": "0"}, {"update_flag": "False"}):
        original = HEADER+b"\n"+_row(.5, overrides=changed)+b"\n"
        with pytest.raises(ValueError, match="mismatch"):
            _run(original, _gnss([0., 1.]))
        assert original.endswith(_row(.5, overrides=changed)+b"\n")


def test_ambiguous_syntax_column_collision_and_empty_crlf_fail():
    valid = _row(.5)
    cases = [
        HEADER+b",dependency_schema\n"+valid+b",bad\n",
        HEADER+b"\n\r\n"+valid+b"\n",
        HEADER+b"\n \t\n"+valid+b"\n",
        HEADER+b"\n"+valid+b',"unterminated\n',
        HEADER+b"\n"+valid+b",extra\n",
    ]
    for original in cases:
        with pytest.raises(ValueError):
            _run(original, _gnss([0., 1.]))


def test_input_pins_and_round_collapsed_endpoint_identity_fail():
    original = HEADER+b"\n"+_row(.5)+b"\n"
    gnss = _gnss([0., 1.])
    wrong = _pin(original, "HV")
    wrong["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA mismatch"):
        prepare.prepare_bytes(original, gnss, hv_pin=wrong, gnss_pin=_pin(gnss, "GNSS"),
                              source_pins={"source": "a"*64}, plan_pin={"sha256": "b"*64})
    with pytest.raises(ValueError, match="ordered and unique"):
        _run(original, _gnss([0., .0001]))


def test_fixed_chunk_boundary_keeps_global_rows_and_bounded_calls():
    count = prepare.CHUNK_SIZE + 1
    original = HEADER+b"\n"+b"".join(_row(i/10000.)+b"\n" for i in range(count))
    result, manifest = _run(original, _gnss([0., 1.]), expected_rows=count,
                            expected_helper_calls=2)
    lines = result.splitlines()
    assert len(lines) == count + 1
    assert _metadata(lines[1])[1] == b"0"
    assert _metadata(lines[-1])[1] == str(count-1).encode()
    assert manifest["helper_calls"] == 2 and manifest["helper_chunk_size"] == 8192
    assert manifest["prefix_preserved_rows"] == count
