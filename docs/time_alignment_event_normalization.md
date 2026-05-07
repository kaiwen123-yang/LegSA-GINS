# Time Alignment and Event-Normalized Algorithm Time

N4G does not assume hardware clock synchronization between the BY2 Fixposition
receiver computer and the Go2 computer. A Go2 stamp may look like Unix epoch
time, while GNSS status may expose UTC/GPS-like fields, but this stage does not
claim a physical clock offset.

The filter uses `algo_time_sec`, not raw wall-clock time. GNSS status is
normalized by its own formal motion start. Go2 body-state is normalized by its
own formal motion start. The kick event is only a search anchor for the
experiment segment; it is not directly treated as solver start.

Trace remains evaluation-only. N4G records:

- `clock_sync_claim=false`
- `physical_time_offset_claim=false`
- `event_normalized_time_axis=true`
- `trace_used_for_alignment=false`
- `trace_solver_input=false`

Raw times are retained as `raw_time` for provenance and are not overwritten.

