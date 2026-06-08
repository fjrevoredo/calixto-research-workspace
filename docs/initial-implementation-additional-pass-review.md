# Initial Implementation Additional-Pass Review

Date: 2026-06-08  
Branch: current branch  
Reviewed state: commit `1ae24dc` plus the current working tree

## Part 1: Assessment

The final-final findings are fixed in the current implementation:

- Windows fallback extraction now uses `tar -xzf`.
- Branch and tag archive URLs are distinguished.
- JSON caches for newly added providers are visible to git.
- Real archive-fallback test paths were added for Unix and Windows.

The isolated test suite and cached golden run pass. The implementation is still not merge-ready because configurable repository fallback mode only works for archives whose extracted root begins with `calixto-`, and the new end-to-end fallback tests skip in the declared development environment.

## Part 2: Actionable Fixes

### 1. Discover the extracted archive root instead of requiring `calixto-*`

Severity: High

Both installers advertise configurable repository sources through `CALIXTO_REPO_URL` / `-RepoUrl`, and fallback URL generation now accepts arbitrary GitHub-style hosts and repositories. However, extraction still only recognizes directories named `calixto-*`:

- `install.sh:314` and `install.sh:440`
- `install.ps1:272` and `install.ps1:384`

GitHub names an archive's root after the repository. A fork or custom repository such as `fake-org/fake-repo` extracts to a root such as `fake-repo-main`, not `calixto-main`. The installer therefore downloads and extracts the archive successfully, then reports that no expected directory exists.

The new fallback tests mask this defect by configuring a fake repository URL while deliberately building an archive rooted at `calixto-<version>`.

Suggested fix:

- Discover the single extracted top-level directory without relying on the repository name.
- Exclude known staging artifacts such as `repo.tar.gz`.
- Fail if zero or multiple candidate directories exist.

Tests to add:

- Fresh and update fallback tests where `RepoUrl` is `fake-org/fake-repo` and the archive root is `fake-repo-main`.
- Equivalent tests for the default `calixto` repository.

### 2. Make archive-fallback integration tests run in the declared dev environment

Severity: Medium

The new Unix and Windows archive-fallback tests generate HTTPS certificates with `cryptography`, but `cryptography` is not listed in the project or development dependencies. In the current normal test environment:

```text
SKIPPED [2] tests/unit/test_install_windows.py: cryptography is required
```

All Unix installer integration tests are also skipped on Windows. As a result, neither archive fallback implementation is executed by the full suite on this host, even though those paths are the focus of the latest fixes.

`tests/unit/gen_test_cert.py` says generated certificate files will be committed, but the certificate and key are not present; the script itself is currently untracked.

Suggested fix:

- Add `cryptography` to development dependencies, or commit a dedicated test certificate/key fixture.
- Ensure CI includes at least one Unix job and one Windows job where the fallback end-to-end tests run rather than skip.
- Fail CI when all tests for a required installer path are skipped.

### 3. Add rollback for partially applied toolkit updates

Severity: Medium

Both update implementations destructively replace toolkit-owned top-level entries one at a time:

- Unix removes the existing destination before moving each staged entry at `install.sh:211-213`.
- Windows removes the existing destination before moving each staged entry at `install.ps1:374-375` and `install.ps1:396-397`.

Only user data and config are backed up. If a permission, disk, antivirus, or filesystem error occurs after replacement starts, the installer exits with a partially updated toolkit and has no rollback source for removed toolkit files.

This falls short of the plan's requirement to back up the current state and its description of the installer as extremely safe and idempotent.

Suggested fix:

- Keep the existing toolkit entries in a rollback staging directory until the full replacement validates successfully.
- On failure, restore replaced entries before exiting.
- Alternatively, assemble a complete sibling tree and atomically swap it into place where the platform permits.

Tests to add:

- Inject a failure after several top-level replacements and verify the original toolkit is restored.
- Verify user data and repository metadata remain unchanged during rollback.

### 4. Separate fresh-install and update protection rules on Unix

Severity: Low

The Unix `move_staging_contents` helper uses the same protected-entry list for fresh installs and updates. `config.json` is protected at `install.sh:163`, so a future root-level toolkit `config.json`, or one supplied by a custom source, will be silently omitted from a fresh installation.

Windows fresh-install mode copies all staged files and only applies protected-entry rules during update, which is the safer distinction.

Suggested fix:

- Apply protected-entry filtering only during updates.
- For fresh installs into a verified empty target, copy every staged repository file except `.git` if excluding repository metadata is intentional.

## Validation Results

- Isolated current working tree: full `python -m pytest -q` passed, with installer fallback tests skipped.
- Isolated current working tree: `python tests/golden/run.py --use-cache` passed with 18 sources and no failed searches.
- Current working directory full suite: two sandbox-only failures caused by git dubious-ownership protection.
- Windows installer tests: three passed, two archive-fallback tests skipped due missing `cryptography`.
- Unix installer tests: all skipped because the current host is Windows.
- Git Bash syntax checks for `install.sh` and `setup.sh`: passed.
- PowerShell parser check for `install.ps1`: passed.
- `git diff --check`: passed aside from line-ending warnings.

## Review Verdict

Not merge-ready. Fix archive-root discovery for configurable repositories and ensure the archive fallback integration tests actually run in CI. Add rollback protection before describing update mode as extremely safe.
