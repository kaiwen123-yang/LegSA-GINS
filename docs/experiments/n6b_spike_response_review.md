# N6B Spike Response Review

N5D1 raw-Doppler spike epochs are sentinels only. They are read by the N6B
after-run spike response audit to check whether raw-Doppler OIM/combined scale
increased near the sentinel rows.

They are not read by the solver policy, not hardcoded into C++, and not used for
threshold selection. The report records:
- spike report presence;
- nearest N6B raw-Doppler trace rows;
- spike-row combined/OIM scale;
- normal raw-Doppler median scale;
- spike-to-median ratio;
- response status.

This is an evaluation-only boundary check, not a tuning loop.
