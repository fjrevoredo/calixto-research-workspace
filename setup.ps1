#!/usr/bin/env pwsh
# setup.ps1: One-shot environment setup for Calixto Research Workspace on Windows.
# Idempotent. Safe to re-run. Prints every step clearly.
#
# Usage: .\setup.ps1
# Requires: Python 3.11+, internet, ~500MB disk for Playwright/Chromium.

[CmdletBinding()]
param(
    [switch]$Force  # Skip the PowerShell execution policy check (use with care)
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ScriptDir

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
    $scriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("calixto-setup-" + [guid]::NewGuid().ToString("N") + ".py")
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
    $venvDir = Join-Path $ScriptDir ".venv"
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

# 1. Check PowerShell execution policy
Write-Section "Step 1/8: Checking PowerShell execution policy"
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

# 2. Verify Python 3.11+
Write-Section "Step 2/8: Verifying Python"
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

# 3. Install uv if missing
Write-Section "Step 3/8: Installing uv (Python package manager)"
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

# 4. Sync dependencies. PowerShell try/catch does NOT reliably catch
# native executable nonzero exits: $LASTEXITCODE is the source of truth.
Write-Section "Step 4/8: Installing Python dependencies"
Write-Info "This installs: crawl4ai (~50MB), ddgs (~5MB, renamed from duckduckgo-search), arxiv (~1MB), pyyaml (~1MB)"
Repair-IncompleteVenv
$syncResult = Invoke-NativeCapture -FilePath 'uv' -Arguments @('sync', '--locked')
if ($syncResult.ExitCode -ne 0) {
    Write-Fail "uv sync failed (rc=$($syncResult.ExitCode)): $($syncResult.Output)"
}
Write-Info "Python dependencies installed"

# 5. Verify the root toolkit environment itself.
Write-Section "Step 5/8: Verifying toolkit dependencies"
$verifyCode = @'
import sys
try:
    import crawl4ai
    import ddgs
    import arxiv
    import yaml
    print("All required packages importable")
except ImportError as e:
    print(f"Import failed: {e}", file=sys.stderr)
    sys.exit(1)
'@
$verifyResult = Invoke-UvPythonCode -Code $verifyCode
if ($verifyResult.ExitCode -ne 0) {
    Write-Fail "Verification failed (rc=$($verifyResult.ExitCode)): $($verifyResult.Output)"
}
Write-Info $verifyResult.Output

# 6. Prepare the shared managed workspace runtime.
Write-Section "Step 6/8: Preparing managed workspace runtime"
Write-Info "This prepares the shared workspace runtime once and installs Chromium only when missing"
$managedRuntime = Invoke-NativeCapture -FilePath 'uv' -Arguments @('run', 'python', 'scripts/managed_runtime.py', 'prepare')
if ($managedRuntime.ExitCode -ne 0) {
    Write-Fail "Managed runtime preparation failed (rc=$($managedRuntime.ExitCode)): $($managedRuntime.Output)"
}
Write-Info "Managed runtime ready"

# 7. Install the context-aware launcher.
Write-Section "Step 7/8: Installing calixto launcher"
$shimResult = Invoke-NativeCapture -FilePath 'uv' -Arguments @('run', 'python', 'scripts/install_calixto_shim.py', '--toolkit-root', $ScriptDir)
if ($shimResult.ExitCode -ne 0) {
    Write-Fail "Launcher installation failed (rc=$($shimResult.ExitCode)): $($shimResult.Output)"
}
Write-Info "Launcher ready"
if ($shimResult.Output -match 'PATH_MISSING::([^\r\n]+)') {
    Write-Warn "The launcher directory is not currently on PATH: $($Matches[1])"
    Write-Warn "Add it to PATH or use the fallback command: uv run --project `"$ScriptDir`" calixto ..."
}

# 8. Summary
Write-Section "Step 8/8: Setup complete"
Write-Info "Total installed: ~500MB (mostly Chromium browser)"
Write-Host ""
Write-Info "Quick start:"
Write-Info "  Run this from inside this toolkit root (or set CALIXTO_TOOLKIT_ROOT):"
Write-Info "  calixto research 'your question' --agent none"
Write-Info "Fallback if the launcher is not on PATH:"
Write-Info "  uv run --project `"$ScriptDir`" calixto research 'your question' --agent none"
Write-Host ""
Write-Info "Run the golden dataset to validate:"
Write-Info "  python tests\golden\run.py --use-cache"
Write-Host ""
Write-Info "See AGENTS.md for full documentation."
