"""Explicit device allowances never relax protected data write boundaries."""
from pathlib import Path
import pytest
from legsa_gins.paper_rebuild.clean5_sequence.io_audit import audited_open_records, write_scope_audit


def check(tmp_path, path, target=""):
    log = tmp_path / "opens.strace"
    log.write_text(f'42 openat(AT_FDCWD, "{path}", O_RDWR) = 3{target}\n')
    return write_scope_audit(audited_open_records(log, tmp_path), raw_root=tmp_path/"raw",
        allowed_write_roots=[tmp_path/"clean/run"], clean_root=tmp_path/"clean")


@pytest.mark.parametrize("path", ["/dev/null", "/dev/pts/99999"])
def test_explicit_device_exception(tmp_path, path):
    result = check(tmp_path, path)
    assert result["pass"] and result["allowed_device_write_count"] == 1
    assert result["write_outside_run_count"] == 0


def test_kernel_identified_anonymous_pipe(tmp_path):
    result = check(tmp_path, "/proc/self/fd/1", "<pipe:[424242]>")
    assert result["pass"] and result["allowed_anonymous_pipe_write_count"] == 1


def test_regular_file_named_pipe_is_not_exception(tmp_path):
    result = check(tmp_path, str(tmp_path/"pipe:[424242]"))
    assert not result["pass"] and result["allowed_anonymous_pipe_write_count"] == 0


def test_clean_write_outside_run_is_rejected(tmp_path):
    result = check(tmp_path, str(tmp_path/"clean/old-output"))
    assert not result["pass"] and result["clean_root_outside_run_write_count"] == 1


def test_raw_write_even_device_symlink_is_rejected(tmp_path):
    raw = tmp_path/"raw"
    raw.mkdir()
    (raw/"device").symlink_to("/dev/null")
    result = check(tmp_path, str(raw/"device"))
    assert not result["pass"] and result["raw_write_open_count"] == 1
