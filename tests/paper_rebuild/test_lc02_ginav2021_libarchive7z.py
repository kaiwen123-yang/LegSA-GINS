from __future__ import annotations

import ctypes
import errno
import hashlib
import importlib.util
import inspect
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Sequence

import pytest

from legsa_gins.paper_rebuild.horizontal_literature.ginav2021 import libarchive7z
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021 import (
    transaction as transaction_module,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.constants import (
    OFFICIAL_CONFIG_RELATIVE,
    OFFICIAL_SAMPLE_RELATIVE,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.libarchive7z import (
    ARCHIVE_EOF,
    ARCHIVE_FAILED,
    ARCHIVE_FATAL,
    ARCHIVE_OK,
    ARCHIVE_RETRY,
    ARCHIVE_WARN,
    Libarchive7zBackend,
    Libarchive7zError,
    LibarchiveExtractionError,
    LibarchiveInventoryError,
    LibarchivePreflightError,
    REQUIRED_ABI_SYMBOLS,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.transaction import (
    _classify_sample_archive_members,
    _extract_sample,
    _inventory_sample_archive,
    _run_sample_regression,
    TransactionOptions,
    run_transaction,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.source import (
    AccessLedger,
    SourceIdentityError,
)


REPOSITORY = Path(__file__).resolve().parents[2]
RUNNER = REPOSITORY / "scripts/paper_rebuild/run_lc02_ginav2021.py"


class FakeSymbol:
    def __init__(self, callback: Callable[..., Any]) -> None:
        self.callback = callback
        self.argtypes: list[Any] | None = None
        self.restype: Any = None
        self.calls: list[tuple[Any, ...]] = []

    def __call__(self, *arguments: Any) -> Any:
        self.calls.append(arguments)
        return self.callback(*arguments)


@dataclass
class FakeEntry:
    path: bytes | None
    payload: bytes = b"payload"
    size: int | None = None
    size_is_set: int = 1
    filetype: int = libarchive7z.S_IFREG
    symlink: bytes | None = None
    hardlink: bytes | None = None
    encrypted: int = 0
    sparse_count: int = 0
    blocks: tuple[tuple[int, bytes | None, int | None], ...] | None = None

    @property
    def declared_size(self) -> int:
        return len(self.payload) if self.size is None else self.size


@dataclass
class FakeReader:
    entries: list[FakeEntry]
    header_index: int = -1
    block_index: int = 0
    descriptor: int = -1


def _handle(value: Any) -> int:
    if isinstance(value, ctypes.c_void_p):
        if value.value is None:
            raise AssertionError("null fake handle")
        return int(value.value)
    return int(value)


class FakeLibrary:
    def __init__(
        self,
        entries: Sequence[FakeEntry] = (),
        *,
        readers: Sequence[Sequence[FakeEntry]] | None = None,
        missing_symbol: str | None = None,
        version_number: int = 3_006_000,
        version_string: bytes = b"libarchive 3.6.0",
        setup_status: dict[str, int] | None = None,
        header_failure: tuple[int, int] | None = None,
        skip_status: int = ARCHIVE_OK,
        data_status: int | None = None,
        global_encryption: int = 0,
        filter_count: int = 1,
        filter_code: int = libarchive7z.ARCHIVE_FILTER_NONE,
        archive_format: int = libarchive7z.ARCHIVE_FORMAT_7ZIP,
        close_status: int = ARCHIVE_OK,
        free_status: int = ARCHIVE_OK,
        preflight_free_status: int = ARCHIVE_OK,
        null_reader: bool = False,
    ) -> None:
        self.entry_sets = [list(item) for item in readers] if readers is not None else [list(entries)]
        self.version_number = version_number
        self.version_string = version_string
        self.setup_status = dict(setup_status or {})
        self.header_failure = header_failure
        self.skip_status = skip_status
        self.data_status = data_status
        self.global_encryption = global_encryption
        self.filter_count = filter_count
        self.filter_code = filter_code
        self.archive_format_code = archive_format
        self.close_status = close_status
        self.free_status = free_status
        self.preflight_free_status = preflight_free_status
        self.null_reader = null_reader
        self.readers: dict[int, FakeReader] = {}
        self.entries: dict[int, FakeEntry] = {}
        self.buffers: list[ctypes.Array[Any]] = []
        self.next_reader = 100
        self.next_entry = 10_000
        self.reader_creation_count = 0
        self.skip_paths: list[bytes | None] = []
        self.data_paths: list[bytes | None] = []
        self.close_fd_was_open: list[bool] = []
        self.free_fd_was_open: list[bool] = []
        self.last_descriptor = -1
        self.loader_arguments: tuple[str, int, bool] | None = None

        callbacks: dict[str, Callable[..., Any]] = {
            "archive_version_number": lambda: self.version_number,
            "archive_version_string": lambda: self.version_string,
            "archive_version_details": lambda: b"libarchive 3.6.0 fake-details",
            "archive_read_new": self._read_new,
            "archive_read_support_filter_none": lambda archive: self._status(
                "archive_read_support_filter_none"
            ),
            "archive_read_support_format_7zip": lambda archive: self._status(
                "archive_read_support_format_7zip"
            ),
            "archive_read_open_fd": self._open_fd,
            "archive_read_next_header": self._next_header,
            "archive_read_data_skip": self._data_skip,
            "archive_read_data_block": self._data_block,
            "archive_read_has_encrypted_entries": lambda archive: self.global_encryption,
            "archive_filter_count": lambda archive: self.filter_count,
            "archive_filter_code": lambda archive, index: self.filter_code,
            "archive_format": lambda archive: self.archive_format_code,
            "archive_errno": lambda archive: 5,
            "archive_error_string": lambda archive: b"scripted fake failure",
            "archive_read_close": self._close,
            "archive_read_free": self._free,
            "archive_entry_pathname_utf8": lambda entry: self._entry(entry).path,
            "archive_entry_size_is_set": lambda entry: self._entry(entry).size_is_set,
            "archive_entry_size": lambda entry: self._entry(entry).declared_size,
            "archive_entry_filetype": lambda entry: self._entry(entry).filetype,
            "archive_entry_symlink_utf8": lambda entry: self._entry(entry).symlink,
            "archive_entry_hardlink_utf8": lambda entry: self._entry(entry).hardlink,
            "archive_entry_is_encrypted": lambda entry: self._entry(entry).encrypted,
            "archive_entry_sparse_reset": lambda entry: self._entry(entry).sparse_count,
        }
        for name, callback in callbacks.items():
            if name != missing_symbol:
                setattr(self, name, FakeSymbol(callback))

    def loader(self, path: str, *, mode: int, use_errno: bool) -> "FakeLibrary":
        self.loader_arguments = (path, mode, use_errno)
        return self

    def _status(self, name: str) -> int:
        return self.setup_status.get(name, ARCHIVE_OK)

    def _read_new(self) -> int | None:
        if self.null_reader:
            return None
        handle = self.next_reader
        self.next_reader += 1
        self.readers[handle] = FakeReader([])
        return handle

    def _reader(self, archive: Any) -> FakeReader:
        return self.readers[_handle(archive)]

    def _entry(self, entry: Any) -> FakeEntry:
        return self.entries[_handle(entry)]

    def _open_fd(self, archive: Any, descriptor: int, block_size: int) -> int:
        reader = self._reader(archive)
        index = min(self.reader_creation_count, len(self.entry_sets) - 1)
        self.reader_creation_count += 1
        reader.entries = list(self.entry_sets[index])
        reader.descriptor = descriptor
        self.last_descriptor = descriptor
        return self._status("archive_read_open_fd")

    def _next_header(self, archive: Any, entry_pointer: Any) -> int:
        reader = self._reader(archive)
        next_index = reader.header_index + 1
        if self.header_failure is not None and next_index == self.header_failure[0]:
            return self.header_failure[1]
        if next_index >= len(reader.entries):
            return ARCHIVE_EOF
        reader.header_index = next_index
        reader.block_index = 0
        entry_handle = self.next_entry
        self.next_entry += 1
        self.entries[entry_handle] = reader.entries[next_index]
        entry_pointer._obj.value = entry_handle
        return ARCHIVE_OK

    def _current_entry(self, archive: Any) -> FakeEntry:
        reader = self._reader(archive)
        return reader.entries[reader.header_index]

    def _data_skip(self, archive: Any) -> int:
        self.skip_paths.append(self._current_entry(archive).path)
        return self.skip_status

    def _data_block(
        self, archive: Any, buffer_pointer: Any, size_pointer: Any, offset_pointer: Any
    ) -> int:
        entry = self._current_entry(archive)
        self.data_paths.append(entry.path)
        if self.data_status is not None:
            return self.data_status
        reader = self._reader(archive)
        blocks = entry.blocks
        if blocks is None:
            blocks = ((0, entry.payload, None),) if entry.payload else ()
        if reader.block_index >= len(blocks):
            return ARCHIVE_EOF
        offset, content, size_override = blocks[reader.block_index]
        reader.block_index += 1
        if content is None:
            buffer_pointer._obj.value = None
            size_pointer._obj.value = 1 if size_override is None else size_override
        else:
            buffer = ctypes.create_string_buffer(content)
            self.buffers.append(buffer)
            buffer_pointer._obj.value = ctypes.addressof(buffer)
            size_pointer._obj.value = len(content) if size_override is None else size_override
        offset_pointer._obj.value = offset
        return ARCHIVE_OK

    def _descriptor_open(self, archive: Any) -> bool:
        descriptor = self._reader(archive).descriptor
        try:
            os.fstat(descriptor)
            return True
        except OSError:
            return False

    def _close(self, archive: Any) -> int:
        self.close_fd_was_open.append(self._descriptor_open(archive))
        return self.close_status

    def _free(self, archive: Any) -> int:
        reader = self._reader(archive)
        if reader.descriptor >= 0:
            self.free_fd_was_open.append(self._descriptor_open(archive))
            return self.free_status
        return self.preflight_free_status


def _backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake: FakeLibrary,
) -> tuple[Libarchive7zBackend, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    library = tmp_path / "libarchive.so.13.6.0"
    library.write_bytes(b"pinned-fake-libarchive-for-ABI-tests")
    digest = hashlib.sha256(library.read_bytes()).hexdigest()
    monkeypatch.setattr(libarchive7z, "PINNED_LIBARCHIVE_SHA256", digest)
    return Libarchive7zBackend(library, _loader=fake.loader), library


def _archive(tmp_path: Path) -> Path:
    path = tmp_path / "official_sample.7z"
    path.write_bytes(b"fake-archive-container-bytes")
    return path


def _official_entries() -> list[FakeEntry]:
    return [
        FakeEntry(b"data/cpt.19o", b"observation"),
        FakeEntry(b"data/cpt.19c", b"navigation"),
        FakeEntry(b"data/cpt_imu.csv", b"imu"),
        FakeEntry(b"data/cpt_pva_ref.mat", b"forbidden-reference"),
        FakeEntry(b"data/cpt.ubx", b"excluded-ubx"),
    ]


def _official_entries_with_directory(
    *, trailing_slash: bool = True,
) -> list[FakeEntry]:
    directory = b"data_cpt/" if trailing_slash else b"data_cpt"
    return [
        FakeEntry(directory, b"", size=0, filetype=libarchive7z.S_IFDIR),
        FakeEntry(b"data_cpt/cpt.19o", b"observation"),
        FakeEntry(b"data_cpt/cpt.19c", b"navigation"),
        FakeEntry(b"data_cpt/cpt_imu.csv", b"imu"),
        FakeEntry(b"data_cpt/cpt_pva_ref.mat", b"forbidden-reference"),
        FakeEntry(b"data_cpt/cpt.ubx", b"excluded-ubx"),
    ]


def _classified_inventory(backend: Libarchive7zBackend, archive: Path) -> dict[str, Any]:
    raw = backend.inventory(archive)
    classified = _classify_sample_archive_members(raw["members"])
    result = {**raw, **classified}
    result["frozen_inventory_binding_sha256"] = (
        libarchive7z.frozen_inventory_binding_sha256(result)
    )
    return result


def test_fake_abi_binds_every_symbol_and_records_pinned_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLibrary(_official_entries())
    backend, library = _backend(tmp_path, monkeypatch, fake)
    assert backend.identity["archive_version_number"] == 3_006_000
    assert backend.identity["archive_version_string"] == "libarchive 3.6.0"
    assert backend.identity["library_sha256"] == hashlib.sha256(
        library.read_bytes()
    ).hexdigest()
    assert backend.identity["install_performed"] is False
    assert backend.identity["subprocess_used"] is False
    assert fake.loader_arguments is not None
    assert fake.loader_arguments[2] is True
    for name in REQUIRED_ABI_SYMBOLS:
        symbol = getattr(fake, name)
        expected_argtypes, expected_restype = libarchive7z._ABI_SIGNATURES[name]
        assert symbol.argtypes == list(expected_argtypes), name
        assert symbol.restype is expected_restype, name


@pytest.mark.parametrize(
    ("missing", "version_number", "version_string", "message"),
    (
        ("archive_read_data_block", 3_006_000, b"libarchive 3.6.0", "missing"),
        (None, 3_005_000, b"libarchive 3.6.0", "ABI version mismatch"),
        (None, 3_006_000, b"libarchive 3.6.1", "runtime version mismatch"),
    ),
)
def test_preflight_rejects_missing_symbol_or_version_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    missing: str | None,
    version_number: int,
    version_string: bytes,
    message: str,
) -> None:
    fake = FakeLibrary(
        missing_symbol=missing, version_number=version_number,
        version_string=version_string,
    )
    library = tmp_path / "libarchive.so.13.6.0"
    library.write_bytes(b"fake")
    monkeypatch.setattr(
        libarchive7z, "PINNED_LIBARCHIVE_SHA256",
        hashlib.sha256(library.read_bytes()).hexdigest(),
    )
    with pytest.raises(LibarchivePreflightError, match=message):
        Libarchive7zBackend(library, _loader=fake.loader)


def test_preflight_requires_absolute_regular_resolved_non_symlink_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLibrary()
    directory = tmp_path / "directory"
    directory.mkdir()
    with pytest.raises(LibarchivePreflightError, match="regular file"):
        Libarchive7zBackend(directory, _loader=fake.loader)
    target = tmp_path / "target.so"
    target.write_bytes(b"target")
    link = tmp_path / "link.so"
    link.symlink_to(target)
    with pytest.raises(LibarchivePreflightError, match="symlink"):
        Libarchive7zBackend(link, _loader=fake.loader)
    with pytest.raises(LibarchivePreflightError, match="absolute"):
        Libarchive7zBackend(Path("relative.so"), _loader=fake.loader)


def test_preflight_rejects_hash_mismatch_null_reader_and_non_ok_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    library = tmp_path / "libarchive.so.13.6.0"
    library.write_bytes(b"not-the-pinned-file")
    with pytest.raises(LibarchivePreflightError, match="SHA256"):
        Libarchive7zBackend(library, _loader=FakeLibrary().loader)

    with pytest.raises(LibarchivePreflightError, match="null"):
        _backend(tmp_path / "null", monkeypatch, FakeLibrary(null_reader=True))
    with pytest.raises(LibarchivePreflightError, match="archive_read_free"):
        _backend(
            tmp_path / "free", monkeypatch,
            FakeLibrary(preflight_free_status=ARCHIVE_WARN),
        )


def test_inventory_is_next_header_only_and_keeps_fd_ownership_and_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLibrary(_official_entries())
    backend, library = _backend(tmp_path, monkeypatch, fake)
    archive = _archive(tmp_path)
    archive_before = hashlib.sha256(archive.read_bytes()).hexdigest()
    library_before = hashlib.sha256(library.read_bytes()).hexdigest()
    inventory = backend.inventory(archive)
    assert inventory["inventory_operation"] == "libarchive_next_header_only"
    assert inventory["payload_api_calls"] == 0
    assert inventory["api_call_counts"].get("archive_read_data_block", 0) == 0
    assert inventory["api_call_counts"].get("archive_read_data_skip", 0) == 0
    assert all(item["header_metadata_sha256"] for item in inventory["members"])
    assert {item["size_contract"] for item in inventory["members"]} == {
        "REQUIRED_SET_NONNEGATIVE_WITHIN_CAP_FOR_REGULAR_FILE"
    }
    assert fake.close_fd_was_open == [True]
    assert fake.free_fd_was_open == [True]
    with pytest.raises(OSError) as closed:
        os.fstat(fake.last_descriptor)
    assert closed.value.errno == errno.EBADF
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == archive_before
    assert hashlib.sha256(library.read_bytes()).hexdigest() == library_before


def test_transaction_inventory_records_backend_and_selected_excluded_hash_ledgers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLibrary(_official_entries())
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    archive = _archive(tmp_path)
    inventory = _inventory_sample_archive(archive, backend, AccessLedger())
    assert inventory["archive_backend"]["library_sha256"]
    assert inventory["archive_sha256"] == hashlib.sha256(
        archive.read_bytes()
    ).hexdigest()
    ledger = {item["path"]: item for item in inventory["member_inventory_ledger"]}
    assert ledger["data/cpt.19o"]["role"] == "selected_observation"
    assert ledger["data/cpt_pva_ref.mat"]["role"] == "excluded_reference"
    assert ledger["data/cpt.ubx"]["role"] == "excluded_ubx"
    assert all(item["header_metadata_sha256"] for item in ledger.values())
    assert inventory["reference_member_payload_read_calls"] == 0
    assert inventory["ubx_member_payload_read_calls"] == 0
    assert inventory["frozen_inventory_binding_sha256"] == (
        libarchive7z.frozen_inventory_binding_sha256(inventory)
    )


@pytest.mark.parametrize("status", (ARCHIVE_RETRY, ARCHIVE_WARN, ARCHIVE_FAILED, ARCHIVE_FATAL))
@pytest.mark.parametrize(
    "operation",
    (
        "archive_read_support_filter_none",
        "archive_read_support_format_7zip",
        "archive_read_open_fd",
    ),
)
def test_setup_accepts_only_archive_ok(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    operation: str,
) -> None:
    fake = FakeLibrary(
        _official_entries(), setup_status={operation: status}
    )
    if operation != "archive_read_open_fd":
        with pytest.raises(LibarchivePreflightError, match="non-OK"):
            _backend(tmp_path, monkeypatch, fake)
        assert len(fake.archive_read_free.calls) == 1
    else:
        backend, _ = _backend(tmp_path, monkeypatch, fake)
        with pytest.raises(LibarchiveInventoryError, match="non-OK"):
            backend.inventory(_archive(tmp_path))
        assert len(fake.archive_read_free.calls) == 2
        assert len(fake.archive_read_close.calls) == 1


@pytest.mark.parametrize("status", (ARCHIVE_RETRY, ARCHIVE_WARN, ARCHIVE_FAILED, ARCHIVE_FATAL))
def test_header_iteration_accepts_only_ok_or_terminal_eof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    fake = FakeLibrary(_official_entries(), header_failure=(0, status))
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    with pytest.raises(LibarchiveInventoryError, match="non-OK/non-EOF"):
        backend.inventory(_archive(tmp_path))


@pytest.mark.parametrize("encrypted_state", (-2, -1, 1, 2))
def test_global_encryption_unknown_or_present_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, encrypted_state: int
) -> None:
    fake = FakeLibrary(_official_entries(), global_encryption=encrypted_state)
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    with pytest.raises(LibarchiveInventoryError, match="encryption state"):
        backend.inventory(_archive(tmp_path))


@pytest.mark.parametrize(
    "kwargs",
    (
        {"filter_count": 2},
        {"filter_code": 1},
        {"archive_format": 0x10000},
    ),
)
def test_reader_accepts_only_filter_none_and_7zip_format(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kwargs: dict[str, int],
) -> None:
    fake = FakeLibrary(_official_entries(), **kwargs)
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    with pytest.raises(LibarchiveInventoryError, match="filter|format"):
        backend.inventory(_archive(tmp_path))


@pytest.mark.parametrize(
    "path",
    (
        None,
        b"",
        b"/absolute",
        b"../escape",
        b"data/../escape",
        b"data//file",
        b"data/./file",
        b"data\\file",
        b"C" + b":/drive",
        b"data/\x01control",
        b"data/\xffinvalid",
        "data/e\u0301.txt".encode("utf-8"),
    ),
)
def test_inventory_rejects_unsafe_non_utf8_or_non_nfc_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path: bytes | None,
) -> None:
    fake = FakeLibrary([FakeEntry(path)])
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    with pytest.raises(Libarchive7zError):
        backend.inventory(_archive(tmp_path))


def test_canonical_directory_single_trailing_slash_is_normalized_and_extractable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLibrary(_official_entries_with_directory())
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    archive = _archive(tmp_path)
    inventory = _classified_inventory(backend, archive)
    directory = inventory["members"][0]
    assert directory["path"] == "data_cpt"
    assert directory["archive_pathname_utf8"] == "data_cpt/"
    assert directory["kind"] == "directory"
    assert directory["directory"] is True
    assert directory["bytes"] == 0
    assert directory["size_is_set"] is True
    assert directory["size_contract"] == "NOT_APPLICABLE_FOR_DIRECTORY"
    assert directory["directory_pathname_trailing_slash"] is True
    assert fake.data_paths == []
    result = backend.extract_selected(archive, tmp_path / "selected", inventory)
    assert result["extracted_members"] == [
        "data_cpt/cpt.19c",
        "data_cpt/cpt.19o",
        "data_cpt/cpt_imu.csv",
    ]
    assert fake.skip_paths.count(b"data_cpt/") == 1
    assert b"data_cpt/" not in fake.data_paths
    assert (tmp_path / "selected/data_cpt").is_dir()
    assert not (tmp_path / "selected/data_cpt/cpt_pva_ref.mat").exists()


def test_unset_size_directory_inventory_and_extraction_are_valid_without_payload_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entries = _official_entries_with_directory()
    entries[0] = FakeEntry(
        b"data_cpt/", b"directory-payload-must-not-be-read", size_is_set=0,
        filetype=libarchive7z.S_IFDIR,
    )
    fake = FakeLibrary(entries)
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    archive = _archive(tmp_path)
    inventory = _classified_inventory(backend, archive)
    directory = inventory["members"][0]
    assert directory["bytes"] == 0
    assert directory["size_is_set"] is False
    assert directory["size_contract"] == "NOT_APPLICABLE_FOR_DIRECTORY"
    assert len(fake.archive_entry_size.calls) == 5
    assert fake.data_paths == []

    result = backend.extract_selected(archive, tmp_path / "selected-unset", inventory)
    assert result["extracted_members"] == [
        "data_cpt/cpt.19c",
        "data_cpt/cpt.19o",
        "data_cpt/cpt_imu.csv",
    ]
    assert len(fake.archive_entry_size.calls) == 10
    assert fake.skip_paths.count(b"data_cpt/") == 1
    assert b"data_cpt/" not in fake.data_paths
    assert (tmp_path / "selected-unset/data_cpt").is_dir()


def test_truthy_noncanonical_size_state_is_normalized_for_regular_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLibrary([FakeEntry(b"data/file", b"payload", size_is_set=64)])
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    member = backend.inventory(_archive(tmp_path))["members"][0]
    assert member["bytes"] == len(b"payload")
    assert member["size_is_set"] is True
    assert member["size_contract"] == (
        "REQUIRED_SET_NONNEGATIVE_WITHIN_CAP_FOR_REGULAR_FILE"
    )


def test_truthy_noncanonical_size_state_is_valid_for_zero_size_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLibrary(
        [
            FakeEntry(
                b"data/", b"", size=0, size_is_set=64,
                filetype=libarchive7z.S_IFDIR,
            )
        ]
    )
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    member = backend.inventory(_archive(tmp_path))["members"][0]
    assert member["bytes"] == 0
    assert member["size_is_set"] is True
    assert member["size_contract"] == "NOT_APPLICABLE_FOR_DIRECTORY"


def test_directory_with_set_nonzero_size_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLibrary(
        [
            FakeEntry(
                b"data/", b"ignored", size=1, size_is_set=64,
                filetype=libarchive7z.S_IFDIR,
            )
        ]
    )
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    with pytest.raises(LibarchiveInventoryError, match="directory has nonzero size"):
        backend.inventory(_archive(tmp_path))


def test_directory_without_trailing_slash_remains_canonical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLibrary(_official_entries_with_directory(trailing_slash=False))
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    inventory = backend.inventory(_archive(tmp_path))
    directory = inventory["members"][0]
    assert directory["path"] == "data_cpt"
    assert directory["archive_pathname_utf8"] == "data_cpt"
    assert directory["directory_pathname_trailing_slash"] is False


@pytest.mark.parametrize("filetype", (libarchive7z.S_IFREG, stat.S_IFIFO))
def test_regular_or_special_file_trailing_slash_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, filetype: int
) -> None:
    fake = FakeLibrary([FakeEntry(b"data/file/", filetype=filetype)])
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    with pytest.raises(LibarchiveInventoryError, match="trailing slash"):
        backend.inventory(_archive(tmp_path))


@pytest.mark.parametrize(
    "path",
    (
        None,
        b"",
        b"/",
        b"//",
        b"data_cpt//",
        b"data//nested/",
        b"/absolute/",
        b"../escape/",
        b"data/../escape/",
        b"data/./",
        b"data\\dir/",
        b"\\\\server\\share/",
        b"C" + b":/drive/",
        b"data/\x01control/",
        b"data/\x00nul/",
        b"data/\xffinvalid/",
        "data/e\u0301/".encode("utf-8"),
    ),
)
def test_directory_trailing_slash_keeps_all_path_guards(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path: bytes | None,
) -> None:
    fake = FakeLibrary(
        [FakeEntry(path, b"", size=0, filetype=libarchive7z.S_IFDIR)]
    )
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    with pytest.raises(Libarchive7zError):
        backend.inventory(_archive(tmp_path))


def test_directory_trailing_slash_form_is_part_of_frozen_header_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with_slash = _official_entries_with_directory(trailing_slash=True)
    without_slash = _official_entries_with_directory(trailing_slash=False)
    fake = FakeLibrary(readers=[with_slash, without_slash])
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    archive = _archive(tmp_path)
    inventory = _classified_inventory(backend, archive)
    with pytest.raises(LibarchiveExtractionError, match="changed from inventory"):
        backend.extract_selected(archive, tmp_path / "header-drift", inventory)


@pytest.mark.parametrize(
    "entries",
    (
        [
            FakeEntry(b"data/", b"", size=0, filetype=libarchive7z.S_IFDIR),
            FakeEntry(b"data", b"", size=0, filetype=libarchive7z.S_IFDIR),
        ],
        [
            FakeEntry(b"data/", b"", size=0, filetype=libarchive7z.S_IFDIR),
            FakeEntry(b"data", b"payload", filetype=libarchive7z.S_IFREG),
        ],
        [
            FakeEntry(b"data", b"payload", filetype=libarchive7z.S_IFREG),
            FakeEntry(b"data/", b"", size=0, filetype=libarchive7z.S_IFDIR),
        ],
    ),
)
def test_normalized_directory_name_collisions_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entries: list[FakeEntry],
) -> None:
    fake = FakeLibrary(entries)
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    with pytest.raises(LibarchiveInventoryError, match="collid|duplicate"):
        backend.inventory(_archive(tmp_path))


@pytest.mark.parametrize(
    "entries",
    (
        [FakeEntry(b"data/A"), FakeEntry(b"data/a")],
        [FakeEntry(b"data/file"), FakeEntry(b"data/file/child")],
        [FakeEntry("data/stra\u00dfe".encode()), FakeEntry(b"data/STRASSE")],
    ),
)
def test_inventory_rejects_casefold_and_prefix_collisions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entries: list[FakeEntry],
) -> None:
    fake = FakeLibrary(entries)
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    with pytest.raises(LibarchiveInventoryError, match="collid|prefix"):
        backend.inventory(_archive(tmp_path))


@pytest.mark.parametrize(
    ("entry", "message"),
    (
        (FakeEntry(b"data/link", symlink=b"target"), "symlink"),
        (FakeEntry(b"data/hard", hardlink=b"target"), "hardlink"),
        (FakeEntry(b"data/encrypted", encrypted=1), "encryption"),
        (FakeEntry(b"data/unknown-encryption", encrypted=-1), "encryption"),
        (FakeEntry(b"data/sparse", sparse_count=1), "sparse"),
        (FakeEntry(b"data/sparse-unknown", sparse_count=-1), "sparse"),
        (FakeEntry(b"data/special", filetype=stat.S_IFIFO), "special"),
        (FakeEntry(b"data/unset", size_is_set=0), "unset"),
        (FakeEntry(b"data/negative", size=-1), "size"),
        (
            FakeEntry(b"data/oversize", size=libarchive7z.MAX_ARCHIVE_MEMBER_BYTES + 1),
            "cap",
        ),
    ),
)
def test_inventory_rejects_links_encryption_sparse_special_and_invalid_sizes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry: FakeEntry,
    message: str,
) -> None:
    fake = FakeLibrary([entry])
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    with pytest.raises(LibarchiveInventoryError, match=message):
        backend.inventory(_archive(tmp_path))


def test_inventory_enforces_member_count_and_aggregate_size_caps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLibrary([FakeEntry(b"a", b"a"), FakeEntry(b"b", b"b")])
    backend, _ = _backend(tmp_path / "count", monkeypatch, fake)
    monkeypatch.setattr(libarchive7z, "MAX_ARCHIVE_MEMBER_COUNT", 1)
    with pytest.raises(LibarchiveInventoryError, match="member-count"):
        backend.inventory(_archive(tmp_path / "count"))

    fake_total = FakeLibrary([FakeEntry(b"a", b"aa"), FakeEntry(b"b", b"bb")])
    backend_total, _ = _backend(tmp_path / "total", monkeypatch, fake_total)
    monkeypatch.setattr(libarchive7z, "MAX_ARCHIVE_MEMBER_COUNT", 100_000)
    monkeypatch.setattr(libarchive7z, "MAX_ARCHIVE_TOTAL_BYTES", 3)
    with pytest.raises(LibarchiveInventoryError, match="total uncompressed"):
        backend_total.inventory(_archive(tmp_path / "total"))


def test_exact_extraction_streams_only_obs_nav_imu_and_hashes_readback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLibrary(_official_entries())
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    archive = _archive(tmp_path)
    inventory = _classified_inventory(backend, archive)
    destination = tmp_path / "selected"
    result = backend.extract_selected(archive, destination, inventory)
    assert result["extracted_members"] == [
        "data/cpt.19c", "data/cpt.19o", "data/cpt_imu.csv"
    ]
    assert (destination / "data/cpt.19o").read_bytes() == b"observation"
    assert (destination / "data/cpt.19c").read_bytes() == b"navigation"
    assert (destination / "data/cpt_imu.csv").read_bytes() == b"imu"
    assert not (destination / "data/cpt_pva_ref.mat").exists()
    assert not (destination / "data/cpt.ubx").exists()
    assert result["reference_member_payload_read_calls"] == 0
    assert result["ubx_member_payload_read_calls"] == 0
    assert fake.skip_paths.count(b"data/cpt_pva_ref.mat") == 1
    assert fake.skip_paths.count(b"data/cpt.ubx") == 1
    assert set(fake.data_paths) == {
        b"data/cpt.19o", b"data/cpt.19c", b"data/cpt_imu.csv"
    }
    assert all(item["sha256"] for item in result["selected_member_ledger"])
    assert result["fresh_archive_identity_match_before_payload"] is True
    assert result["selected_payload_started_only_after_identity_match"] is True
    assert result["frozen_inventory_binding_sha256"] == inventory[
        "frozen_inventory_binding_sha256"
    ]


def test_two_pristine_extractions_share_one_frozen_inventory_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLibrary(_official_entries())
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    archive = _archive(tmp_path)
    inventory = _classified_inventory(backend, archive)
    first = backend.extract_selected(archive, tmp_path / "pristine-1", inventory)
    second = backend.extract_selected(archive, tmp_path / "pristine-2", inventory)
    assert first["frozen_inventory_binding_sha256"] == inventory[
        "frozen_inventory_binding_sha256"
    ]
    assert second["frozen_inventory_binding_sha256"] == inventory[
        "frozen_inventory_binding_sha256"
    ]


def test_payload_container_drift_fails_before_header_or_payload_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLibrary(_official_entries())
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    archive = _archive(tmp_path)
    inventory = _classified_inventory(backend, archive)
    original = archive.read_bytes()
    archive.write_bytes(bytes((original[0] ^ 1,)) + original[1:])
    assert archive.stat().st_size == inventory["archive_identity_before"]["bytes"]
    header_calls_before = len(fake.archive_read_next_header.calls)
    payload_calls_before = len(fake.archive_read_data_block.calls)
    destination = tmp_path / "container-drift"
    with pytest.raises(LibarchiveExtractionError, match="before payload"):
        backend.extract_selected(archive, destination, inventory)
    assert len(fake.archive_read_next_header.calls) == header_calls_before
    assert len(fake.archive_read_data_block.calls) == payload_calls_before
    assert fake.data_paths == []
    assert not destination.exists()


def test_partial_output_writes_are_fully_conserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLibrary(_official_entries())
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    archive = _archive(tmp_path)
    inventory = _classified_inventory(backend, archive)
    real_write = libarchive7z.os.write
    calls = 0

    def partial_write(descriptor: int, data: Any) -> int:
        nonlocal calls
        calls += 1
        limited = data[: max(1, len(data) // 2)]
        return real_write(descriptor, limited)

    monkeypatch.setattr(libarchive7z.os, "write", partial_write)
    backend.extract_selected(archive, tmp_path / "partial-writes", inventory)
    assert calls > 3


@pytest.mark.parametrize(
    ("blocks", "declared_size", "message"),
    (
        (((0, None, 1),), 1, "null/empty"),
        (((0, b"", 0),), 0, "null/empty"),
        (((1, b"a", None),), 1, "contiguous"),
        (((0, b"ab", None), (1, b"c", None)), 3, "contiguous"),
        (((0, b"ab", None),), 1, "exceeds"),
        (((0, b"a", None),), 2, "differs"),
    ),
)
def test_payload_blocks_require_nonnull_contiguous_exact_declared_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    blocks: tuple[tuple[int, bytes | None, int | None], ...],
    declared_size: int,
    message: str,
) -> None:
    entries = _official_entries()
    entries[0] = FakeEntry(
        b"data/cpt.19o", b"x" * declared_size,
        size=declared_size, blocks=blocks,
    )
    fake = FakeLibrary(entries)
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    archive = _archive(tmp_path)
    inventory = _classified_inventory(backend, archive)
    with pytest.raises(LibarchiveExtractionError, match=message):
        backend.extract_selected(archive, tmp_path / "bad-blocks", inventory)


@pytest.mark.parametrize("status", (ARCHIVE_RETRY, ARCHIVE_WARN, ARCHIVE_FAILED, ARCHIVE_FATAL))
def test_data_block_and_skip_accept_only_ok_or_expected_eof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    archive = _archive(tmp_path)
    fake_data = FakeLibrary(_official_entries(), data_status=status)
    backend_data, _ = _backend(tmp_path / "data", monkeypatch, fake_data)
    inventory = _classified_inventory(backend_data, archive)
    with pytest.raises(LibarchiveExtractionError, match="non-OK/non-EOF"):
        backend_data.extract_selected(archive, tmp_path / "data-fail", inventory)

    fake_skip = FakeLibrary(_official_entries(), skip_status=status)
    backend_skip, _ = _backend(tmp_path / "skip", monkeypatch, fake_skip)
    inventory_skip = _classified_inventory(backend_skip, archive)
    with pytest.raises(LibarchiveExtractionError, match="non-OK"):
        backend_skip.extract_selected(archive, tmp_path / "skip-fail", inventory_skip)


def test_second_reader_header_drift_and_existing_destination_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = _official_entries()
    changed = _official_entries()
    changed[0] = FakeEntry(b"data/cpt.19o", b"changed-size")
    fake = FakeLibrary(readers=[original, changed])
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    archive = _archive(tmp_path)
    inventory = _classified_inventory(backend, archive)
    with pytest.raises(LibarchiveExtractionError, match="changed from inventory"):
        backend.extract_selected(archive, tmp_path / "drift", inventory)

    destination = tmp_path / "exists"
    destination.mkdir()
    with pytest.raises(LibarchiveExtractionError, match="already exists"):
        backend.extract_selected(archive, destination, inventory)


def test_symlinked_destination_parent_is_rejected_without_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLibrary(_official_entries())
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    archive = _archive(tmp_path)
    inventory = _classified_inventory(backend, archive)
    real = tmp_path / "real-parent"
    real.mkdir()
    link = tmp_path / "linked-parent"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises((OSError, LibarchiveExtractionError)):
        backend.extract_selected(archive, link / "escape", inventory)
    assert not (real / "escape").exists()


@pytest.mark.parametrize("cleanup", ("close", "free"))
def test_non_ok_cleanup_status_fails_and_does_not_leak_fd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cleanup: str
) -> None:
    fake = FakeLibrary(
        _official_entries(),
        close_status=ARCHIVE_WARN if cleanup == "close" else ARCHIVE_OK,
        free_status=ARCHIVE_FATAL if cleanup == "free" else ARCHIVE_OK,
    )
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    with pytest.raises(LibarchiveInventoryError, match="cleanup"):
        backend.inventory(_archive(tmp_path))
    with pytest.raises(OSError) as closed:
        os.fstat(fake.last_descriptor)
    assert closed.value.errno == errno.EBADF


def test_primary_header_failure_is_not_replaced_by_cleanup_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLibrary(
        _official_entries(), header_failure=(0, ARCHIVE_FATAL),
        close_status=ARCHIVE_WARN, free_status=ARCHIVE_FATAL,
    )
    backend, _ = _backend(tmp_path, monkeypatch, fake)
    with pytest.raises(LibarchiveInventoryError, match="next_header") as failure:
        backend.inventory(_archive(tmp_path))
    assert failure.value.cleanup_diagnostics == (
        f"archive_read_close={ARCHIVE_WARN}",
        f"archive_read_free={ARCHIVE_FATAL}",
    )
    assert "cleanup/identity failure" in str(failure.value)


def test_cli_requires_and_propagates_explicit_libarchive_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = importlib.util.spec_from_file_location("lc02_ginav_runner_test", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    common = [
        "execute", "--ginav-root", str(tmp_path / "ginav"),
        "--matlab-executable", str(tmp_path / "matlab"),
        "--scratch-root", str(tmp_path / "scratch"),
        "--stage-root", str(tmp_path / "stage"),
        "--paper-root", str(tmp_path / "paper"),
        "--legacy-freeze-root", str(tmp_path / "legacy"),
    ]
    with pytest.raises(SystemExit):
        module.parser().parse_args(common)
    library = tmp_path / "libarchive.so"
    observed: dict[str, Any] = {}

    def fake_transaction(options: Any) -> dict[str, Any]:
        observed["options"] = options
        return {
            "terminal_status": module.SUCCESS_STATUS,
            "transaction_complete": True,
            "artifact_publication": "COMPLETE",
        }

    monkeypatch.setattr(module, "run_transaction", fake_transaction)
    assert module.main(common + ["--libarchive-path", str(library)]) == 0
    assert observed["options"].libarchive_path == library


def test_transaction_archive_path_has_no_7z_cli_or_implicit_discovery() -> None:
    archive_source = "\n".join(
        inspect.getsource(function)
        for function in (
            _inventory_sample_archive, _extract_sample, _run_sample_regression
        )
    )
    assert "shutil.which" not in archive_source
    assert "subprocess.run" not in archive_source
    assert '"7z"' not in archive_source and '"7zz"' not in archive_source
    backend_source = inspect.getsource(libarchive7z)
    assert "archive_read_extract(" not in backend_source
    assert "archive_read_data_into_fd(" not in backend_source


def _mock_transaction_to_backend_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[TransactionOptions, dict[str, Any]]:
    clean = tmp_path / "clean"
    raw = tmp_path / "raw"
    ginav = tmp_path / "ginav"
    paper = tmp_path / "paper"
    legacy = tmp_path / "legacy"
    matlab = tmp_path / "matlab"
    rtklib = tmp_path / "rtklib"
    convbin = tmp_path / "convbin"
    for directory in (clean, raw, ginav, paper, legacy, rtklib):
        directory.mkdir()
    matlab.write_bytes(b"matlab")
    convbin.write_bytes(b"convbin")
    options = TransactionOptions(
        repository_root=REPOSITORY,
        paths_config=tmp_path / "local.yaml",
        ginav_root=ginav,
        matlab_executable=matlab,
        libarchive_path=tmp_path / "libarchive.so",
        scratch_root=tmp_path / "scratch",
        destination_stage_root=tmp_path / "stage",
        paper_root=paper,
        legacy_freeze_root=legacy,
    )
    local = {
        "code_root": REPOSITORY,
        "raw_root": raw,
        "by2_fix_root": raw,
        "by2_go2_body": raw / "go2.txt",
        "clean_root": clean,
        "horizontal_literature_rtklib_root": rtklib,
        "horizontal_literature_convbin": convbin,
    }
    monkeypatch.setattr(
        transaction_module, "_load_local_paths",
        lambda supplied, verify_raw_availability: local,
    )
    monkeypatch.setattr(
        transaction_module, "validate_exact_destination",
        lambda destination, **kwargs: Path(destination),
    )

    def make_scratch(requested: Path, **kwargs: Any) -> Path:
        requested.mkdir()
        return requested

    monkeypatch.setattr(transaction_module, "_make_scratch_root", make_scratch)
    source_lock = {
        "commit": "pinned",
        "tree_oid": "pinned-tree",
        "tracked_source_clean": True,
        "named_files": {
            OFFICIAL_SAMPLE_RELATIVE.as_posix(): {"sha256": "sample-hash"},
            OFFICIAL_CONFIG_RELATIVE.as_posix(): {"sha256": "config-hash"},
        },
    }
    monkeypatch.setattr(
        transaction_module, "verify_source_identity", lambda root: source_lock
    )
    monkeypatch.setattr(
        transaction_module, "discover_matlab_candidates", lambda path: (matlab,)
    )
    monkeypatch.setattr(
        transaction_module, "_matlab_environment",
        lambda **kwargs: (
            {
                "executable_sha256": "matlab-hash",
                "version": "test", "release": "2025b",
                "platform_route": "TEST_ONLY",
            },
            {"run_id": "G0_MATLAB_ENVIRONMENT_candidate_1", "pass": True},
        ),
    )
    captured: dict[str, Any] = {}

    def finalize(status: str, **kwargs: Any) -> dict[str, Any]:
        captured.update({"status": status, **kwargs})
        return {"terminal_status": status, "pass": False}

    monkeypatch.setattr(transaction_module, "_finalize_terminal", finalize)
    return options, captured


def test_backend_preflight_failure_routes_as_technical_pre_sample_not_observed_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    options, captured = _mock_transaction_to_backend_boundary(tmp_path, monkeypatch)

    def fail_preflight(path: Path) -> None:
        raise LibarchivePreflightError("scripted incompatible backend")

    monkeypatch.setattr(transaction_module, "Libarchive7zBackend", fail_preflight)
    payload = run_transaction(options)
    assert payload["terminal_status"] == (
        "BLOCKED_LC02_GINAV_OFFICIAL_SAMPLE_REGRESSION_FAILURE"
    )
    provenance = captured["provenance"]
    assert provenance["technical_pre_sample_backend_failure"] is True
    assert provenance["official_sample_regression_executed"] is False
    assert provenance["official_sample_archive_inventory_completed"] is False
    assert provenance["official_sample_extraction_count"] == 0
    assert provenance["gate_execution_counts"]["G1_official_sample_runs"] == 0
    assert provenance["data_mode"] == "source_environment_only"
    assert "technical pre-sample archive backend failure" in captured["detail"]


def test_ordinary_archive_failure_does_not_inherit_technical_preflight_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    options, captured = _mock_transaction_to_backend_boundary(tmp_path, monkeypatch)
    backend = SimpleNamespace(
        identity={
            "library_path": str(options.libarchive_path),
            "library_sha256": "pinned",
            "pass": True,
        }
    )
    monkeypatch.setattr(
        transaction_module, "Libarchive7zBackend", lambda path: backend
    )
    monkeypatch.setattr(
        transaction_module, "_run_sample_regression",
        lambda **kwargs: (_ for _ in ()).throw(
            LibarchiveInventoryError("scripted archive contract failure")
        ),
    )
    payload = run_transaction(options)
    assert payload["terminal_status"] == (
        "BLOCKED_LC02_GINAV_OFFICIAL_SAMPLE_REGRESSION_FAILURE"
    )
    provenance = captured["provenance"]
    assert provenance["technical_pre_sample_backend_failure"] is False
    assert provenance["official_sample_archive_backend_preflight_completed"] is True
    assert provenance["official_sample_regression_executed"] is False
    assert "technical pre-sample" not in captured["detail"]


def test_g1_inventory_hash_mismatch_stops_before_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stage = tmp_path / "stage"
    (stage / "01_OFFICIAL_SAMPLE_REGRESSION").mkdir(parents=True)
    ginav = tmp_path / "ginav"
    ginav.mkdir()
    inventory = {
        "archive_sha256": "a" * 64,
        "frozen_inventory_binding_sha256": "b" * 64,
    }
    monkeypatch.setattr(
        transaction_module,
        "_inventory_sample_archive",
        lambda archive, backend, ledger: dict(inventory),
    )
    extraction_calls = 0

    def forbidden_extraction(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal extraction_calls
        extraction_calls += 1
        raise AssertionError("extraction must not start after source-lock mismatch")

    monkeypatch.setattr(transaction_module, "_extract_sample", forbidden_extraction)
    progress = {
        "official_sample_regression_executed": False,
        "official_sample_archive_inventory_completed": False,
        "official_sample_extraction_count": 0,
    }
    with pytest.raises(SourceIdentityError, match="pinned official source-lock"):
        _run_sample_regression(
            stage=stage,
            ginav_root=ginav,
            matlab_executable=tmp_path / "matlab",
            archive_backend=SimpleNamespace(),
            expected_archive_sha256="c" * 64,
            timeout_seconds=1,
            access_ledger=AccessLedger(),
            progress=progress,
        )
    assert progress["official_sample_archive_inventory_completed"] is True
    assert progress["official_sample_extraction_count"] == 0
    assert extraction_calls == 0


def test_g1_source_lock_hash_mismatch_routes_source_identity_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    options, captured = _mock_transaction_to_backend_boundary(tmp_path, monkeypatch)
    backend = SimpleNamespace(
        identity={
            "library_path": str(options.libarchive_path),
            "library_sha256": "pinned",
            "pass": True,
        }
    )
    monkeypatch.setattr(
        transaction_module, "Libarchive7zBackend", lambda path: backend
    )

    def source_mismatch(**kwargs: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        assert kwargs["expected_archive_sha256"] == "sample-hash"
        raise SourceIdentityError(
            "G1 archive inventory SHA256 does not match source lock"
        )

    monkeypatch.setattr(transaction_module, "_run_sample_regression", source_mismatch)
    payload = run_transaction(options)
    assert payload["terminal_status"] == (
        "BLOCKED_LC02_GINAV_SOURCE_IDENTITY_MISMATCH"
    )
    assert captured["status"] == "BLOCKED_LC02_GINAV_SOURCE_IDENTITY_MISMATCH"
    assert captured["provenance"]["official_sample_extraction_count"] == 0
    assert "source lock" in captured["detail"]
