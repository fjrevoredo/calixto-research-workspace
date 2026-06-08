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
    # -Version is treated as a git tag (e.g. v0.1.0). It produces
    # the archive URL archive/refs/tags/<Version>.tar.gz in
    # tarball fallback mode. -Branch is treated as a branch name
    # and produces archive/refs/heads/<Branch>.tar.gz. -Ref is an
    # advanced escape hatch for an arbitrary ref; it short-circuits
    # the branch/tag distinction in the URL builder.
    [string]$Version = $env:CALIXTO_VERSION,
    [string]$RepoUrl = $(if ($env:CALIXTO_REPO_URL) { $env:CALIXTO_REPO_URL } else { 'https://github.com/calixto/calixto.git' }),
    [string]$Branch = $(if ($env:CALIXTO_REPO_BRANCH) { $env:CALIXTO_REPO_BRANCH } else { 'main' }),
    [string]$Ref = $env:CALIXTO_REF
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

# Entries that must NEVER be replaced when moving staged content
# into a target directory. These are user-owned data (workspaces,
# notes, outputs), repository metadata (.git) that would lose its
# history, and toolkit-owned config (config.json) that may carry
# user overrides. The list mirrors the Unix installer's
# TOOLKIT_PROTECTED_NAMES array; both lists MUST stay in sync
# because the same data-integrity hazards exist on each platform.
$ProtectedEntries = @(
    '.git',
    'workspaces',
    'notes',
    'outputs',
    'config.json'
)

# Test whether a top-level entry name is protected. Used by the
# update loops below to skip data and metadata that the staged
# copy must not overwrite.
function Test-ProtectedEntry {
    param([string]$Name)
    foreach ($p in $ProtectedEntries) {
        if ($Name -eq $p) { return $true }
    }
    return $false
}

function Write-Section { param($m) Write-Host "`n=== $m ===" -ForegroundColor Cyan }
function Write-Info    { param($m) Write-Host "  -> $m" -ForegroundColor Gray }
function Write-Warn    { param($m) Write-Host "  !! $m" -ForegroundColor Yellow }
function Write-Fail    { param($m) Write-Host "  XX $m" -ForegroundColor Red; exit 1 }

# Extract a gzipped tar archive at $Tarball into $Destination.
# We use `tar.exe` (shipped with Windows 10 1803+ as part of
# libarchive, and on every supported Unix), not PowerShell's
# Expand-Archive, because Expand-Archive only handles ZIP and
# silently returns exit 1 on a `.tar.gz`. The gitHub codeload
# archives we fetch are `.tar.gz`, so Expand-Archive would make
# the tarball fallback unusable on Windows.
#
# The function checks $LASTEXITCODE after the call because
# PowerShell try/catch does not reliably catch native
# executable nonzero exits, as documented in setup.ps1.
function Expand-TarGz {
    param(
        [Parameter(Mandatory)] [string] $Tarball,
        [Parameter(Mandatory)] [string] $Destination
    )
    $tar = Get-Command tar -ErrorAction SilentlyContinue
    if (-not $tar) {
        Write-Fail "Cannot extract tarball: 'tar' is not on PATH. Install Windows 10 1803+ (which ships tar.exe) or install Git for Windows, then re-run."
    }
    & tar -xzf $Tarball -C $Destination
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "tar -xzf failed (rc=$LASTEXITCODE) for $Tarball. The archive may be corrupt or in an unsupported format."
    }
}

# Download $Url to $Destination using curl.exe (bundled with
# Windows 10 1803+). We avoid `Invoke-WebRequest` because it
# has a long-standing bug ("Cannot determine the frame size or
# a corrupted frame was received") when fetching from a localhost
# HTTP server on some PowerShell versions; curl.exe does not
# have this problem. As a secondary benefit, the installer
# becomes a uniform script across platforms: the Unix and
# Windows installers both invoke `curl` for tarball downloads.
function Download-File {
    param(
        [Parameter(Mandatory)] [string] $Url,
        [Parameter(Mandatory)] [string] $Destination
    )
    $curl = Get-Command curl -ErrorAction SilentlyContinue
    if (-not $curl) {
        # Use a here-string to avoid the PowerShell parser
        # misinterpreting $Url: as a scope-qualified variable
        # inside a double-quoted string.
        $msg = @"
Cannot download ${Url}: 'curl' is not on PATH. Install Windows 10 1803+ (which ships curl.exe) or install Git for Windows, then re-run.
"@
        Write-Fail $msg
    }
    # -s silent, -S show errors, -L follow redirects, -f fail
    # fast on HTTP errors. We use the .exe name explicitly to
    # avoid PowerShell's alias for Invoke-WebRequest. -k skips
    # TLS verification, which is opt-in via CALIXTO_INSECURE_TLS=1
    # for air-gapped environments that use a self-signed tarball
    # host (and is what the integration test suite needs against a
    # localhost fixture). Production usage against github.com does
    # not need -k.
    $extraArgs = @()
    if ($env:CALIXTO_INSECURE_TLS -eq '1') {
        $extraArgs += '-k'
    }
    & curl.exe -sSLf @extraArgs -o $Destination $Url
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "curl download failed (rc=$LASTEXITCODE) for $Url -> $Destination. If the tarball host uses a self-signed certificate, retry with CALIXTO_INSECURE_TLS=1."
    }
}

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
        # -Ref (advanced) overrides everything else. Otherwise
        # -Version is a tag and -Branch is a branch.
        if ($Ref) {
            $ref = $Ref
        } elseif ($Version) {
            $ref = $Version
        } else {
            $ref = $Branch
        }
        return @{ Mode = 'git'; Url = $RepoUrl; Ref = $ref }
    }
    # Tarball fallback. We accept any https URL whose host is
    # github.com (or a github-equivalent like GitHub Enterprise).
    # The GitHub codeload archive path works for github.com and for
    # GitHub Enterprise instances as long as the URL prefix ends
    # in `/<org>/<repo>`. The strict github.com check we used to
    # have here blocked self-hosted GitHub Enterprise and our
    # own integration tests, which need to point at a local HTTP
    # server with a non-github.com URL.
    if ($RepoUrl -notmatch '^https://[^/]+/[^/]+/[^/]+/?$') {
        Write-Fail "Cannot derive tarball URL from: $RepoUrl. URL must look like https://host/org/repo (no .git suffix)."
    }
    $base = $RepoUrl -replace '\.git$', '' -replace '/$', ''
    # The archive path depends on the ref kind:
    #   - refs/heads/<Branch>  for branches (the default)
    #   - refs/tags/<Version>  for tags (e.g. v0.1.0)
    # -Ref is an arbitrary ref name; we use the unprefixed
    # `/archive/<ref>` form, which the codeload server accepts
    # for any ref and which is the most permissive.
    if ($Ref) {
        return @{ Mode = 'tarball'; Url = "$base/archive/$Ref.tar.gz" }
    }
    if ($Version) {
        return @{ Mode = 'tarball'; Url = "$base/archive/refs/tags/$Version.tar.gz" }
    }
    return @{ Mode = 'tarball'; Url = "$base/archive/refs/heads/$Branch.tar.gz" }
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
            Invoke-Step { Download-File -Url $src.Url -Destination $tarball }
            if (-not $DryRun) {
                Expand-TarGz -Tarball $tarball -Destination $staging
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
                # The fresh-install contract is "after this script exits
                # 0, the environment is usable". A failed setup must
                # not leave the user with a "Fresh install complete"
                # message and an unusable environment.
                Write-Fail "setup.ps1 failed (rc=$LASTEXITCODE). Toolkit files are installed at $TargetDir, but the Python environment is not usable. Re-run $TargetDir\setup.ps1 manually to diagnose, or re-run this installer with -SkipDeps to install files without setting up the environment."
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
    foreach ($item in @('workspaces', 'notes', 'outputs', 'config.json')) {
        $src = Join-Path $TargetDir $item
        if (Test-Path $src) {
            $dst = Join-Path $backupDir $item
            Invoke-Step { Copy-Item -LiteralPath $src -Destination $dst -Recurse -Force }
        }
    }
    # Also back up any *.local config overrides at the workspace root.
    Get-ChildItem -LiteralPath $TargetDir -Filter '*.local' -ErrorAction SilentlyContinue |
        ForEach-Object {
            Invoke-Step { Copy-Item -LiteralPath $_.FullName -Destination $backupDir -Force }
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
                # Move each staged entry into the target, EXCEPT the
                # protected names. The staged clone contains a `.git`
                # directory whose metadata (branches, remotes, reflogs,
                # hooks, uncommitted index) we must not clobber on an
                # existing repo. User-owned data and toolkit config
                # (config.json) are also protected; the .local
                # override files and the data dirs are restored from
                # $backupDir further down.
                Get-ChildItem -LiteralPath $clonedDir -Force | ForEach-Object {
                    if (Test-ProtectedEntry $_.Name) {
                        Write-Info "Skipping protected entry from staged clone: $($_.Name)"
                        return
                    }
                    $dst = Join-Path $TargetDir $_.Name
                    if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
                    Move-Item -LiteralPath $_.FullName -Destination $dst -Force
                }
            }
        }
        'tarball' {
            $tarball = Join-Path $staging 'repo.tar.gz'
            Invoke-Step { Download-File -Url $src.Url -Destination $tarball }
            if (-not $DryRun) {
                Expand-TarGz -Tarball $tarball -Destination $staging
                $extracted = Get-ChildItem -LiteralPath $staging -Directory | Where-Object { $_.Name -like 'calixto-*' } | Select-Object -First 1
                if ($extracted) {
                    # Same protection rules as the git path. A tarball
                    # of a toolkit release also contains a `.git` if
                    # the maintainer ships one; we must not clobber
                    # the existing repo's metadata either way.
                    Get-ChildItem -LiteralPath $extracted.FullName -Force | ForEach-Object {
                        if (Test-ProtectedEntry $_.Name) {
                            Write-Info "Skipping protected entry from tarball: $($_.Name)"
                            return
                        }
                        $dst = Join-Path $TargetDir $_.Name
                        if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
                        Move-Item -LiteralPath $_.FullName -Destination $dst -Force
                    }
                }
            }
        }
    }

    # Restore user data from backup. config.json and *.local overrides
    # are restored alongside the data dirs so user-owned config survives
    # the update.
    Write-Info "Restoring user data from backup"
    foreach ($item in @('workspaces', 'notes', 'outputs', 'config.json')) {
        $backupItem = Join-Path $backupDir $item
        if (Test-Path $backupItem) {
            $targetItem = Join-Path $TargetDir $item
            Invoke-Step {
                if (Test-Path $targetItem) { Remove-Item $targetItem -Recurse -Force }
                Copy-Item -LiteralPath $backupItem -Destination $targetItem -Recurse -Force
            }
        }
    }
    Get-ChildItem -LiteralPath $backupDir -Filter '*.local' -ErrorAction SilentlyContinue |
        ForEach-Object {
            Invoke-Step {
                Copy-Item -LiteralPath $_.FullName -Destination $TargetDir -Force
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
                if ($LASTEXITCODE -ne 0) {
                    # User's data is safe (restored from $backupDir) but
                    # the environment is not in a known-good state.
                    Write-Fail "setup.ps1 failed during update (rc=$LASTEXITCODE). Toolkit files were updated and user data restored from $backupDir, but the Python environment is not usable. Re-run $TargetDir\setup.ps1 manually to diagnose, or re-run this installer with -SkipDeps to apply files without touching the environment."
                }
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
