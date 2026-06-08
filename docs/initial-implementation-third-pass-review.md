# Initial Implementation Third-Pass Review

Date: 2026-06-07
Branch: `master`
Reviewed commit: `a465b00` plus current working-tree changes
Baseline review: `docs/initial-implementation-second-pass-review.md`

## Part 1: Assessment

The claimed second-pass completion is not present in the implementation. There is no implementation commit after `a465b00`, and the only working-tree code change is in `tests/unit/test_golden_runner.py`. All six actionable implementation findings from the second-pass report remain unchanged.

The test-only change does shorten workspace names, but the full suite still fails and the new teardown introduces a broad deletion pattern that can remove unrelated historical golden runs. The implementation remains not merge-ready.

### Second-Pass Finding Status

| Second-pass finding | Third-pass status |
|---|---|
| Stop invoking Bash builtins through `sh -c` | Not fixed |
| Verify `ddgs`, not `duckduckgo_search` | Not fixed |
| Restore golden-cache compatibility and arXiv cache writes | Not fixed |
| Preserve config files during installer update | Not fixed |
| Repair golden-run regression tests | Not fixed; new teardown errors added |
| Emit error status on failed golden comparison | Not fixed |

### Validation Performed

| Command | Outcome |
|---|---|
| `python -m pytest -q` | Failed: 1 failed, 115 passed, 3 skipped, 2 teardown errors |
| `python tests/validate_skills.py` | Passed |
| `python tests/golden/run.py --use-cache` | Could not complete in sandbox because workspace creation was denied; all four configured cache keys independently confirmed missing |
| `python tests/golden/compare.py examples/sample-workspace examples/sample-workspace --strict` | Exited 1 while still emitting top-level `"status": "ok"` |
| PowerShell parser checks for `install.ps1` and `setup.ps1` | Passed |

## Part 2: Actionable Fixes

### 1. Fix the Unix installer instead of only changing its tests

Severity: Critical

The Unix installer still invokes Bash-only `shopt` through `sh -c` and hides failures with `|| true`. Fresh install and update mode remain broken on common systems where `/bin/sh` is not Bash.

Evidence: `install.sh:182`, `install.sh:183`, `install.sh:190`, `install.sh:191`, `install.sh:282`, `install.sh:288`.

Required fix:

- Replace these commands with Bash-native, failure-checked copy/move logic.
- Run the existing installer integration tests in Linux CI instead of skipping them on Windows-only validation.

### 2. Fix clean setup verification and native-command failure handling

Severity: High

Both setup scripts still install `ddgs` but verify the undeclared legacy module `duckduckgo_search`.

PowerShell setup also runs `uv sync` inside `try/catch` without checking `$LASTEXITCODE`. Native executable nonzero exits do not reliably throw PowerShell exceptions, so setup can print `"Python dependencies installed"` after `uv sync` fails.

Evidence: `setup.sh:50`, `setup.sh:69`; `setup.ps1:80`, `setup.ps1:82`, `setup.ps1:114`; `pyproject.toml:25`.

Required fix:

- Verify `import ddgs`.
- Check `$LASTEXITCODE` after every required native command.
- Add a clean-environment setup test.

### 3. Fix the unchanged golden-cache workflow

Severity: High

All four cache keys needed by `tests/golden/config.json` are still absent after the cache-key migration. Live arXiv searches still only save cache entries inside the unreachable `if use_cache` branch. Both web and arXiv cached modes still initialize providers before reading cache files.

Evidence: `scripts/search_web.py:291`; `scripts/search_arxiv.py:151`, `scripts/search_arxiv.py:217`; `tests/golden/cache/`.

Required fix:

- Migrate/regenerate committed cache files.
- Save successful live arXiv results unconditionally.
- Read cache before initializing providers.
- Add a passing end-to-end committed-cache test.

### 4. Preserve config files during both update installers

Severity: High

Unix still backs up root `config.json` and `*.local` files without restoring them. Windows still promises config preservation without backing up or restoring config files.

Evidence: `install.sh:261`, `install.sh:268`, `install.sh:294`; `install.ps1:194`, `install.ps1:205`, `install.ps1:251`.

Required fix:

- Define, back up, and restore the same user-owned config set on Unix and Windows.
- Add update integration tests that prove modified config survives.

### 5. Do not delete unrelated golden-run history from test teardown

Severity: High

The new teardown loops over every directory under `tests/golden/runs/` and deletes any directory whose name begins with `2026`. This can destroy unrelated historical benchmark runs and violates the cleanup rule to never remove user-provided or unrelated data.

The teardown currently raises `NameError` because `shutil` was not imported, but adding the missing import would activate the dangerous deletion.

Evidence: `tests/unit/test_golden_runner.py:87`, `tests/unit/test_golden_runner.py:103`.

Required fix:

- Track the exact workspace and archive paths created by each test.
- Delete only those exact paths.
- Run integration tests in a temporary repository root rather than the real repository.

### 6. Make golden-run regression tests isolated and repeatable

Severity: Medium

The modified partial-failure tests still use deterministic workspace names in the real repository. A previous failed run leaves those workspaces behind, causing later runs to fail with `workspace_exists` before reaching the behavior being tested. Debug prints also remain in the test.

Evidence: `tests/unit/test_golden_runner.py:151`, `tests/unit/test_golden_runner.py:160`, `tests/unit/test_golden_runner.py:203`; leftover `workspaces/fail-test-child-search-failure-prod0` and `workspaces/preserve-test-partial-workspace-is-pres0`.

Required fix:

- Use a temporary repository root or a unique safe slug.
- Ensure cleanup is exact and reliable even after assertion failures.
- Remove debug output.

### 7. Emit structured error JSON when comparison fails

Severity: Medium

The comparator remains unchanged: it exits 1 but emits `"status": "ok"` to stdout through `emit_ok()`.

Evidence: `tests/golden/compare.py:349`, `tests/golden/compare.py:354`, `tests/golden/compare.py:366`.

Required fix:

- Emit `"status": "error"` to stderr on failed comparison while preserving metrics and findings.

### 8. Do not report installer completion after setup failure

Severity: Medium

Both fresh installers treat dependency setup failure as a warning and then report installation complete. A user can receive a successful installer outcome even though the required environment is unusable.

Evidence: `install.sh:223`, `install.sh:227`; `install.ps1:166`, `install.ps1:168`, `install.ps1:173`.

Required fix:

- Return nonzero when setup fails, or explicitly emit a structured partial-install result that automation can detect.

## Review Verdict

Not merge-ready. The prior implementation findings remain unresolved, the full suite fails, and the only new working-tree change introduces a potentially destructive cleanup pattern. The next fix pass must modify the implementation itself and demonstrate a clean, repeatable validation run.
