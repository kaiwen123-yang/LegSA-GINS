"""Runtime-only RTKLIB command execution helpers.

中文说明：RTKLIB 可执行程序和输出都只作为 runtime 参数/产物使用；本模块不修改
RTKLIB 目录，不把 rnx2rtkp 最终定位解直接作为 LegSA solver 输入。
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    invocation_mode: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "stdout": self.stdout[-4000:],
            "stderr": self.stderr[-4000:],
            "invocation_mode": self.invocation_mode,
        }


def command_for_path(executable: str | Path, args: list[str] | None = None) -> tuple[list[str], str]:
    exe = str(executable)
    args = args or []
    if exe.lower().endswith(".exe"):
        # 中文说明：WSL 下先直接调用 Windows .exe；若失败，调用方可再尝试 cmd.exe /C。
        return [exe, *args], "windows_exe_via_wsl"
    return [exe, *args], "linux_binary"


def run_command(
    executable: str | Path,
    args: list[str] | None = None,
    *,
    cwd: str | Path | None = None,
    timeout: float = 30.0,
) -> CommandResult:
    command, mode = command_for_path(executable, args)
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return CommandResult(command, proc.returncode, proc.stdout, proc.stderr, mode)
    except (OSError, subprocess.TimeoutExpired) as first_error:
        if str(executable).lower().endswith(".exe"):
            command = ["cmd.exe", "/C", str(executable), *(args or [])]
            try:
                proc = subprocess.run(
                    command,
                    cwd=str(cwd) if cwd else None,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=timeout,
                    check=False,
                )
                return CommandResult(command, proc.returncode, proc.stdout, proc.stderr, "windows_exe_via_cmd")
            except (OSError, subprocess.TimeoutExpired) as second_error:
                return CommandResult(command, 127, "", f"{first_error}\n{second_error}", "windows_exe_failed")
        return CommandResult(command, 127, "", str(first_error), mode)


def ensure_runtime_dir(path: str | Path) -> Path:
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    return out


def env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else None
