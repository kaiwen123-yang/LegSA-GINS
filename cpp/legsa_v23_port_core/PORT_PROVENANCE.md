# Port Provenance

- Source repository: `kaiwen123-yang/KF-GINS-graduation-design`
- Source role: final_v23/KF-GINS reference backbone
- Source commit: `5a4471efd4fcfcdc31e258a677af354c652ff16f`
- Port target: `cpp/legsa_v23_port_core`
- Port method: controlled source-backed refactor into LegSA-owned files with
  provenance headers and Chinese comments.

This port is a mature GNSS/INS backbone implementation target, not paper
novelty and not the proposed factor contribution. final_v23 output is not
solver input. Trace remains evaluation-only. Generated data and generated
results are excluded from Git. Clean/noisy provenance must be preserved.

N4H4R1 is a minimal compileable foundation and toy dry-run stage. Clean replay
parity is not attempted in R1.

