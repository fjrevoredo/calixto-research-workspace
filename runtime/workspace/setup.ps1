#!/usr/bin/env pwsh
# setup.ps1: bootstrap a standalone Calixto research workspace on Windows.

[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

$WorkspaceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $WorkspaceRoot

function Write-Section { param($msg) Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Write-Info    { param($msg) Write-Host "  -> $msg" -ForegroundColor Gray }
function Write-Warn    { param($msg) Write-Host "  !! $msg" -ForegroundColor Yellow }
function Write-Fail    { param($msg) Write-Host "  XX $msg" -ForegroundColor Red; exit 1 }
function Invoke-NativeCapture {
    param(
        [Parameter(Mandatory)] [string] $FilePath,
        [string[]] $Arguments = @()
    )
    $stdoutPath = [System.IO.Path]::GetTempFileName()
    $stderrPath = [System.IO.Path]::GetTempFileName()
    try {
        $process = Start-Process `
            -FilePath $FilePath `
            -ArgumentList $Arguments `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath `
            -Wait `
            -PassThru `
            -NoNewWindow
        $stdout = if (Test-Path -LiteralPath $stdoutPath) {
            Get-Content -LiteralPath $stdoutPath -Raw
        } else {
            ''
        }
        if ($null -eq $stdout) {
            $stdout = ''
        }
        $stderr = if (Test-Path -LiteralPath $stderrPath) {
            Get-Content -LiteralPath $stderrPath -Raw
        } else {
            ''
        }
        if ($null -eq $stderr) {
            $stderr = ''
        }
        return [pscustomobject]@{
            ExitCode = $process.ExitCode
            Output = ($stdout + $stderr).TrimEnd("`r", "`n")
        }
    } finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}
function Invoke-UvPythonCode {
    param([Parameter(Mandatory)] [string] $Code)
    $scriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("calixto-workspace-setup-" + [guid]::NewGuid().ToString("N") + ".py")
    try {
        Set-Content -LiteralPath $scriptPath -Value $Code -Encoding UTF8
        return Invoke-NativeCapture -FilePath 'uv' -Arguments @('run', 'python', $scriptPath)
    } finally {
        Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
    }
}
function Get-PreferredPowerShellCommand {
    foreach ($candidate in @('pwsh', 'powershell')) {
        if (Get-Command $candidate -ErrorAction SilentlyContinue) {
            return $candidate
        }
    }
    return $null
}
function Repair-IncompleteVenv {
    $venvDir = Join-Path $WorkspaceRoot ".venv"
    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    if ((Test-Path -LiteralPath $venvDir -PathType Container) -and -not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        Write-Warn "Detected incomplete virtual environment at '$venvDir'. Removing it before uv sync."
        try {
            Remove-Item -LiteralPath $venvDir -Recurse -Force
        } catch {
            Write-Fail "Failed to remove incomplete virtual environment at '$venvDir': $($_.Exception.Message)"
        }
    }
}

Write-Section "Step 1/5: Checking PowerShell execution policy"
$policy = Get-ExecutionPolicy -Scope CurrentUser
if ($policy -eq 'Restricted' -or $policy -eq 'AllSigned') {
    if (-not $Force) {
        Write-Warn "Current execution policy is '$policy' which may block this script."
        Write-Info "To bypass for this run only, use: pwsh -ExecutionPolicy Bypass -File .\setup.ps1"
        Write-Info "Or re-run with -Force to attempt without prompt."
        $choice = Read-Host "Continue anyway? (y/n)"
        if ($choice -ne 'y') { exit 1 }
    }
}

Write-Section "Step 2/5: Verifying Python"
$python = $null
foreach ($cand in @('python', 'python3', 'py')) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) {
        $python = $cand
        break
    }
}
if (-not $python) {
    Write-Fail "Python not found in PATH. Install Python 3.11+: https://www.python.org/downloads/windows/"
}
$pyVersionOutput = & $python --version 2>&1
Write-Info "Found: $pyVersionOutput"
if ($pyVersionOutput -notmatch 'Python (\d+)\.(\d+)') {
    Write-Fail "Could not parse Python version from: $pyVersionOutput"
}
$pyMajor = [int]$Matches[1]
$pyMinor = [int]$Matches[2]
if ($pyMajor -lt 3 -or ($pyMajor -eq 3 -and $pyMinor -lt 11)) {
    Write-Fail "Python 3.11+ required, found $pyVersionOutput"
}

Write-Section "Step 3/5: Installing uv"
if (Get-Command uv -ErrorAction SilentlyContinue) {
    $uvVersion = uv --version
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "uv --version failed (rc=$LASTEXITCODE). PATH may be stale; restart the shell."
    }
    Write-Info "uv already installed: $uvVersion"
} else {
    Write-Info "uv not found, installing via official PowerShell installer..."
    $powerShellCommand = Get-PreferredPowerShellCommand
    if (-not $powerShellCommand) {
        Write-Fail "Neither pwsh nor powershell is available to run the uv installer."
    }
    & $powerShellCommand -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "uv install failed (rc=$LASTEXITCODE). See https://docs.astral.sh/uv/getting-started/installation/"
    }
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Fail "uv not found after install. Check $env:USERPROFILE\.local\bin or reinstall manually."
    }
    Write-Info "uv installed: $(uv --version)"
}

Write-Section "Step 4/5: Syncing workspace dependencies"
Repair-IncompleteVenv
$syncResult = Invoke-NativeCapture -FilePath 'uv' -Arguments @('sync', '--locked')
if ($syncResult.ExitCode -ne 0) {
    Write-Fail "uv sync failed (rc=$($syncResult.ExitCode)): $($syncResult.Output)"
}
Write-Info "Workspace dependencies installed"

Write-Section "Step 5/5: Verifying workspace runtime"
$probeResult = Invoke-NativeCapture -FilePath 'uv' -Arguments @('run', 'python', 'scripts/runtime_probe.py')
if ($probeResult.ExitCode -ne 0) {
    if ($probeResult.Output -match '"error": "missing_browser"') {
        Write-Info "Chromium is missing; installing it for this standalone workspace"
        $playwrightInstall = Invoke-NativeCapture -FilePath 'uv' -Arguments @('run', 'python', '-m', 'playwright', 'install', 'chromium')
        if ($playwrightInstall.ExitCode -ne 0) {
            Write-Fail "Chromium install failed (rc=$($playwrightInstall.ExitCode)): $($playwrightInstall.Output)"
        }
        $probeResult = Invoke-NativeCapture -FilePath 'uv' -Arguments @('run', 'python', 'scripts/runtime_probe.py')
        if ($probeResult.ExitCode -ne 0) {
            Write-Fail "Workspace runtime probe still failed after browser install (rc=$($probeResult.ExitCode)): $($probeResult.Output)"
        }
    } else {
        Write-Fail "Workspace runtime probe failed (rc=$($probeResult.ExitCode)): $($probeResult.Output)"
    }
}

Write-Section "Workspace ready"
Write-Info "Next steps:"
Write-Info "  If this workspace lives under the creating toolkit root, you can reopen it with calixto open from there."
Write-Info "  If it was copied elsewhere, this local .venv is now the supported runtime."
Write-Info "  update config.json with your research question"
Write-Info "  uv run python scripts\search_web.py 'your query' --workspace ."
Write-Info "  uv run python scripts\workspace_info.py audit ."
