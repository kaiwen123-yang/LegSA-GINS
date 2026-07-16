"""Fail-closed subprocess execution for CLEAN1 process trees."""

from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path
from typing import Sequence


def run_process_group(
    command: Sequence[str],
    *,
    cwd: str | Path,
    timeout_seconds: float,
    timeout_message: str,
    launch_failure_message: str,
    termination_grace_seconds: float = 5.0,
) -> subprocess.CompletedProcess[str]:
    """Run one isolated process group and kill the whole tree on timeout.

    ``strace -f`` is frequently the direct child while the actual provider,
    solver, or evaluator is its tracee.  Killing only the direct child can
    leave that tracee writing into an attempt directory after the caller has
    declared failure, so every CLEAN1 external execution gets a new session.
    """

    argv = [str(value) for value in command]
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            start_new_session=True,
        )
    except OSError as exc:
        return subprocess.CompletedProcess(
            argv,
            127,
            "",
            f"{launch_failure_message}: {exc}",
        )

    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = process.communicate(timeout=termination_grace_seconds)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
        suffix = f"\n{timeout_message}"
        return subprocess.CompletedProcess(argv, 124, stdout, (stderr or "") + suffix)
