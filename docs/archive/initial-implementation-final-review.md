# Initial Implementation Final Review

Date: 2026-06-08  
Branch: current branch  
Reviewed commit: `1ae24dc`  

## Part 1: Assessment

The fourth-pass fixes substantially improved the implementation. The committed golden caches work from a clean checkout, the clean-checkout test suite passes, setup now verifies a launchable Chromium installation, comparator failures use stderr only, and the documented package verification uses `ddgs`.

The implementation is still not merge-ready. The final pass found a critical Windows update data-integrity issue and three Unix/cache maintenance problems. The most serious issue is that the Windows updater deletes and replaces an existing workspace's `.git` directory.

## Part 2: Actionable Fixes

### 1. Preserve repository metadata during Windows updates

Severity: Critical

In both Windows update source paths, every top-level staged entry is moved into the target after recursively deleting any existing entry with the same name:

- `install.ps1:234-237` for git-clone updates
- `install.ps1:248-251` for tarball updates

A staged git clone contains `.git`, so updating an existing repository deletes its current `.git` directory and replaces it with metadata from a new shallow clone. This loses the repository's branches, remotes, reflogs, hooks, configuration, and uncommitted-index state. It also conflicts with the Unix updater's newly documented invariant that `.git` must never be replaced.

Suggested fix:

- Exclude `.git` from both Windows update loops.
- Centralize the protected-entry rules so git and tarball update paths cannot diverge.
- Add a Windows update integration test that creates recognizable `.git/HEAD`, `.git/config`, and hook files and verifies they remain unchanged.

Tests to add:

- Windows update from a git clone preserves all existing `.git` metadata.
- Windows tarball update preserves all existing `.git` metadata.

### 2. Fix the Unix fresh-install tarball extraction lookup

Severity: High

`install.sh:270` searches for `calixto-*/` relative to the process's current directory, but the tarball is extracted into `TARGET_DIR` at `install.sh:264`. When git is unavailable and the tarball fallback is used from an empty target directory, the extracted directory is not found and the installer fails at `install.sh:275-276`.

The update tarball path correctly searches under `$staging`; the fresh-install path should likewise search under `$TARGET_DIR`.

Suggested fix:

```bash
for entry in "$TARGET_DIR"/calixto-*/; do
    [ -d "$entry" ] || continue
    extracted_dir="$entry"
    break
done
move_staging_contents "$extracted_dir" "$TARGET_DIR"
```

Tests to add:

- Fresh Unix installation succeeds through the tarball fallback when git is unavailable.
- Tarball extraction failure preserves useful diagnostics and exits nonzero.

### 3. Install and update the Unix `.gitignore`

Severity: High

`.gitignore` is included in the global protected-name list at `install.sh:145-151`, and `move_staging_contents` skips protected entries for both fresh installs and updates at `install.sh:176-188`.

Consequences:

- A fresh Unix install silently omits the repository's `.gitignore`, despite the plan requiring all files to be copied.
- Existing Unix workspaces never receive toolkit `.gitignore` updates.
- Users can accidentally commit generated workspaces, environments, or other ignored artifacts.

`.gitignore` is toolkit configuration, not one of the documented user-data entries preserved by the installer. If user customization must be supported, it needs an explicit merge or override policy rather than silently keeping an indefinitely stale file.

Suggested fix:

- Remove `.gitignore` from the global protected list.
- If desired, preserve only documented user-owned ignore overrides in a separate file.
- Add fresh-install and update assertions for the expected `.gitignore` content.

### 4. Make future golden cache files visible to git

Severity: Medium

The existing cache files are committed and the clean cached run succeeds. However, `.gitignore:28` ignores `tests/golden/cache/` as a directory. The later negations at `.gitignore:29-32` cannot re-include files below an ignored parent directory.

Confirmed behavior:

```text
git check-ignore --no-index -v tests/golden/cache/duckduckgo/future-cache.json
.gitignore:28:tests/golden/cache/
```

Future live runs, migrations, or additional providers can create cache files that remain invisible to normal `git status` and are easily omitted from commits. The current clean-checkout test only checks cache files already present on disk, so it does not detect this.

Suggested fix:

```gitignore
tests/golden/cache/*
!tests/golden/cache/arxiv/
!tests/golden/cache/arxiv/*.json
!tests/golden/cache/duckduckgo/
!tests/golden/cache/duckduckgo/*.json
```

Alternatively, stop ignoring golden cache JSON entirely and ignore only temporary cache artifacts.

Tests to add:

- `git check-ignore` confirms a newly named cache JSON file is not ignored.
- A cache directory for a newly supported provider follows the intended versioning policy.

## Validation Results

- Synthetic clean checkout: full `python -m pytest -q` passed.
- Synthetic clean checkout: `python tests/golden/run.py --use-cache` passed with 18 sources and no failed searches.
- Current working tree: all tests except `test_cache_files_are_tracked` passed; that test was blocked by the sandbox's git dubious-ownership protection, not by repository behavior.
- `python tests/validate_skills.py`: passed.
- Strict golden comparison: correctly exited 1 and emitted its structured error to stderr only.
- Existing committed golden cache files are tracked.
- `git diff --check HEAD^..HEAD`: passed.

## Review Verdict

Not merge-ready. Preserve `.git` during Windows updates and correct the Unix installer paths before release. The ineffective future-cache ignore rules should also be fixed so the newly restored reproducibility contract remains maintainable.
