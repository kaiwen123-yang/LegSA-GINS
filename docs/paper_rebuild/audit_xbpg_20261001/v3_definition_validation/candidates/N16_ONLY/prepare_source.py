#!/usr/bin/env python3
"""Copy the registered observation source and apply only the N16 candidate patch."""
import csv
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat


def main():
    repo = Path(__file__).resolve().parents[6]
    aliases = json.loads((repo / "configs/paper_rebuild/V3_DEFINITION_ROOTS.local.json").read_text())["aliases"]
    original = Path(aliases["<OBSERVED_SOURCE>"])
    copied = Path(aliases["<VALIDATION_BUILD_ROOT>"]) / "source_N16_ONLY"
    output = Path(__file__).resolve().parent
    if original.is_symlink() or not original.is_dir() or copied.exists():
        raise RuntimeError("Refuse non-directory/symlink source or existing candidate source")
    inventory = []
    for parent, dirs, files in os.walk(original, followlinks=False):
        for name in dirs + files:
            path = Path(parent) / name
            if path.is_symlink():
                raise RuntimeError("Source contains symlink")
            if name in files:
                if not stat.S_ISREG(path.stat().st_mode):
                    raise RuntimeError("Source contains non-regular file")
                content = path.read_bytes()
                inventory.append({"relative_path": str(path.relative_to(original)), "bytes": len(content),
                                  "observed_source_sha256": hashlib.sha256(content).hexdigest()})
    shutil.copytree(original, copied, symlinks=False)
    for row in inventory:
        assert hashlib.sha256((copied / row["relative_path"]).read_bytes()).hexdigest() == row["observed_source_sha256"]

    changed = set()
    def replace(relative, old, new):
        path = copied / relative
        text = path.read_text()
        if text.count(old) != 1:
            raise RuntimeError("Unique patch anchor missing: " + relative)
        path.write_text(text.replace(old, new))
        changed.add(relative)

    prefix = "cpp/legsa_v23_port_core/"
    replace(prefix + "include/legsa_v23_port_core/source_aware/measurement_source.hpp",
            "  Vec3 std_xyz = makeVec3(1.0, 1.0, 1.0);",
            "  Vec3 std_xyz = makeVec3(1.0, 1.0, 1.0);\n"
            "  // N16_ONLY: quality follows actual observation axes; retain all original std values.\n"
            "  std::array<bool, 3> std_active_axes{{true, true, true}};")
    policy = prefix + "src/source_aware/source_aware_policy.cpp"
    replace(policy, "#include <deque>", "#include <deque>\n#include <limits>")
    replace(policy, """double maxStd(const Vec3& std_xyz) {
  return std::max({std::fabs(std_xyz[0]), std::fabs(std_xyz[1]), std::fabs(std_xyz[2])});
}

bool finiteStd(const Vec3& std_xyz) {
  return std::isfinite(std_xyz[0]) && std::isfinite(std_xyz[1]) && std::isfinite(std_xyz[2]) &&
         std_xyz[0] > 0.0 && std_xyz[1] > 0.0 && std_xyz[2] > 0.0;
}""", """double maxStd(const Vec3& std_xyz, const std::array<bool, 3>& active_axes) {
  // Preserve frozen comparison order, including active-NaN behavior.
  double value = std::numeric_limits<double>::quiet_NaN();
  bool have_active_axis = false;
  for (std::size_t axis = 0; axis < active_axes.size(); ++axis) {
    if (!active_axes[axis]) continue;
    const double axis_std = std::fabs(std_xyz[axis]);
    value = have_active_axis ? std::max(value, axis_std) : axis_std;
    have_active_axis = true;
  }
  return value;
}

bool finiteStd(const Vec3& std_xyz, const std::array<bool, 3>& active_axes) {
  bool have_active_axis = false;
  for (std::size_t axis = 0; axis < active_axes.size(); ++axis) {
    if (!active_axes[axis]) continue;
    have_active_axis = true;
    if (!std::isfinite(std_xyz[axis]) || std_xyz[axis] <= 0.0) return false;
  }
  // Empty is invalid, not a nominal zero-uncertainty domain.
  return have_active_axis;
}""")
    replace(policy, "maxStd(metadata.std_xyz)", "maxStd(metadata.std_xyz, metadata.std_active_axes)")
    replace(policy, "finiteStd(metadata.std_xyz)", "finiteStd(metadata.std_xyz, metadata.std_active_axes)")
    replace(policy, '         << ";yaw_std_rad=" << metadata.yaw_std_rad',
            '         << ";std_active_axes=(" << metadata.std_active_axes[0] << "/" << metadata.std_active_axes[1]\n'
            '         << "/" << metadata.std_active_axes[2] << ")"\n'
            '         << ";yaw_std_rad=" << metadata.yaw_std_rad')
    replace(prefix + "src/kf_gins/gi_engine.cpp",
            "    metadata.std_xyz = makeVec3(stdv[0], stdv[1], options_.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_vertical_disabled ? 999.0 : stdv[2]);",
            "    metadata.std_xyz = makeVec3(stdv[0], stdv[1], options_.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_vertical_disabled ? 999.0 : stdv[2]);\n"
            "    if (horizontal_2d) metadata.std_active_axes = {{true, true, false}};")
    replace(prefix + "src/kf_gins/gi_observer.cpp",
            '  Json md;md.add("source",source_aware::toString(m.source)).add("time",m.time).add("valid",m.valid).add("std_xyz",m.std_xyz)',
            '  Json md;md.add("source",source_aware::toString(m.source)).add("time",m.time).add("valid",m.valid).add("std_xyz",m.std_xyz)\n'
            '    .add("std_active_axes",m.std_active_axes)')
    patch = "".join("".join(difflib.unified_diff((original / relative).read_text().splitlines(True),
                      (copied / relative).read_text().splitlines(True), fromfile="a/" + relative,
                      tofile="b/" + relative, n=0)) for relative in sorted(changed))
    (output / "N16_ONLY.patch").write_text(patch)
    with (output / "SOURCE_COPY.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["relative_path", "bytes", "observed_source_sha256"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(inventory, key=lambda row: row["relative_path"]))
    manifest = {
        "candidate": "N16_ONLY", "source_base": "<OBSERVED_SOURCE>",
        "source_copy": "<VALIDATION_BUILD_ROOT>/source_N16_ONLY", "source_copy_files": len(inventory),
        "source_copy_bytes": sum(row["bytes"] for row in inventory),
        "copy_identity": "ALL_REGULAR_FILES_MATCH_BEFORE_PATCH", "symlinks": "NONE; rejected if present",
        "candidate_patch": "N16_ONLY.patch", "candidate_patch_sha256": hashlib.sha256(patch.encode()).hexdigest(),
        "changed_paths": sorted(changed), "public_observation_layer": "PENDING_SEPARATE_INSTALLATION",
        "std_active_axes_contract": "default N/E/D active; actual horizontal_2d N/E only; finiteStd(empty)=false; std values unchanged",
        "preparation_attempts": [
            {"attempt": 1, "status": "STOPPED_BEFORE_COPY", "reason": "one-off assertion expected 150 rg-visible files; actual source also has six .gitkeep files", "mutations": 0, "native_calls": 0},
            {"attempt": 2, "status": "SOURCE_COPY_AND_PATCH_COMPLETE", "file_count_policy": "all regular files including .gitkeep; no arbitrary expected count"}],
        "data_mode": "synthetic_fixture_only", "synthetic_data_used": True, "semisynthetic_data_used": False,
        "new_real_native_calls": 0, "new_evaluator_calls": 0, "new_provider_calls": 0,
    }
    (output / "CANDIDATE_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"status": "SOURCE_COPY_AND_PATCH_COMPLETE", "files": len(inventory), "candidate_patch_files": len(changed), "native_calls": 0}))


if __name__ == "__main__":
    main()
