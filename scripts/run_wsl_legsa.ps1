param(
    [Alias("Distro")]
    [string]$WslDistro,

    [Alias("Cwd", "WorkDir")]
    [string]$WorkingDirectory,

    [Alias("Cmd")]
    [Parameter(Mandatory = $true)]
    [string]$Command,

    [switch]$DryRun,

    [string]$LogPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Convert-ToWslPath {
    param([string]$PathValue)
    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        return $PathValue
    }
    if ($PathValue -match "^/") {
        return $PathValue
    }
    $full = [System.IO.Path]::GetFullPath($PathValue)
    if ($full -match "^([A-Za-z]):\\(.*)$") {
        $drive = $matches[1].ToLowerInvariant()
        $rest = $matches[2] -replace "\\", "/"
        return "/mnt/$drive/$rest"
    }
    return $PathValue
}

$wslWorkingDirectory = Convert-ToWslPath -PathValue $WorkingDirectory
$wslArgs = @()
if (-not [string]::IsNullOrWhiteSpace($WslDistro)) {
    $wslArgs += @("-d", $WslDistro)
}
if (-not [string]::IsNullOrWhiteSpace($wslWorkingDirectory)) {
    $wslArgs += @("--cd", $wslWorkingDirectory)
}
$wslArgs += @("bash", "-lc", $Command)

$plan = [ordered]@{
    dry_run = [bool]$DryRun
    wsl_distro = $WslDistro
    working_directory_input = $WorkingDirectory
    working_directory_wsl = $wslWorkingDirectory
    command = $Command
    argv = @("wsl.exe") + $wslArgs
    executed = $false
}

$planJson = $plan | ConvertTo-Json -Depth 5
Write-Output $planJson
if (-not [string]::IsNullOrWhiteSpace($LogPath)) {
    $logParent = Split-Path -Parent $LogPath
    if (-not [string]::IsNullOrWhiteSpace($logParent)) {
        New-Item -ItemType Directory -Force -Path $logParent | Out-Null
    }
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($LogPath, $planJson, $utf8NoBom)
}

if ($DryRun) {
    exit 0
}

& wsl.exe @wslArgs
exit $LASTEXITCODE
