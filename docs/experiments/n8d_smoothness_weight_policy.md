# N8D Smoothness Weight Policy

Smoothness remains active in N8D, but its position, velocity, yaw, and attitude
roles are reviewed separately.

`no_yaw_smoothness` and `no_smoothness` variants are diagnostic-only. They are
not eligible as a final shortcut.

If deletion-style diagnostics look best, the recommendation is process-factor
redesign rather than deleting smoothness for metrics.
