from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.raw_gnss import rtklib_doppler_helper_builder as builder
from legsa_gins.raw_gnss import rtklib_doppler_velocity_provider as provider


class RawDopplerWslBridgeTest(unittest.TestCase):
    def test_compile_falls_back_to_wsl_gcc_when_native_gcc_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_copy = root / "src"
            source_copy.mkdir()
            helper_source = root / "helper.c"
            helper_source.write_text("int main(void){return 0;}\n", encoding="utf-8")
            helper_exe = root / "helper"
            c_file = source_copy / "rtkcmn.c"
            c_file.write_text("int x;\n", encoding="utf-8")

            with (
                mock.patch.object(builder.shutil, "which", return_value=None),
                mock.patch.object(builder, "_wsl_gcc_available", return_value=True),
                mock.patch.object(builder, "_wsl_path", side_effect=lambda p: "/wsl/" + Path(p).name),
                mock.patch.object(
                    builder.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess(args=["wsl"], returncode=0, stdout="", stderr=""),
                ),
            ):
                proc, command, mode = builder._run_compile(
                    ["gcc", "-O2"],
                    helper_exe,
                    source_copy,
                    helper_source,
                    [str(c_file)],
                )

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(mode, "wsl_gcc")
        self.assertEqual(command[:3], ["wsl", "bash", "-lc"])
        self.assertIn("gcc -O2", command[3])

    def test_provider_runs_non_exe_helper_through_wsl_on_windows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            helper = root / "helper"
            obs = root / "gnss.obs"
            nav = root / "gnss.nav"
            out = root / "helper.csv"
            for path in [helper, obs, nav]:
                path.write_text("", encoding="utf-8")

            with (
                mock.patch.object(provider.os, "name", "nt"),
                mock.patch.object(provider.shutil, "which", return_value="wsl"),
                mock.patch.object(provider, "_wsl_path", side_effect=lambda p: "/wsl/" + Path(p).name),
                mock.patch.object(
                    provider.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess(args=["wsl"], returncode=0, stdout="", stderr=""),
                ),
            ):
                proc, command, mode = provider._run_helper(helper, obs, nav, out)

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(mode, "wsl_helper")
        self.assertEqual(command[:3], ["wsl", "bash", "-lc"])
        self.assertIn("/wsl/helper", command[3])


if __name__ == "__main__":
    unittest.main()
