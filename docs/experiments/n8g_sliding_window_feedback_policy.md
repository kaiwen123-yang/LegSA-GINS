# N8G Sliding Window Feedback Policy

Sliding windows are built from the EKF state stream and GNSS/update candidate
times.

Each feedback window satisfies:

- `source_window_end <= feedback_time`;
- no future data enters a current-time feedback observation;
- feedback stride controls update cadence;
- epochs are not deleted to improve metrics;
- trace/final_v23 outputs are not solver inputs.
