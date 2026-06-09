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

Write-Section "Step 1/6: Checking PowerShell execution policy"
$policy = Get-ExecutionPolicy -Scope CurrentUser
if ($policy -eq 'Restricted' -or $policy -eq 'AllSigned') {
    if (-not $Force) {
        Write-Warn "Current execution policy is '$policy' which may block this script."
        Write-Info "To bypass for this run only, use: powershell -ExecutionPolicy Bypass -File .\setup.ps1"
        Write-Info "Or re-run with -Force to attempt without prompt."
        $choice = Read-Host "Continue anyway? (y/n)"
        if ($choice -ne 'y') { exit 1 }
    }
}

Write-Section "Step 2/6: Verifying Python"
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

Write-Section "Step 3/6: Installing uv"
if (Get-Command uv -ErrorAction SilentlyContinue) {
    $uvVersion = uv --version
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "uv --version failed (rc=$LASTEXITCODE). PATH may be stale; restart the shell."
    }
    Write-Info "uv already installed: $uvVersion"
} else {
    Write-Info "uv not found, installing via official PowerShell installer..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "uv install failed (rc=$LASTEXITCODE). See https://docs.astral.sh/uv/getting-started/installation/"
    }
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Fail "uv not found after install. Check $env:USERPROFILE\.local\bin or reinstall manually."
    }
    Write-Info "uv installed: $(uv --version)"
}

Write-Section "Step 4/6: Syncing workspace dependencies"
Repair-IncompleteVenv
$syncResult = Invoke-NativeCapture -FilePath 'uv' -Arguments @('sync', '--locked')
if ($syncResult.ExitCode -ne 0) {
    Write-Fail "uv sync failed (rc=$($syncResult.ExitCode)): $($syncResult.Output)"
}
Write-Info "Workspace dependencies installed"

Write-Section "Step 5/6: Installing Playwright Chromium"
$chromiumOk = $false
$crawlSetup = Invoke-NativeCapture -FilePath 'uv' -Arguments @('run', 'crawl4ai-setup')
if ($crawlSetup.ExitCode -eq 0) {
    $chromiumOk = $true
} else {
    Write-Warn "crawl4ai-setup encountered an issue; falling back to playwright install chromium"
    $playwrightInstall = Invoke-NativeCapture -FilePath 'uv' -Arguments @('run', 'python', '-m', 'playwright', 'install', 'chromium')
    if ($playwrightInstall.ExitCode -eq 0) {
        $chromiumOk = $true
    } else {
        Write-Warn "Playwright Chromium install failed. Web scraping will not work until fixed."
        Write-Warn "See https://playwright.dev/python/docs/intro for manual install."
    }
}

Write-Section "Step 6/6: Verifying workspace runtime"
$verifyResult = Invoke-UvPythonCode -Code "import crawl4ai, ddgs, arxiv, yaml; print('ok')"
if ($verifyResult.ExitCode -ne 0) {
    Write-Fail "Verification import failed: $($verifyResult.Output)"
}
Write-Info "All required packages importable: $($verifyResult.Output)"
if (-not $chromiumOk) {
    Write-Fail "Chromium was not installed successfully. Web scraping is the default mode; without Chromium, search_web.py will not be able to fetch pages. Re-run with explicit: uv run python -m playwright install chromium"
}

Write-Section "Workspace ready"
Write-Info "Next steps:"
Write-Info "  update config.json with your research question"
Write-Info "  uv run python scripts\search_web.py 'your query' --workspace ."
Write-Info "  uv run python scripts\workspace_info.py audit ."
