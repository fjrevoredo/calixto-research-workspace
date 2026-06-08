# Initial Implementation Final-Final Review

Date: 2026-06-08  
Branch: current branch  
Reviewed state: commit `1ae24dc` plus the current working tree

## Part 1: Assessment

All four findings from the final review are fixed in the current working tree:

- The Windows git-update path preserves the existing `.git` directory.
- The Unix fresh-install tarball lookup is anchored to `TARGET_DIR`.
- Unix fresh installs and updates now install the toolkit `.gitignore`.
- Future cache files for the existing `duckduckgo` and `arxiv` providers are visible to git.

The isolated working-tree test suite and cached golden run pass. However, the implementation is still not merge-ready because the Windows tarball fallback is unusable, and the fallback/version behavior remains materially under-tested.

## Part 2: Actionable Fixes

### 1. Extract Windows `.tar.gz` fallbacks with a compatible tool

Severity: High

Both Windows fallback paths download a GitHub `.tar.gz` archive and pass it to `Expand-Archive`:

- `install.ps1:168-172` in fresh-install mode
- `install.ps1:242-246` in update mode

PowerShell `Expand-Archive` supports ZIP archives, not gzip-compressed tar archives. A direct validation using the installed PowerShell 7 executable and a valid `.tar.gz` returned exit code 1. Therefore, when Git is unavailable and `Get-RepoSource` selects tarball mode, both fresh installation and update fail during extraction.

Suggested fix:

- Use `tar -xzf` when available, or download GitHub's ZIP archive and keep `Expand-Archive`.
- Check extraction command exit status and fail with a specific diagnostic.
- Do not describe tarball mode as a fallback until an end-to-end fallback test passes.

Tests to add:

- Windows fresh installation succeeds with Git unavailable.
- Windows update succeeds with Git unavailable and preserves `.git` and user data.

### 2. Generate correct archive URLs for version tags

Severity: Medium

Both installers treat `CALIXTO_VERSION` / `-Version` as a version selector, but their tarball fallback always builds a branch URL:

- `install.sh:228-236`
- `install.ps1:123-125`

For a tagged version, GitHub's archive URL uses `archive/refs/tags/<version>.tar.gz`, not `archive/refs/heads/<version>.tar.gz`. Version-pinned installation therefore fails whenever Git is unavailable.

Suggested fix:

- Define whether version values are tags, arbitrary refs, or branches.
- Build the corresponding GitHub archive URL, or use a commit/archive endpoint that accepts the documented ref format.
- Add tests for a branch install and a tagged-version install through fallback mode.

### 3. Do not silently ignore cache files for newly integrated providers

Severity: Medium

The revised `.gitignore` correctly exposes new JSON cache files under the existing `arxiv` and `duckduckgo` directories. It still ignores cache files under any newly added provider directory:

```text
git check-ignore tests/golden/cache/newprovider/abc.json
tests/golden/cache/newprovider/abc.json
```

This conflicts with the `.gitignore` comment claiming that a new provider's cache files can be tracked without editing `.gitignore`, and it creates a reproducibility trap when the pluggable provider system is extended. The new test explicitly treats this ignored state as expected instead of enforcing the stated versioning policy.

Suggested fix:

- Stop ignoring provider cache JSON generally, or adopt an allow-all-JSON rule under `tests/golden/cache/`.
- Ignore only temporary/non-JSON artifacts.
- Update the test to require a hypothetical new provider JSON cache file to be visible to git.

### 4. Replace copied/static installer tests with real fallback integration tests

Severity: Medium

The new Unix tarball test does not execute the installer fallback. `test_fresh_install_tarball_fallback_uses_target_relative_lookup` unconditionally skips, while `test_tarball_extraction_uses_target_relative_lookup` copies the relevant shell snippet into the test. It can pass when another part of the actual fallback path is broken.

The Windows protected-entry behavior test similarly redefines `Test-ProtectedEntry` in the test process rather than exercising the function loaded from `install.ps1`. Static occurrence checks do not validate update behavior.

This gap allowed the incompatible Windows `Expand-Archive` call to remain undetected even though tarball behavior was part of the claimed fix.

Suggested fix:

- Serve a fixture archive from a local HTTP server and execute each installer end to end with Git hidden from `PATH`.
- Execute actual fresh and update paths rather than copied snippets or redefined helper functions.
- Assert final filesystem state, exit code, preserved user data, and preserved repository metadata.

## Validation Results

- Isolated current working tree: full `python -m pytest -q` passed.
- Isolated current working tree: `python tests/golden/run.py --use-cache` passed with 18 sources and no failed searches.
- Actual Windows git-update integration exercise: passed; `.git/HEAD` and a sentinel metadata file were preserved.
- Direct PowerShell `.tar.gz` extraction check: failed, confirming the Windows fallback defect.
- `python tests/validate_skills.py`: passed.
- Git Bash syntax checks for `install.sh` and `setup.sh`: passed.
- PowerShell parser checks for `install.ps1` and `setup.ps1`: passed.
- `git diff --check`: passed, aside from line-ending warnings.
- Full suite in the original working directory reported two failures because sandbox git ownership protection blocked subprocess git calls; the same tests passed in the isolated owned checkout.

## Review Verdict

Not merge-ready. The main implementation is in strong shape, but the advertised Windows no-Git fallback is broken. Fix and genuinely integration-test the archive fallback paths before release.
