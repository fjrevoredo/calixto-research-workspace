# Initial Implementation Second-Pass Review

Date: 2026-06-07
Branch: `master`
Reviewed commit: `a465b00`
Baseline review: `docs/initial-implementation-review.md`

## Part 1: Assessment

The fix commit substantially improved safety checks, cache semantics, comparator warning handling, and test coverage. The critical workspace-delete traversal is fixed. Golden workspace names are now slug-safe. Comparator warnings are returned and enforced by `--strict`. The golden runner now has partial-failure output and a nonzero exit path.

The implementation is still not merge-ready. The Unix fresh installer remains broken because the fix invokes the Bash-only `shopt` builtin through `sh -c` and masks failure with `|| true`. Both setup scripts verify the wrong DuckDuckGo module after installing `ddgs`. Golden cached runs cannot use any committed cache files after the cache-key format change, and live arXiv runs still do not write cache entries. Update mode can also overwrite promised-to-be-preserved config files.

### Previous Finding Status

| Previous finding | Status |
|---|---|
| Constrain workspace deletion | Fixed |
| Make Unix git fresh install work | Not fixed |
| Generate valid golden workspace names | Fixed |
| Repair golden caching | Partially fixed; important failures remain |
| Enforce citation coverage under `--strict` | Fixed |
| Fail golden runner when child searches fail | Implementation added; regression tests currently fail |

### Validation Performed

| Command | Outcome |
|---|---|
| `python -m pytest -q` | Failed: 2 failed, 115 passed, 3 skipped |
| `python -m pytest -q tests/unit/test_scripts.py tests/unit/test_compare.py tests/unit/test_install.py` | Passed: 31 passed, 3 skipped |
| `python tests/validate_skills.py` | Passed |
| `python tests/golden/run.py --use-cache` | Could not complete in sandbox because workspace creation was denied; independent cache-key inspection confirms all four configured cache lookups miss |
| `python tests/golden/compare.py examples/sample-workspace examples/sample-workspace --strict` | Exited 1 as intended, but emitted top-level `"status": "ok"` |
| Python AST parsing for `scripts/*.py` and `providers/**/*.py` | Passed |
| PowerShell parser check for `install.ps1` | Passed |
| Unix installer integration tests | Skipped on Windows |

## Part 2: Actionable Fixes

### 1. Stop invoking Bash builtins through `sh -c` in the Unix installer

Severity: Critical

The fresh-install fix uses `sh -c "shopt -s dotglob && mv ..."`. `shopt` is a Bash builtin and is not available in common `/bin/sh` implementations such as `dash`. The command failure is then hidden by `|| true`. As a result, the cloned files remain under `.calixto-tmp`, required-marker verification fails, and fresh install still cannot succeed on affected Unix systems.

The same pattern is used by update mode, so Unix updates may silently fail to copy fetched toolkit files while reporting completion.

Evidence: `install.sh:182`, `install.sh:183`, `install.sh:190`, `install.sh:191`, `install.sh:268`, `install.sh:282`, `install.sh:288`.

Suggested fix:

- Do not use `sh -c` for Bash syntax.
- Use Bash-native arrays/globs in the current script, or invoke `bash -c` explicitly with safely passed positional parameters.
- Remove `|| true` from required copy/move operations and verify command outcomes.
- Add a real Linux CI job that executes fresh-install and update integration tests.

Tests to add:

- Run `install.sh` on Linux where `/bin/sh` is `dash`.
- Verify fresh install and update mode both copy normal files and dotfiles.
- Verify a failed copy exits nonzero instead of being masked.

### 2. Verify `ddgs`, not the uninstalled legacy `duckduckgo_search` package

Severity: High

`pyproject.toml` installs `ddgs`, and the decision log explicitly records the rename. Both setup scripts still verify `import duckduckgo_search`. A clean environment containing only declared dependencies can therefore complete `uv sync` and then fail the setup verification step.

Evidence: `pyproject.toml:25`; `setup.sh:50`, `setup.sh:69`; `setup.ps1:80`, `setup.ps1:114`; `docs/initial-implementation-plan-decision-log.md` Decision 005.

Suggested fix:

- Change setup verification to `import ddgs`.
- Update setup messages and the AGENTS.md verification command to use `ddgs`.
- Test setup verification in a clean environment built only from `pyproject.toml`.

### 3. Restore golden-cache compatibility and make live arXiv searches cache results

Severity: High

The new cache-key format changed from `provider|query|max_results` to named key/value parts. None of the four committed cache files match the keys now computed for `tests/golden/config.json`, so the documented `--use-cache` golden run will deterministically fail with cache misses once workspace creation succeeds.

Additionally, `search_arxiv.py` only calls `save_cache()` inside `if use_cache`. A cache miss in `use_cache` mode exits earlier, making that save branch unreachable. Live arXiv searches therefore never populate the cache.

Cached execution also initializes providers before cache lookup. Cached Brave searches still require an API key, and cached arXiv searches still require the arXiv package, even though neither is needed to read cached JSON.

Evidence: `scripts/search_web.py:115`, `scripts/search_web.py:291`; `scripts/search_arxiv.py:151`, `scripts/search_arxiv.py:160`, `scripts/search_arxiv.py:217`; committed files under `tests/golden/cache/`.

Suggested fix:

- Regenerate or migrate committed cache files to the new key format.
- Save arXiv results after every successful live call, matching web-search behavior.
- Perform cache lookup before provider/client initialization.
- Add an end-to-end cached golden test that uses the committed cache directory.

### 4. Preserve config files during installer update mode

Severity: High

The plan requires update mode to preserve user data, especially config files. Unix update backs up root `config.json` and `*.local` files but never restores them. Windows update promises that config files will be preserved but neither backs them up nor restores them. Fetched toolkit files can therefore overwrite user configuration during update.

Evidence: `docs/initial-implementation-plan.md:303`; `install.sh:241`, `install.sh:248`, `install.sh:274`; `install.ps1:194`, `install.ps1:205`, `install.ps1:251`.

Suggested fix:

- Define the exact user-owned config file set.
- Back up and restore that same set in both installers.
- Add update-mode integration tests with modified config files and local overrides.

### 5. Repair the new golden-run regression tests

Severity: Medium

The full required test suite currently fails. The two new partial-failure tests construct workspace names from `tmp_path.name`; those names can exceed the 64-character slug limit. The subprocess then fails before workspace creation and emits the structured error to stderr, so the tests never exercise partial child-search failure behavior.

The tests also monkeypatch an imported runner module, then invoke a separate subprocess where those monkeypatches have no effect.

Evidence: `tests/unit/test_golden_runner.py:119`, `tests/unit/test_golden_runner.py:143`, `tests/unit/test_golden_runner.py:166`, `tests/unit/test_golden_runner.py:202`.

Suggested fix:

- Use short, valid, collision-resistant workspace slugs.
- Either test `run_golden()` in process with monkeypatching, or configure the subprocess entirely through arguments/environment.
- Clean up any workspaces and archives created by integration tests.

### 6. Emit an error status when golden comparison exits with failure

Severity: Medium

When comparison checks fail, `compare.py` exits with code 1 but still calls `emit_ok()`, producing top-level `"status": "ok"` on stdout. This contradicts the repository-wide structured-output contract and can mislead callers that inspect JSON status rather than process exit code.

Evidence: `tests/golden/compare.py:349`, `tests/golden/compare.py:354`, `tests/golden/compare.py:366`; reproduced with strict comparison of the sample workspace.

Suggested fix:

- Emit structured failure JSON with `"status": "error"` to stderr when comparison fails.
- Preserve metrics, warnings, and failures in the error payload.
- Add a CLI regression test asserting stream, JSON status, and exit code together.

## Review Verdict

Not merge-ready. The delete-safety fix is solid, but the Unix installer, clean setup, golden cache workflow, and update data-preservation contract still have release-blocking defects. Fix those issues and restore a fully passing test suite before marking the initial implementation complete.
