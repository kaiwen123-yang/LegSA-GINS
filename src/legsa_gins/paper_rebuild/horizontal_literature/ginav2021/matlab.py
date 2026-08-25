"""MATLAB discovery and non-patching official-source orchestration."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from .constants import TDCP_THRESHOLD_LITERAL
from .source import CoreCleanlinessGuard, SourceIdentityError, sha256_file


class MatlabRuntimeError(RuntimeError):
    pass


def discover_matlab_candidates(explicit: str | Path | None = None) -> tuple[Path, ...]:
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(Path(explicit).expanduser())
    for executable_name in ("matlab", "matlab.exe"):
        native = shutil.which(executable_name)
        if native:
            candidates.append(Path(native))
    where = shutil.which("where.exe")
    if where:
        try:
            result = subprocess.run(
                [where, "matlab.exe"], capture_output=True, text=True,
                timeout=15, check=False,
            )
        except OSError:
            result = None
        if result is not None and result.returncode == 0:
            candidates.extend(
                Path(line.strip()) for line in result.stdout.splitlines()
                if line.strip()
            )
    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        if resolved not in seen and resolved.is_file():
            unique.append(resolved)
            seen.add(resolved)
    return tuple(unique)


def wsl_to_windows_path(path: str | Path, *, distro: str | None = None) -> str:
    source = Path(path).expanduser().resolve(strict=False)
    text = str(source)
    match = re.match(r"^/mnt/([a-zA-Z])(?:/(.*))?$", text)
    if match:
        tail = (match.group(2) or "").replace("/", "\\")
        return f"{match.group(1).upper()}:\\{tail}"
    distribution = distro or os.environ.get("WSL_DISTRO_NAME")
    if not distribution:
        raise MatlabRuntimeError(
            "WSL_DISTRO_NAME or an explicit distro is required for an ext4 Windows path"
        )
    return "\\\\wsl.localhost\\" + distribution + text.replace("/", "\\")


def matlab_quote(value: str | Path) -> str:
    return str(value).replace("'", "''")


def build_matlab_batch_command(
    executable: str | Path,
    script_path: str | Path,
    *,
    distro: str | None = None,
) -> tuple[str, ...]:
    binary = Path(executable).resolve(strict=True)
    script = Path(script_path).resolve(strict=True)
    harness = script.parent
    if binary.suffix.casefold() == ".exe":
        target = wsl_to_windows_path(harness, distro=distro)
    else:
        target = str(harness)
    expression = (
        "try,addpath('" + matlab_quote(target) + "','-begin');"
        + script.stem
        + ";catch ME,disp(getReport(ME,'extended'));exit(1);end;exit(0);"
    )
    prefix = (str(binary), "-wait") if binary.suffix.casefold() == ".exe" else (str(binary),)
    return (*prefix, "-nosplash", "-r", expression)


def _matlab_path(path: str | Path, *, windows: bool, distro: str | None = None) -> str:
    return wsl_to_windows_path(path, distro=distro) if windows else str(Path(path).resolve())


def render_fopen_logger(log_path: str | Path, *, windows: bool, distro: str | None = None) -> str:
    ledger = matlab_quote(_matlab_path(log_path, windows=windows, distro=distro))
    return f"""function varargout = fopen(varargin)
global LEGSA_GINAV_FOPEN_LEDGER;
if isempty(LEGSA_GINAV_FOPEN_LEDGER)
    LEGSA_GINAV_FOPEN_LEDGER = '{ledger}';
end
if nargin >= 1 && ischar(varargin{{1}})
    audit_mode = 'r';
    if nargin >= 2 && ischar(varargin{{2}})
        audit_mode = char(varargin{{2}});
    end
    audit_fid = builtin('fopen', LEGSA_GINAV_FOPEN_LEDGER, 'a');
    if audit_fid >= 0
        fprintf(audit_fid, '%s\\t%s\\t%s\\n', datestr(now, 31), ...
            audit_mode, char(varargin{{1}}));
        builtin('fclose', audit_fid);
    end
end
[varargout{{1:nargout}}] = builtin('fopen', varargin{{:}});
end
"""


def render_environment_probe(
    output_tsv: str | Path,
    *,
    mirror_root: str | Path | None = None,
    windows: bool,
    distro: str | None = None,
) -> str:
    output = matlab_quote(_matlab_path(output_tsv, windows=windows, distro=distro))
    add_path = ""
    if mirror_root is not None:
        mirror = matlab_quote(_matlab_path(mirror_root, windows=windows, distro=distro))
        add_path = f"addpath(genpath('{mirror}'), '-begin');\n"
    return f"""function run_legsa_ginav
restoredefaultpath;
{add_path}fid = builtin('fopen', '{output}', 'w');
if fid < 0, error('cannot open MATLAB environment output'); end
fprintf(fid, 'field\\tversion\\t%s\\n', version);
fprintf(fid, 'field\\trelease\\t%s\\n', version('-release'));
fprintf(fid, 'field\\tcomputer\\t%s\\n', computer);
fprintf(fid, 'field\\tarch\\t%s\\n', computer('arch'));
fprintf(fid, 'field\\tmatlab_license_available\\t%d\\n', license('test', 'MATLAB'));
fprintf(fid, 'field\\tusejava_jvm\\t%d\\n', usejava('jvm'));
fprintf(fid, 'field\\tusejava_awt\\t%d\\n', usejava('awt'));
fprintf(fid, 'field\\tusejava_desktop\\t%d\\n', usejava('desktop'));
fprintf(fid, 'field\\tdefault_figure_visible\\t%s\\n', get(0, 'DefaultFigureVisible'));
fprintf(fid, 'field\\tbatch_mode\\t1\\n');
try, java_text = version('-java'); catch, java_text = ''; end
fprintf(fid, 'field\\tjava_version\\t%s\\n', legsa_one_line(java_text));
try, locale_text = evalc('disp(feature(''locale''))'); catch, locale_text = ''; end
fprintf(fid, 'field\\tlocale\\t%s\\n', legsa_one_line(locale_text));
required = {{'global_variable','decode_cfg','read_infile','readimu','exepos', ...
    'waitbar','figure','plot_trajectory_kine','gnss_solver','ins_align','tdcp2vel'}};
for i = 1:numel(required)
    fprintf(fid, 'function\\t%s\\t%s\\n', required{{i}}, ...
        legsa_one_line(which(required{{i}})));
end
installed = ver;
for i = 1:numel(installed)
    fprintf(fid, 'product\\t%s\\t%s\\t%s\\n', legsa_one_line(installed(i).Name), ...
        legsa_one_line(installed(i).Version), legsa_one_line(installed(i).Release));
end
builtin('fclose', fid);
end

function value = legsa_one_line(value)
if ~ischar(value), value = evalc('disp(value)'); end
value = strrep(value, sprintf('\\t'), ' ');
value = strrep(value, sprintf('\\r'), ' ');
value = strrep(value, sprintf('\\n'), ' ');
end
"""


def parse_environment_probe(path: str | Path) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    functions: dict[str, str] = {}
    products: list[dict[str, str]] = []
    with Path(path).open("r", encoding="utf-8", errors="strict") as handle:
        for line_number, raw in enumerate(handle, start=1):
            row = raw.rstrip("\r\n").split("\t")
            if not row or not row[0]:
                continue
            if row[0] == "field" and len(row) == 3:
                value: Any = row[2]
                if row[1] in {
                    "matlab_license_available", "usejava_jvm", "usejava_awt",
                    "usejava_desktop", "batch_mode",
                }:
                    value = row[2] == "1"
                fields[row[1]] = value
            elif row[0] == "function" and len(row) == 3:
                functions[row[1]] = row[2]
            elif row[0] == "product" and len(row) == 4:
                products.append(
                    {"Name": row[1], "Version": row[2], "Release": row[3]}
                )
            else:
                raise MatlabRuntimeError(
                    f"malformed MATLAB environment probe row {line_number}"
                )
    fields["required_function_availability"] = functions
    fields["installed_products"] = products
    return fields


def render_official_run_script(
    *,
    mirror_root: str | Path,
    harness_root: str | Path,
    config_path: str | Path,
    observation_path: str | Path,
    navigation_path: str | Path,
    imu_path: str | Path,
    windows: bool,
    distro: str | None = None,
) -> str:
    values = {
        key: matlab_quote(_matlab_path(value, windows=windows, distro=distro))
        for key, value in {
            "mirror": mirror_root,
            "harness": harness_root,
            "config": config_path,
            "obs": observation_path,
            "nav": navigation_path,
            "imu": imu_path,
            "data": Path(observation_path).parent,
        }.items()
    }
    return f"""function run_legsa_ginav
restoredefaultpath;
addpath(genpath('{values['mirror']}'), '-begin');
addpath('{values['harness']}', '-begin');
legsa_names = {{'global_variable','decode_cfg','read_infile','readimu','exepos', ...
    'gi_processor','gnss_solver','ins_align','tdcp2vel','lc_filter'}};
legsa_relative = {{'src/common/global_variable.m','src/read_file/decode_cfg.m', ...
    'src/read_file/read_infile.m','src/read_file/readimu.m','src/main_func/exepos.m', ...
    'src/main_func/gi_processor.m','src/main_func/gnss_solver.m', ...
    'src/ins/ins_align.m','src/ins/tdcp2vel.m','src/gnss_ins_lc/lc_filter.m'}};
for legsa_i = 1:numel(legsa_names)
    legsa_expected = fullfile('{values['mirror']}', strrep(legsa_relative{{legsa_i}}, '/', filesep));
    legsa_actual = which(legsa_names{{legsa_i}});
    if ~strcmpi(legsa_actual, legsa_expected)
        error('GINav pinned source resolution mismatch for %s: %s', ...
            legsa_names{{legsa_i}}, legsa_actual);
    end
end
global_variable;
global gls glc LEGSA_GINAV_FOPEN_LEDGER;
opt = decode_cfg(gls.default_opt, '{values['config']}');
file = gls.default_file;
file.path = '{values['data']}';
file.obsr = '{values['obs']}';
file.beph = '{values['nav']}';
file.imu = '{values['imu']}';
exepos(opt, file);
end
"""


def render_tdcp_probe_script(
    *,
    mirror_root: str | Path,
    harness_root: str | Path,
    config_path: str | Path,
    observation_path: str | Path,
    navigation_path: str | Path,
    imu_path: str | Path,
    output_csv: str | Path,
    windows: bool,
    distro: str | None = None,
) -> str:
    values = {
        key: matlab_quote(_matlab_path(value, windows=windows, distro=distro))
        for key, value in {
            "mirror": mirror_root, "harness": harness_root, "config": config_path,
            "obs": observation_path, "nav": navigation_path, "imu": imu_path,
            "output": output_csv, "data": Path(observation_path).parent,
        }.items()
    }
    # legsa_tdcp_counts is a diagnostic mirror only.  Official tdcp2vel is
    # separately called for velocity/flag and ins_align is called for the
    # actual alignment result.  The loop intentionally covers every eligible
    # epoch (not merely the first activation), yielding a conserved SPP status
    # inventory.  No core file is patched or replaced.
    return f"""function run_legsa_ginav
restoredefaultpath;
addpath(genpath('{values['mirror']}'), '-begin');
addpath('{values['harness']}', '-begin');
legsa_names = {{'global_variable','decode_cfg','read_infile','readimu','exepos', ...
    'gi_processor','gnss_solver','ins_align','tdcp2vel','lc_filter'}};
legsa_relative = {{'src/common/global_variable.m','src/read_file/decode_cfg.m', ...
    'src/read_file/read_infile.m','src/read_file/readimu.m','src/main_func/exepos.m', ...
    'src/main_func/gi_processor.m','src/main_func/gnss_solver.m', ...
    'src/ins/ins_align.m','src/ins/tdcp2vel.m','src/gnss_ins_lc/lc_filter.m'}};
for legsa_i = 1:numel(legsa_names)
    legsa_expected = fullfile('{values['mirror']}', strrep(legsa_relative{{legsa_i}}, '/', filesep));
    legsa_actual = which(legsa_names{{legsa_i}});
    if ~strcmpi(legsa_actual, legsa_expected)
        error('GINav pinned source resolution mismatch for %s: %s', ...
            legsa_names{{legsa_i}}, legsa_actual);
    end
end
global_variable;
global gls glc LEGSA_GINAV_FOPEN_LEDGER;
opt = decode_cfg(gls.default_opt, '{values['config']}');
file = gls.default_file;
file.path = '{values['data']}'; file.obsr = '{values['obs']}';
file.beph = '{values['nav']}'; file.imu = '{values['imu']}';
[obsr, obsb, nav, imu] = read_infile(opt, file); %#ok<ASGLU>
obsr = adjobs(obsr, opt); nav = adjnav(nav, opt);
rtk = initrtk(gls.rtk, opt);
oldobstime = gls.gtime; k = 0;
fid = builtin('fopen', '{values['output']}', 'w');
fprintf(fid, ['epoch_index,gps_week,gps_sow,common_phase_satellites,tdcp_equation_count,' ...
    'robust_retained_count,velocity_east_mps,velocity_north_mps,velocity_up_mps,' ...
    'velocity_right_mps,velocity_forward_mps,velocity_body_up_mps,' ...
    'velocity_ned_north_mps,velocity_ned_east_mps,velocity_ned_down_mps,' ...
    'speed_mps,speed_squared_m2ps2,threshold_literal,threshold_pass,' ...
    'official_tdcp_flag,prior_spp_available,prior_spp_status,spp_status,' ...
    'spp_satellite_count,spp_pair_available,tdcp_velocity_attempted,' ...
    'alignment_attempted,alignment_result\\n']);
while true
    [imud,imu,imu_stat] = searchimu(imu); %#ok<ASGLU>
    if imu_stat == 0, break; end
    [obs_epoch,nobs] = matchobs(rtk,imud,obsr);
    if nobs == 0, continue; end
    if (oldobstime.time ~= 0 && timediff(oldobstime,obs_epoch(1).time) == 0) ...
            || obs_epoch(1).time.sec ~= 0
        oldobstime = obs_epoch(1).time;
        continue;
    end
    oldobstime = obs_epoch(1).time; k = k + 1;
    common = 0; equations = 0; retained = 0;
    vel = [0,0,0]; tdcp_flag = 0; tdcp_attempted = 0;
    prior_spp_available = norm(rtk.sol.pos) ~= 0;
    prior_spp_status = rtk.sol.stat;
    if prior_spp_available
        [common,equations,retained] = legsa_tdcp_counts(rtk,nav,obs_epoch,rtk.oldobsr);
        [vel,tdcp_flag] = tdcp2vel(rtk,nav,obs_epoch,rtk.oldobsr);
        tdcp_attempted = 1;
    end
    speed2 = dot(vel,vel); speed = sqrt(speed2);
    yaw = vel2yaw(vel); Cnb = att2Cnb([0;0;yaw]); vbody = (Cnb' * vel')';
    alignment_attempted = 1;
    [rtk,align_flag] = ins_align(rtk,obs_epoch,NaN,nav);
    spp_pair_available = prior_spp_available && rtk.sol.stat ~= glc.SOLQ_NONE;
    [week,sow] = time2gpst(obs_epoch(1).time);
    fprintf(fid, ['%d,%d,%.9f,%d,%d,%d,%.12g,%.12g,%.12g,' ...
        '%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,' ...
        '{TDCP_THRESHOLD_LITERAL},%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\\n'], ...
        k-1,week,sow,common,equations,retained,vel(1),vel(2),vel(3), ...
        vbody(1),vbody(2),vbody(3),vel(2),vel(1),-vel(3),speed,speed2, ...
        speed2>3,tdcp_flag,prior_spp_available,prior_spp_status,rtk.sol.stat, ...
        rtk.sol.ns,spp_pair_available,tdcp_attempted,alignment_attempted,align_flag);
end
builtin('fclose', fid);
end

function [common,nv,n] = legsa_tdcp_counts(rtk,nav,cur_obs,old_obs)
global glc;
common=0; nv=0; n=0;
if isempty(old_obs) || ~isstruct(old_obs), return; end
cur_sv=satposs(cur_obs,nav,rtk.opt.sateph); old_sv=satposs(old_obs,nav,rtk.opt.sateph);
cur_rr=rtk.sol.pos; [cur_pos,~]=xyz2blh(cur_rr); old_rr=rtk.sol.pos;
v=zeros(size(cur_obs,1),1);
for i=1:size(cur_obs,1)
    cur_obsi=cur_obs(i); cur_svi=cur_sv(i); lam=nav.lam(cur_obsi.sat,:);
    [sys,~]=satsys(cur_obsi.sat); if rtk.mask(sys)==0 || lam(1)==0, continue; end
    old_idx=0;
    for j=1:size(old_obs,1)
        if cur_obsi.sat==old_obs(j).sat, old_idx=j; break; end
    end
    if old_idx==0, continue; end
    old_obsi=old_obs(old_idx); old_svi=old_sv(old_idx);
    if cur_obsi.L(1)==0 || old_obsi.L(1)==0, continue; end
    common=common+1;
    if cur_svi.svh~=0 || old_svi.svh~=0 || norm(cur_svi.pos)<=0 || norm(old_svi.pos)<=0, continue; end
    [cur_range,~]=geodist(cur_svi.pos,cur_rr'); [old_range,~]=geodist(old_svi.pos,old_rr');
    nv=nv+1; v(nv)=cur_obsi.L(1)*lam(1)-old_obsi.L(1)*lam(1)-cur_range+old_range ...
        +glc.CLIGHT*(cur_svi.dts-old_svi.dts);
end
if nv<4, return; end
v=v(1:nv); exc=zeros(nv,1);
for i=1:nv
    vi=abs(v(i)); other=abs(v); other(i)=[]; ave_v=sum(abs(other))/(nv-1);
    ave_distance=sum(abs(vi-other))/(nv-1);
    if ave_distance>3*ave_v || (ave_distance>100 && ave_distance>1.2*ave_v), exc(i)=1; end
end
n=sum(exc==0);
end
"""


def write_harness_files(
    harness_root: str | Path,
    *,
    main_script: str,
    fopen_log: str | Path,
    windows: bool,
    distro: str | None = None,
) -> Path:
    root = Path(harness_root)
    if root.exists():
        raise MatlabRuntimeError(f"MATLAB harness root already exists: {root}")
    root.mkdir(parents=True, exist_ok=False)
    (root / "fopen.m").write_text(
        render_fopen_logger(fopen_log, windows=windows, distro=distro),
        encoding="utf-8",
    )
    script = root / "run_legsa_ginav.m"
    script.write_text(main_script, encoding="utf-8")
    return script


def run_matlab_script(
    executable: str | Path,
    script: str | Path,
    *,
    timeout_seconds: float,
    launch_cwd: str | Path | None = None,
) -> dict[str, Any]:
    command = build_matlab_batch_command(executable, script)
    if launch_cwd is None:
        launch_cwd = Path(script).resolve(strict=True).parent
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=launch_cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        raise MatlabRuntimeError(
            "MATLAB invocation timed out after "
            f"{timeout_seconds}s; stdout={stdout!r}; stderr={stderr!r}"
        ) from exc
    runtime = time.monotonic() - started
    return {
        "command": list(command),
        "batch_invocation": "-nosplash -r function invocation",
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "runtime_seconds": runtime,
        "pass": result.returncode == 0,
    }


def validate_matlab_environment(
    payload: Mapping[str, Any],
    *,
    expected_source_root: str | Path | None = None,
) -> None:
    release = str(payload.get("release") or "")
    match = re.fullmatch(r"R?(\d{4})([ab])", release)
    if match is None:
        raise MatlabRuntimeError(f"unrecognized MATLAB release: {release}")
    release_key = (int(match.group(1)), match.group(2))
    if release_key < (2016, "a"):
        raise MatlabRuntimeError("GINav requires MATLAB R2016a or newer")
    if payload.get("matlab_license_available") not in (True, 1):
        raise MatlabRuntimeError("licensed MATLAB runtime is unavailable")
    if payload.get("usejava_awt") not in (True, 1):
        raise MatlabRuntimeError("MATLAB AWT/display support is unavailable for official figures")
    available = payload.get("required_function_availability")
    required = (
        "global_variable", "decode_cfg", "read_infile", "readimu", "exepos",
        "waitbar", "figure", "plot_trajectory_kine", "gnss_solver",
        "ins_align", "tdcp2vel",
    )
    if not isinstance(available, Mapping) or any(
        not available.get(name) for name in required
    ):
        raise MatlabRuntimeError("a MATLAB/GINav function required by the route is unavailable")
    if expected_source_root is not None:
        prefix = str(expected_source_root).replace("\\", "/").rstrip("/").casefold() + "/"
        official_names = required[:5] + required[7:]
        for name in official_names:
            resolved = str(available[name]).replace("\\", "/").casefold()
            if not resolved.startswith(prefix):
                raise MatlabRuntimeError(
                    f"MATLAB function {name} does not resolve inside the pinned mirror"
                )
