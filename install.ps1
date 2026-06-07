# install.ps1: One-liner installer for Calixto Research Workspace on Windows.
#
# Two modes:
#   1. Fresh install: runs in an empty directory. Downloads the repo, copies files,
#      runs setup.ps1.
#   2. Workspace update: runs inside an existing Calixto workspace. Backs up user
#      data (especially workspaces/), pulls latest changes, optionally runs setup.
#
# Usage:
#   irm https://calixto.dev/install.ps1 | iex
#   irm https://calixto.dev/install.ps1 -DryRun | iex
#
# Safety:
#   - Never deletes user data without explicit confirmation
#   - Always prompts before making changes
#   - Backs up workspaces/ before updating
#   - Idempotent: safe to re-run

[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$NonInteractive,
    [switch]$SkipDeps,
    [string]$Version = $env:CALIXTO_VERSION,
    [string]$RepoUrl = $(if ($env:CALIXTO_REPO_URL) { $env:CALIXTO_REPO_URL } else { 'https://github.com/calixto/calixto.git' }),
    [string]$Branch = $(if ($env:CALIXTO_REPO_BRANCH) { $env:CALIXTO_REPO_BRANCH } else { 'main' })
)

$ErrorActionPreference = 'Stop'

$TargetDir = (Get-Location).Path
$RepoUrl = $RepoUrl
$Branch = $Branch
$Version = $Version

# Files/dirs that signal "this is already a Calixto workspace"
$WorkspaceMarkers = @(
    'PHILOSOPHY.md',
    'requirements.md',
    'AGENTS.md',
    'setup.sh',
    'setup.ps1',
    'templates',
    'scripts',
    'providers',
    'skills'
)

function Write-Section { param($m) Write-Host "`n=== $m ===" -ForegroundColor Cyan }
function Write-Info    { param($m) Write-Host "  -> $m" -ForegroundColor Gray }
function Write-Warn    { param($m) Write-Host "  !! $m" -ForegroundColor Yellow }
function Write-Fail    { param($m) Write-Host "  XX $m" -ForegroundColor Red; exit 1 }

function Test-Workspace {
    foreach ($marker in $WorkspaceMarkers) {
        if (-not (Test-Path -LiteralPath (Join-Path $TargetDir $marker))) {
            return $false
        }
    }
    return $true
}

function Confirm-Action {
    param($prompt)
    if ($NonInteractive) {
        Write-Info "[non-interactive] auto-confirming: $prompt"
        return $true
    }
    if ($DryRun) {
        Write-Host "   [dry-run] would prompt: $prompt"
        return $true
    }
    $r = Read-Host "  $prompt (y/n)"
    return ($r -eq 'y' -or $r -eq 'Y' -or $r -eq 'yes')
}

function Invoke-Step {
    param([scriptblock]$action)
    if ($DryRun) {
        Write-Host "   [dry-run] $($action.ToString().Trim())"
    } else {
        & $action
    }
}

# Fetch the source
function Get-RepoSource {
    # Prefer git if available, else tarball
    if (Get-Command git -ErrorAction SilentlyContinue) {
        $ref = if ($Version) { $Version } else { $Branch }
        return @{ Mode = 'git'; Url = $RepoUrl; Ref = $ref }
    }
    # Tarball fallback
    if ($RepoUrl -notmatch '^https://github\.com/') {
        Write-Fail "Cannot derive tarball URL from: $RepoUrl. Install git or set CALIXTO_REPO_URL to a GitHub URL."
    }
    $base = $RepoUrl -replace '\.git$', ''
    $ref = if ($Version) { $Version } else { $Branch }
    return @{ Mode = 'tarball'; Url = "$base/archive/refs/heads/$ref.tar.gz" }
}

# =================================================================
# Mode 1: Fresh install
# =================================================================
function Invoke-FreshInstall {
    Write-Section "Mode: fresh install"
    Write-Info "Target: $TargetDir"
    Write-Info "Repository: $RepoUrl (branch: $Branch$(if ($Version) { ", version: $Version" }))"

    # Safety: refuse to install into a non-empty directory
    if (Test-Path -LiteralPath $TargetDir) {
        $existing = Get-ChildItem -LiteralPath $TargetDir -Force -ErrorAction SilentlyContinue
        if ($existing.Count -gt 0) {
            Write-Fail "Target directory is not empty. Use a new directory for fresh install, or run inside an existing Calixto workspace for update mode."
        }
    }

    if (-not (Confirm-Action "This will install Calixto Research Workspace into '$TargetDir'. Continue?")) {
        Write-Info "Installation cancelled."
        exit 0
    }

    $src = Get-RepoSource
    Write-Info "Source mode: $($src.Mode)"

    $staging = Join-Path $TargetDir '.calixto-stage'
    if (-not $DryRun) {
        if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
        New-Item -ItemType Directory -Path $staging -Force | Out-Null
    }

    switch ($src.Mode) {
        'git' {
            Invoke-Step { git clone --depth 1 --branch $src.Ref $src.Url $staging }
            if (-not $DryRun) {
                Get-ChildItem -LiteralPath $staging -Force | ForEach-Object {
                    Move-Item -LiteralPath $_.FullName -Destination $TargetDir -Force
                }
            }
        }
        'tarball' {
            $tarball = Join-Path $staging 'repo.tar.gz'
            Invoke-Step { Invoke-WebRequest -Uri $src.Url -OutFile $tarball }
            if (-not $DryRun) {
                Expand-Archive -Path $tarball -DestinationPath $staging -Force
                $extracted = Get-ChildItem -LiteralPath $staging -Directory | Where-Object { $_.Name -like 'calixto-*' } | Select-Object -First 1
                if ($extracted) {
                    Get-ChildItem -LiteralPath $extracted.FullName -Force | ForEach-Object {
                        Move-Item -LiteralPath $_.FullName -Destination $TargetDir -Force
                    }
                } else {
                    Write-Fail "Tarball extraction did not produce expected directory."
                }
            }
        }
    }

    if (-not $DryRun -and (Test-Path $staging)) {
        Remove-Item $staging -Recurse -Force
    }

    if (-not $SkipDeps -and -not $DryRun) {
        Write-Section "Running setup.ps1 to install dependencies"
        $setupPath = Join-Path $TargetDir 'setup.ps1'
        if (Test-Path $setupPath) {
            & pwsh -ExecutionPolicy Bypass -File $setupPath
            if ($LASTEXITCODE -ne 0) {
                Write-Warn "setup.ps1 had issues. Re-run with .\setup.ps1 to retry."
            }
        }
    }

    Write-Section "Fresh install complete"
    Write-Info "To start: cd $TargetDir ; python scripts\init_workspace.py my-research"
}

# =================================================================
# Mode 2: Update workspace
# =================================================================
function Invoke-UpdateWorkspace {
    Write-Section "Mode: workspace update"
    Write-Info "Target: $TargetDir"

    $missing = @()
    foreach ($marker in $WorkspaceMarkers) {
        if (-not (Test-Path -LiteralPath (Join-Path $TargetDir $marker))) {
            $missing += $marker
        }
    }
    if ($missing.Count -gt 0) {
        Write-Fail "Directory looks like a partial Calixto workspace. Missing: $($missing -join ', '). Run from a complete Calixto workspace, or use a new directory for fresh install."
    }

    if (-not (Confirm-Action "This will update Calixto Research Workspace in '$TargetDir'. User data (workspaces/, notes/, outputs/, config files) will be preserved. Continue?")) {
        Write-Info "Update cancelled."
        exit 0
    }

    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backupDir = Join-Path $TargetDir ".calixto-backup-$timestamp"
    Write-Info "Backing up user data to $backupDir"
    if (-not $DryRun) {
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    }
    foreach ($item in @('workspaces', 'notes', 'outputs')) {
        $src = Join-Path $TargetDir $item
        if (Test-Path $src) {
            $dst = Join-Path $backupDir $item
            Invoke-Step { Copy-Item -LiteralPath $src -Destination $dst -Recurse -Force }
        }
    }

    $src = Get-RepoSource
    $staging = Join-Path $TargetDir '.calixto-update'
    if (-not $DryRun) {
        if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
        New-Item -ItemType Directory -Path $staging -Force | Out-Null
    }

    switch ($src.Mode) {
        'git' {
            Invoke-Step { git clone --depth 1 --branch $src.Ref $src.Url (Join-Path $staging 'repo') }
            if (-not $DryRun) {
                $clonedDir = Join-Path $staging 'repo'
                Get-ChildItem -LiteralPath $clonedDir -Force | ForEach-Object {
                    $dst = Join-Path $TargetDir $_.Name
                    if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
                    Move-Item -LiteralPath $_.FullName -Destination $dst -Force
                }
            }
        }
        'tarball' {
            $tarball = Join-Path $staging 'repo.tar.gz'
            Invoke-Step { Invoke-WebRequest -Uri $src.Url -OutFile $tarball }
            if (-not $DryRun) {
                Expand-Archive -Path $tarball -DestinationPath $staging -Force
                $extracted = Get-ChildItem -LiteralPath $staging -Directory | Where-Object { $_.Name -like 'calixto-*' } | Select-Object -First 1
                if ($extracted) {
                    Get-ChildItem -LiteralPath $extracted.FullName -Force | ForEach-Object {
                        $dst = Join-Path $TargetDir $_.Name
                        if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
                        Move-Item -LiteralPath $_.FullName -Destination $dst -Force
                    }
                }
            }
        }
    }

    # Restore user data from backup
    Write-Info "Restoring user data from backup"
    foreach ($item in @('workspaces', 'notes', 'outputs')) {
        $backupItem = Join-Path $backupDir $item
        if (Test-Path $backupItem) {
            $targetItem = Join-Path $TargetDir $item
            Invoke-Step {
                if (Test-Path $targetItem) { Remove-Item $targetItem -Recurse -Force }
                Copy-Item -LiteralPath $backupItem -Destination $targetItem -Recurse -Force
            }
        }
    }

    if (-not $DryRun -and (Test-Path $staging)) {
        Remove-Item $staging -Recurse -Force
    }

    if (-not $SkipDeps -and -not $DryRun) {
        if (Confirm-Action "Run setup.ps1 now to update dependencies?") {
            Write-Section "Running setup.ps1"
            $setupPath = Join-Path $TargetDir 'setup.ps1'
            if (Test-Path $setupPath) {
                & pwsh -ExecutionPolicy Bypass -File $setupPath
            }
        }
    }

    Write-Section "Update complete"
    Write-Info "Backup preserved at: $backupDir"
    Write-Info "To start: cd $TargetDir ; python scripts\init_workspace.py my-research"
}

# =================================================================
# Main
# =================================================================
Write-Section "Calixto Research Workspace installer"
Write-Info "Target: $TargetDir"

if (Test-Workspace) {
    Invoke-UpdateWorkspace
} else {
    Invoke-FreshInstall
}
