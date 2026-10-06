from pathlib import Path
import shutil
import subprocess

import pytest

from legsa_gins.paper_rebuild.imu_time_contract import bind_measured_durations, continuous_segments


def test_gap_keeps_short_increment_and_partitions_without_imputation():
    measured = [dict(time=t, dt=.01, dtheta_x=.02, dtheta_y=0, dtheta_z=0)
                for t in (1., 1.01, 1.21, 1.22)]
    text = ''.join(f'{r["time"]:.6f} .02 0 0 0 0 -.098\n' for r in measured)
    rows = bind_measured_durations(text, measured)
    segments, gaps = continuous_segments(rows, start=1, end=2)
    assert [len(s) for s in segments] == [2, 2]
    assert gaps[0]['missing_duration'] == pytest.approx(.19)
    assert [r['legacy_line'] for s in segments for r in s] == text.splitlines()
    assert rows[2]['dt'] == .01


def test_wrong_raw_row_or_gyro_lineage_fails_closed():
    measured = [dict(time=1, dt=.01, dtheta_x=.02, dtheta_y=0, dtheta_z=0)]
    for line in ('1.1 .02 0 0 0 0 0', '1 .2 0 0 0 0 0'):
        with pytest.raises(ValueError):
            bind_measured_durations(line, measured)


@pytest.fixture(scope='module')
def loader_probe(tmp_path_factory):
    if not shutil.which('g++'):
        pytest.skip('native C++ regression requires g++')
    root = Path(__file__).resolve().parents[2] / 'cpp/legsa_v23_port_core'
    work = tmp_path_factory.mktemp('imu_loader_probe')
    source = work / 'probe.cpp'
    source.write_text('''#include "legsa_v23_port_core/fileio/imu_file_loader.hpp"
#include <iostream>
int main(int argc,char** argv) {
  try { auto rows=legsa_v23_port_core::ImuFileLoader::loadSevenColumn(argv[1]);
    std::cout.precision(17); for(auto& r:rows) std::cout<<r.dt<<"\\n";
  } catch(const std::exception& e) {std::cerr<<e.what();return 2;}
}''')
    exe = work / 'probe'
    subprocess.run(['g++', '-std=c++17', '-I'+str(root/'include'), str(source),
                    str(root/'src/fileio/imu_file_loader.cpp'),
                    str(root/'src/common/types.cpp'), '-o', str(exe)], check=True)
    return exe


def test_native_loader_rejects_short_increment_over_missing_interval(loader_probe, tmp_path):
    source = tmp_path / 'gap.imu'
    source.write_text('1 .02 0 0 0 0 -.098 .01\n1.2 .02 0 0 0 0 -.098 .01\n')
    result = subprocess.run([str(loader_probe), str(source)], capture_output=True, text=True)
    assert result.returncode == 2
    assert 'IMU_INCREMENT_DURATION_DISCONTINUITY' in result.stderr


def test_native_loader_uses_measured_duration_with_timestamp_rounding(loader_probe, tmp_path):
    source = tmp_path / 'valid.imu'
    source.write_text('1 .02 0 0 0 0 -.098 .0099997\n1.01 .02 0 0 0 0 -.098 .0099997\n')
    result = subprocess.run([str(loader_probe), str(source)], capture_output=True, text=True, check=True)
    assert [float(x) for x in result.stdout.split()] == pytest.approx([.0099997, .0099997], abs=1e-15)


@pytest.mark.parametrize('line', ['1 0 0 0 0 0 0 nan', '1 0 0 0 0 0 0 0',
                                  '1 0 0 0 0 0 0 .01 trailing', 'nan 0 0 0 0 0 0 .01'])
def test_native_extended_schema_rejects_invalid_rows(loader_probe, tmp_path, line):
    source = tmp_path / 'invalid.imu'; source.write_text(line+'\n')
    result = subprocess.run([str(loader_probe), str(source)], capture_output=True, text=True)
    assert result.returncode == 2
