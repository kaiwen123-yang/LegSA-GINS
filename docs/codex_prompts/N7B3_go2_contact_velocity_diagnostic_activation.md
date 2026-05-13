# N7B3 Go2 Contact Velocity Diagnostic Activation Prompt

Continue PR #36 without merging it, tagging it, opening a new PR, or moving to
FGO. Keep Go2 velocity/contact/yaw-rate activation diagnostic-only.

Run the N7B3 runner with role-alias runtime roots, build C++ first, generate all
JSON/CSV/MD reports and figures in runtime output directories only, then run the
N7B3 audits, inherited N7B/N7A boundary audits, pytest, CMake, path-leak checks,
artifact checks, `/home/kaiwen/KF-GINS` unchanged checks, and submodule checks.

Do not commit raw data, `by2.txt`, generated prior CSVs, generated NAV/STD/EVAL
outputs, summaries, error series, figures, or local absolute runtime paths.
