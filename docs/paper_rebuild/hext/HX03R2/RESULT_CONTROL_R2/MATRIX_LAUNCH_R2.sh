#!/bin/bash
cd /home/kaiwen/research/LegSA-GINS-WORKTREES/clean3-math-repair
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src TMPDIR=/home/kaiwen/research/LegSA-GINS-SCRATCH/CLEAN9_EXTERNAL_COMPARISON/HX03R2 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 strace -yy -s 4096 -e trace=openat,execve -o /mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN9_EXTERNAL_COMPARISON/HX03R2_AUDIT_REEVAL/00_CONTROL/MATRIX_CONTROLLER_MAIN_R2.strace python3 scripts/paper_rebuild/hx03r2_execute.py --phase matrix --workers 6 > /mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN9_EXTERNAL_COMPARISON/HX03R2_AUDIT_REEVAL/00_CONTROL/MATRIX_STDOUT_R2.log 2> /mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN9_EXTERNAL_COMPARISON/HX03R2_AUDIT_REEVAL/00_CONTROL/MATRIX_STDERR_R2.log
hx03r2_exit_code=$?
printf '%s\n' "$hx03r2_exit_code" > /mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN9_EXTERNAL_COMPARISON/HX03R2_AUDIT_REEVAL/00_CONTROL/MATRIX_EXIT_CODE_R2.txt
exit "$hx03r2_exit_code"
