# install.ps1: one-liner installer for Calixto Research Workspace.
#
# Fresh install and update intentionally use different safety rules:
# - fresh install copies the whole toolkit into a verified empty directory
# - update preserves user-owned data, repo metadata, and unknown files unless
#   managed-entry metadata proves the toolkit owns them

[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$NonInteractive,
    [switch]$SkipDeps,
    [string]$Version = $env:CALIXTO_VERSION,
    [string]$RepoUrl = $(if ($env:CALIXTO_REPO_URL) {
        $env:CALIXTO_REPO_URL
    } else {
        'https://github.com/calixto/calixto.git'
    }),
    [string]$Branch = $(if ($env:CALIXTO_REPO_BRANCH) {
        $env:CALIXTO_REPO_BRANCH
    } else {
        'main'
    })
)

$ErrorActionPreference = 'Stop'

$TargetDir = (Get-Location).Path
$TestMode = $env:CALIXTO_TEST_MODE -eq '1'
$TestArchiveUrl = $env:CALIXTO_TEST_ARCHIVE_URL
$TestCaCert = $env:CALIXTO_TEST_CA_CERT
$BranchExplicit = $PSBoundParameters.ContainsKey('Branch') -or [bool]$env:CALIXTO_REPO_BRANCH
$BackupDir = $null

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

function Write-Section { param($Message) Write-Host "`n=== $Message ===" -ForegroundColor Cyan }
function Write-Info { param($Message) Write-Host "  -> $Message" -ForegroundColor Gray }
function Write-Warn { param($Message) Write-Host "  !! $Message" -ForegroundColor Yellow }
function Write-Fail { param($Message) Write-Host "  XX $Message" -ForegroundColor Red; exit 1 }

function Invoke-Python {
    param([string[]]$Arguments)
    if (Get-Command python -ErrorAction SilentlyContinue) {
        & python @Arguments
        return
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 @Arguments
        return
    }
    Write-Fail "Python 3.11+ is required to run the installer."
}

function Confirm-Action {
    param([string]$Prompt)
    if ($NonInteractive) {
        Write-Info "[non-interactive] auto-confirming: $Prompt"
        return $true
    }
    if ($DryRun) {
        Write-Host "   [dry-run] would prompt: $Prompt"
        return $true
    }
    $response = Read-Host "  $Prompt (y/n)"
    return $response -in @('y', 'Y', 'yes', 'YES')
}

function Test-Workspace {
    foreach ($marker in $WorkspaceMarkers) {
        if (-not (Test-Path -LiteralPath (Join-Path $TargetDir $marker))) {
            return $false
        }
    }
    return $true
}

function Get-SelectedRef {
    if ($Version) {
        return $Version
    }
    return $Branch
}

function Validate-SelectorContract {
    if ($Version -and $BranchExplicit) {
        Write-Fail "Specify either -Branch or -Version, not both."
    }
    if ($env:CALIXTO_TEST_FAIL_AFTER_REPLACEMENTS -and -not $TestMode) {
        Write-Fail "CALIXTO_TEST_FAIL_AFTER_REPLACEMENTS requires CALIXTO_TEST_MODE=1."
    }
    if ($TestArchiveUrl -and -not $TestMode) {
        Write-Fail "CALIXTO_TEST_ARCHIVE_URL requires CALIXTO_TEST_MODE=1."
    }
    if ($TestCaCert -and -not $TestMode) {
        Write-Fail "CALIXTO_TEST_CA_CERT requires CALIXTO_TEST_MODE=1."
    }
}

function Normalize-RepoUrl {
    param([string]$Url)
    if ($Url -notmatch '^https://github\.com/[^/]+/[^/]+(?:\.git)?/?$') {
        Write-Fail "Repo URL must be https://github.com/<owner>/<repo> (optionally ending in .git)."
    }
    return $Url.TrimEnd('/')
}

function Get-ArchiveBaseUrl {
    $normalized = Normalize-RepoUrl $RepoUrl
    return $normalized -replace '\.git$', ''
}

function Get-RepoSource {
    $ref = Get-SelectedRef
    if ($TestArchiveUrl) {
        return @{ Mode = 'tarball'; Url = $TestArchiveUrl }
    }
    if (Get-Command git -ErrorAction SilentlyContinue) {
        if ($TestMode) {
            return @{ Mode = 'git'; Url = $RepoUrl; Ref = $ref }
        }
        return @{ Mode = 'git'; Url = (Normalize-RepoUrl $RepoUrl); Ref = $ref }
    }
    $base = Get-ArchiveBaseUrl
    if ($Version) {
        return @{ Mode = 'tarball'; Url = "$base/archive/refs/tags/$Version.tar.gz" }
    }
    return @{ Mode = 'tarball'; Url = "$base/archive/refs/heads/$Branch.tar.gz" }
}

function Download-File {
    param(
        [Parameter(Mandatory)] [string] $Url,
        [Parameter(Mandatory)] [string] $Destination
    )
    if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
        Write-Fail "curl.exe is required to download installer archives."
    }
    $curlArgs = @('-sSLf')
    if ($TestCaCert) {
        $curlArgs += @('--cacert', $TestCaCert)
    }
    $curlArgs += @('-o', $Destination, $Url)
    & curl.exe @curlArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "curl download failed (rc=$LASTEXITCODE) for $Url."
    }
}

function Expand-ArchiveSource {
    param(
        [Parameter(Mandatory)] [string] $Url,
        [Parameter(Mandatory)] [string] $StagingDirectory
    )
    $archivePath = Join-Path $StagingDirectory 'repo.tar.gz'
    Download-File -Url $Url -Destination $archivePath
    $pyCode = @'
import os
import posixpath
import re
import sys
import tarfile
from pathlib import Path

archive = Path(sys.argv[1])
staging = Path(sys.argv[2]).resolve(strict=False)

def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)

def normalize_member(name: str) -> str:
    if not name:
        fail("Archive contains an empty member name.")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in name):
        fail(f"Archive member contains control characters: {name!r}")
    normalized = posixpath.normpath(name)
    if normalized in {".", ""}:
        fail(f"Archive member is not a real path: {name!r}")
    if normalized.startswith("/") or normalized.startswith("\\"):
        fail(f"Archive member uses an absolute path: {name!r}")
    if normalized == ".." or normalized.startswith("../"):
        fail(f"Archive member escapes staging via '..': {name!r}")
    if re.match(r"^[A-Za-z]:", normalized):
        fail(f"Archive member uses a drive-qualified path: {name!r}")
    return normalized

with tarfile.open(archive, "r:gz") as tf:
    members = tf.getmembers()
    if not members:
        fail("Archive is empty.")
    for member in members:
        normalized = normalize_member(member.name)
        if member.issym() or member.islnk():
            link_target = member.linkname or ""
            if not link_target:
                fail(f"Archive link has no target: {member.name!r}")
            normalized_target = posixpath.normpath(
                posixpath.join(posixpath.dirname(normalized), link_target)
            )
            if normalized_target.startswith("/") or normalized_target.startswith("\\"):
                fail(
                    f"Archive link escapes staging via absolute target: "
                    f"{member.name!r} -> {link_target!r}"
                )
            if normalized_target == ".." or normalized_target.startswith("../"):
                fail(
                    f"Archive link escapes staging: "
                    f"{member.name!r} -> {link_target!r}"
                )
            if re.match(r"^[A-Za-z]:", normalized_target):
                fail(
                    f"Archive link uses a drive-qualified target: "
                    f"{member.name!r} -> {link_target!r}"
                )
    tf.extractall(staging)

candidates = []
for child in staging.iterdir():
    if child.name == archive.name:
        continue
    if child.is_dir():
        resolved = child.resolve(strict=False)
        try:
            resolved.relative_to(staging)
        except ValueError:
            fail(f"Extracted directory escapes staging: {child}")
        candidates.append(resolved)

if len(candidates) != 1:
    fail(
        "Archive extraction must produce exactly one top-level directory; "
        f"found {len(candidates)} candidates."
    )

print(str(candidates[0]))
'@
    $output = Invoke-Python -Arguments @('-c', $pyCode, $archivePath, $StagingDirectory) 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Fail ($output -join [Environment]::NewLine)
    }
    return ($output | Select-Object -Last 1).Trim()
}

function Copy-InstallerCore {
    param(
        [Parameter(Mandatory)] [string] $SourceRoot,
        [Parameter(Mandatory)] [string] $StagingDirectory
    )
    $coreSource = Join-Path $SourceRoot 'scripts/installer_core.py'
    $coreCopy = Join-Path $StagingDirectory 'installer-core.py'
    if (-not (Test-Path -LiteralPath $coreSource)) {
        Write-Fail "Downloaded source is missing scripts/installer_core.py."
    }
    Copy-Item -LiteralPath $coreSource -Destination $coreCopy -Force
    return $coreCopy
}

function Invoke-InstallerCore {
    param(
        [Parameter(Mandatory)] [string] $CoreScript,
        [Parameter(Mandatory)] [string[]] $Arguments
    )
    $allArguments = @($CoreScript) + $Arguments
    Invoke-Python -Arguments $allArguments
    return $LASTEXITCODE
}

function Cleanup-Path {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

function New-StagingDirectory {
    $path = Join-Path ([System.IO.Path]::GetTempPath()) ("calixto-install-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $path -Force | Out-Null
    return $path
}

function Invoke-SetupIfRequested {
    param([string]$Context)
    if ($SkipDeps -or $DryRun) {
        return
    }
    $setupPath = Join-Path $TargetDir 'setup.ps1'
    if (-not (Test-Path -LiteralPath $setupPath)) {
        return
    }
    Write-Section "Running setup.ps1"
    try {
        & $setupPath
    } catch {
        Write-Fail "setup.ps1 failed during $Context. Toolkit files are present, but the environment is not ready."
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "setup.ps1 failed during $Context. Toolkit files are present, but the environment is not ready."
    }
}

function Backup-UserData {
    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $script:BackupDir = Join-Path $TargetDir ".calixto-backup-$timestamp"
    Write-Info "Backing up user data to $script:BackupDir"
    New-Item -ItemType Directory -Path $script:BackupDir -Force | Out-Null
    foreach ($item in @('workspaces', 'notes', 'outputs', 'config.json')) {
        $source = Join-Path $TargetDir $item
        if (Test-Path -LiteralPath $source) {
            Copy-Item -LiteralPath $source -Destination $script:BackupDir -Recurse -Force
        }
    }
    Get-ChildItem -LiteralPath $TargetDir -File -Filter '*.local' -ErrorAction SilentlyContinue |
        ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $script:BackupDir -Force
        }
}

function Invoke-FreshInstall {
    Write-Section "Mode: fresh install"
    Write-Info "Target directory: $TargetDir"
    Write-Info "Repository: $RepoUrl"

    $existing = Get-ChildItem -LiteralPath $TargetDir -Force -ErrorAction SilentlyContinue
    if ($existing.Count -gt 0) {
        Write-Fail "Target directory is not empty. Use a new directory for fresh install."
    }

    if (-not (Confirm-Action "This will install Calixto Research Workspace into '$TargetDir'. Continue?")) {
        Write-Info "Installation cancelled."
        exit 0
    }

    $src = Get-RepoSource
    Write-Info "Source: $($src.Mode):$($src.Url)"

    if ($DryRun) {
        Write-Host "   [dry-run] would fetch source into a staging directory and apply a fresh install"
        exit 0
    }

    $staging = New-StagingDirectory

    $sourceRoot = $null
    switch ($src.Mode) {
        'git' {
            & git clone --depth 1 --branch $src.Ref $src.Url (Join-Path $staging 'repo')
            if ($LASTEXITCODE -ne 0) {
                Cleanup-Path $staging
                Write-Fail "git clone failed during fresh install."
            }
            $sourceRoot = Join-Path $staging 'repo'
        }
        'tarball' {
            $sourceRoot = Expand-ArchiveSource -Url $src.Url -StagingDirectory $staging
        }
        default {
            Cleanup-Path $staging
            Write-Fail "Unknown source mode: $($src.Mode)"
        }
    }

    $coreScript = Copy-InstallerCore -SourceRoot $sourceRoot -StagingDirectory $staging
    $exitCode = Invoke-InstallerCore -CoreScript $coreScript -Arguments @(
        'apply-fresh',
        '--source-root', $sourceRoot,
        '--target-dir', $TargetDir
    )
    if ($exitCode -ne 0) {
        Write-Warn "Fresh install failed. Staging preserved at $staging for inspection."
        exit $exitCode
    }

    Cleanup-Path $staging
    Invoke-SetupIfRequested -Context 'fresh install'

    Write-Section "Fresh install complete"
    Write-Info "To start: cd $TargetDir ; python scripts\init_workspace.py my-research"
}

function Invoke-UpdateWorkspace {
    Write-Section "Mode: workspace update"
    Write-Info "Target directory: $TargetDir"
    Write-Info "Repository: $RepoUrl"

    $missing = @()
    foreach ($marker in $WorkspaceMarkers) {
        if (-not (Test-Path -LiteralPath (Join-Path $TargetDir $marker))) {
            $missing += $marker
        }
    }
    if ($missing.Count -gt 0) {
        Write-Fail "Directory looks like a partial Calixto workspace. Missing: $($missing -join ', ')."
    }

    if (-not (Confirm-Action "This will update Calixto Research Workspace in '$TargetDir'. Continue?")) {
        Write-Info "Update cancelled."
        exit 0
    }

    $src = Get-RepoSource
    Write-Info "Source: $($src.Mode):$($src.Url)"

    if ($DryRun) {
        Write-Host "   [dry-run] would fetch source, validate it, create a backup, and apply an update transaction"
        exit 0
    }

    $staging = New-StagingDirectory

    $sourceRoot = $null
    switch ($src.Mode) {
        'git' {
            & git clone --depth 1 --branch $src.Ref $src.Url (Join-Path $staging 'repo')
            if ($LASTEXITCODE -ne 0) {
                Cleanup-Path $staging
                Write-Fail "git clone failed during update."
            }
            $sourceRoot = Join-Path $staging 'repo'
        }
        'tarball' {
            $sourceRoot = Expand-ArchiveSource -Url $src.Url -StagingDirectory $staging
        }
        default {
            Cleanup-Path $staging
            Write-Fail "Unknown source mode: $($src.Mode)"
        }
    }

    $coreScript = Copy-InstallerCore -SourceRoot $sourceRoot -StagingDirectory $staging
    $recoverExitCode = Invoke-InstallerCore -CoreScript $coreScript -Arguments @(
        'recover-transaction',
        '--target-dir', $TargetDir
    )
    if ($recoverExitCode -ne 0) {
        Cleanup-Path $staging
        exit $recoverExitCode
    }

    Backup-UserData

    $updateExitCode = Invoke-InstallerCore -CoreScript $coreScript -Arguments @(
        'apply-update',
        '--source-root', $sourceRoot,
        '--target-dir', $TargetDir
    )
    if ($updateExitCode -ne 0) {
        Cleanup-Path $staging
        exit $updateExitCode
    }

    Cleanup-Path $staging

    if (-not $SkipDeps) {
        if (Confirm-Action "Run setup.ps1 now to update dependencies?") {
            Invoke-SetupIfRequested -Context 'update'
        }
    }

    Write-Section "Update complete"
    Write-Info "Backup preserved at: $BackupDir"
    Write-Info "To start: cd $TargetDir ; python scripts\init_workspace.py my-research"
}

Validate-SelectorContract

Write-Section "Calixto Research Workspace installer"
Write-Info "Target: $TargetDir"

if (Test-Workspace) {
    Invoke-UpdateWorkspace
} else {
    Invoke-FreshInstall
}
