# Pinned Official C++ Build and Example Report

## Terminal result

`PASS_OFFICIAL_CPP_BUILD_KINEMATICS_AND_LANDMARK_EXAMPLES`

The source was `RossHartley/invariant-ekf@ef16e8a1df72f9272111a488880e3fe9d161f59f`, detached and clean before and after the build. No source patch was applied.

## Environment

| Component | Observed identity |
|---|---|
| Operating environment | Linux x86-64, WSL-hosted audit environment |
| C++ compiler | `/usr/bin/g++`, GCC 11.4.0 (`Ubuntu 11.4.0-1ubuntu1~22.04.3`) |
| CMake | 3.22.1 |
| Eigen | 3.4.0, package `3.4.0-2ubuntu2`, include `/usr/include/eigen3` |
| Boost system | 1.74.0, package `1.74.0.3ubuntu7` |
| Upstream CMake options | `USE_CPP11=ON`, `USE_MUTEX=OFF`, Release plus upstream `-O3 -DEIGEN_NO_DEBUG -march=native` |

## Commands and return codes

Aliases used below:

- `<HARTLEY_CPP_ROOT>`: external pinned source clone;
- `<HARTLEY_CPP_BUILD>`: external isolated CMake object/cache and audit directory.

```bash
cmake -S <HARTLEY_CPP_ROOT> \
  -B <HARTLEY_CPP_BUILD> \
  -DCMAKE_BUILD_TYPE=Release

cmake --build <HARTLEY_CPP_BUILD> --parallel 4

cd <HARTLEY_CPP_ROOT>/bin
./kinematics
./landmarks
```

| Operation | Return code | Wall time | Result |
|---|---:|---:|---|
| CMake configure | 0 | 1.49 s | pass; Boost and Eigen found |
| CMake build | 0 | 20.94 s | pass; examples, speed tests, and shared library linked |
| `kinematics` official executable | 0 | 0.22 s | pass |
| `landmarks` official executable | 0 | 0.01 s | pass with parser limitation below |

CMake emitted only its expected compatibility warning for the upstream `cmake_minimum_required(VERSION 2.8.3)`. The upstream CMake file fixes final executable/library destinations to `<HARTLEY_CPP_ROOT>/bin` and `<HARTLEY_CPP_ROOT>/lib`; CMake object/cache files remained under `<HARTLEY_CPP_BUILD>`. Those final build products are ignored by the upstream repository, and `git status --short --branch` remained `## HEAD (no branch)`.

Observed build-product hashes for this environment:

| Product | SHA-256 |
|---|---|
| `bin/kinematics` | `7feb615e4392cd24399f890c5788f262bbf7beac186b0959f0460d6571f6892c` |
| `bin/landmarks` | `3d7ec57bdb864ca1231a7d14d547ec76d02a8a0e1786634054ea1efdd2d66544` |
| `lib/libinekf.so` | `3d1b190b0f933adbb3a042ac3d36e14e05ef2a68c788f3794e07287c1c30405a` |

These binary hashes are environment-specific build evidence, not portable expected values.

## Diagnostic method

The official executables print every event and a rounded final `RobotState`; they do not print lifecycle counters, covariance symmetry, or eigenvalues. A non-invasive, untracked harness was therefore built under `<HARTLEY_CPP_BUILD>` against the unmodified shared library. It:

- reproduces each example's initialization and parser semantics;
- queries only the public `InEKF`/`RobotState` API;
- counts input and lifecycle events before/after public correction calls;
- computes full-precision finite, symmetry, and symmetrized-covariance eigenvalue diagnostics;
- uses the same Eigen ABI/compiler flags as the upstream library;
- does not alter either official repository.

Final harness SHA-256: `cc52a08ddd6dda8b21d066d2cc6dfadc6e27a0c9c955cc93038f77f46dfe7477`.

The harness reproduces the official executables' rounded final state fields. The JSON summaries are observations from this pinned environment, not paper-provided golden truth.

## Kinematics/contact example

Input: `src/data/imu_kinematic_measurements.txt`, SHA-256 `224e03c83062fb937bfe529aa3858a04e07ed3143f92f8e0868bacbeae08491b`.

| Quantity | Count/value |
|---|---:|
| Total input rows | 59,976 |
| IMU rows / propagation calls | 19,992 / 19,992 |
| CONTACT rows / indicator values | 19,992 / 39,984 |
| KINEMATIC rows / point measurements | 19,992 / 39,984 |
| Stacked correction calls / used point rows | 19,780 / 26,741 |
| Contact additions / removals | 34 / 33 |
| Final active contacts | 1 |
| Final dimensions | `X 6x6`, `Theta 6`, `P 18x18` |
| State finite / covariance finite | true / true |
| Maximum covariance asymmetry | `2.2456264278658544e-12` |
| Minimum symmetrized covariance eigenvalue | `2.7730288943281978e-07` |
| Maximum symmetrized covariance eigenvalue | `2.3272959657420311` |
| Rotation determinant | `1.0000000000000082` |

This closes the official switching-contact lifecycle smoke: both additions and removals occurred, a stacked point-contact update was exercised, and the final covariance was finite, nearly symmetric, and positive under the reported eigensolver check.

## Landmark example

Input: `src/data/imu_landmark_measurements.txt`, SHA-256 `fe9f4cb906d4189108b5a0162614504979b2f249cc640424908d850a23139b67`.

| Quantity | Count/value |
|---|---:|
| Total input rows | 20,192 |
| IMU rows | 19,992 |
| Effective propagation calls | 0 |
| LANDMARK rows / measurements | 200 / 421 |
| Correction calls / used landmark rows | 200 / 420 |
| New estimated landmarks | 1 |
| Final estimated landmarks | 1 |
| Final dimensions | `X 6x6`, `Theta 6`, `P 18x18` |
| State finite / covariance finite | true / true |
| Maximum covariance asymmetry | `5.5511151231257827e-16` |
| Minimum symmetrized covariance eigenvalue | `9.27596869229605e-06` |
| Maximum symmetrized covariance eigenvalue | `1.5000287005917698` |
| Rotation determinant | `0.99999999999999922` |

The zero propagation count is an exact upstream-example limitation: `src/examples/landmarks.cpp:111-117` parses decimal timestamps and IMU values with `atoi`, and its strict `dt<1` gate rejects the resulting one-second timestamp jumps. The executable's return code and finite output prove that the pinned landmark path builds and runs, but they do **not** prove landmark-aided IMU propagation fidelity. No upstream repair was made.

## Historical MATLAB execution status

Neither MATLAB nor Octave was available. The pinned historical repository was audited statically and remained clean. Its absence is nonblocking under the H0-H2 contract.

## Evidence boundary

- No paper figure or plot was used as a numerical expected value.
- No BY2 data or filter path was opened or run by this code/build lane.
- No trace/reference trajectory or prior LegSA/EXT output was read.
- No EXT01-EXT06, HORIZONTAL18, or Canonical-541 execution occurred.
- All example outputs and build products remain external and untracked.
