# PAPER10Y WSL Compact Instructions

`fstrim` was attempted with `sudo -n fstrim -av`, but sudo required a password. No shutdown or compact command was executed inside WSL.

To compact the WSL ext4.vhdx, close this Codex/WSL session first, then run the generated script from Windows Administrator PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
cd <PAPER10Y_C_EXPORT_ROOT>
cd .\09_fstrim_compact
.\compact_wsl_vhdx_AFTER_USER_CONFIRM.ps1
```

The script runs `wsl.exe --shutdown`, locates the Ubuntu ext4.vhdx, prints before/after sizes, tries `Optimize-VHD -Mode Full`, falls back to diskpart compact, and does not unregister or move the VHDX.
