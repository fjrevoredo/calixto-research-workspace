# Initial Implementation Review

Date: 2026-06-07
Branch: `master`
Reviewed commit: `3f43662f77eae5d5aa6fa4cf7ef01fb72cf1cdcc`
Review target: `requirements.md`, `docs/initial-implementation-plan.md`, `docs/initial-implementation-plan-decision-log.md`, and the complete initial implementation

## Part 1: Assessment

The implementation establishes the intended repository structure, provider abstractions, workspace template, skills, documentation, and a useful unit-test base. The core Python test suite passes, and skill-spec validation passes. The implementation is generally readable and cohesive.

It is not merge-ready as the completed initial implementation. There are two release-blocking safety/install defects, the documented golden run currently cannot start, and the golden validation/caching implementation does not enforce the reproducibility and citation-quality contracts stated in `requirements.md`. These gaps also contradict the plan's claim that final end-to-end and installer verification completed successfully.

Validation performed:

| Command | Outcome |
|---|---|
| `python -m pytest -q` | Passed: 91 tests; two pytest-cache permission warnings |
| `python tests/validate_skills.py` | Passed |
| `python tests/golden/run.py --use-cache` | Failed before searching: generated workspace name contains uppercase `T` and `Z` |
| `python -m ruff check .` | Not run: `ruff` is not installed in the system Python environment |
| `uv run python -m pytest -q` / `uv run ruff check .` | Not run: sandbox `uv` cache creation failed |
| PowerShell parser checks for `install.ps1` and `setup.ps1` | Passed |
| `bash -n install.sh` / `bash -n setup.sh` | Not run: no WSL distribution is installed |

## Part 2: Actionable Fixes

### 1. Constrain workspace deletion to a verified workspace target

Severity: Critical

`_resolve_workspace()` resolves invalid names relative to the workspace parent without checking that the result remains inside that parent. `cmd_delete()` then only checks that the path exists before calling `shutil.rmtree()`. For example, `workspace_info.py delete .. --path ./workspaces --force` resolves to the repository root and recursively deletes it.

Evidence: `scripts/workspace_info.py:62`, `scripts/workspace_info.py:76`, `scripts/workspace_info.py:184`, `scripts/workspace_info.py:198`.

Suggested fix:

- Require delete targets to contain the workspace marker `config.json`.
- Resolve both parent and target, then reject targets outside the configured parent unless an explicit, separately designed absolute-path mode is used.
- Reject the parent itself and filesystem roots.
- Keep the final safety checks immediately before `shutil.rmtree()`.

Tests to add:

- Reject `delete .. --path <parent> --force`.
- Reject deletion of an existing non-workspace directory.
- Reject traversal and absolute paths outside the workspace parent.
- Continue allowing deletion of a verified workspace.

### 2. Make the Unix git fresh-install path actually install the repository

Severity: Critical

The git fresh-install branch clones into `.calixto-tmp`, renames it to `.calixto-stage`, never moves its contents into the target directory, then deletes `.calixto-stage`. The script proceeds to report a successful fresh install while leaving the target empty.

Evidence: `install.sh:180`, `install.sh:181`, `install.sh:194`, `install.sh:196`, `install.sh:207`.

Suggested fix:

- Clone into a staging directory outside or inside the target.
- Move/copy all staged contents, including dotfiles, into the target.
- Verify required workspace markers exist before deleting staging or reporting success.
- Fail and preserve staging when installation is incomplete.

Tests to add:

- Fresh install from a local git repository into an empty temporary directory.
- Assert all required markers and dotfiles exist after install.
- Assert the installer exits nonzero if staged files were not installed.

### 3. Generate valid golden workspace names

Severity: High

The golden runner formats timestamps as `%Y%m%dT%H%M%SZ`, but workspace slugs only allow lowercase letters, digits, and hyphens. Therefore the documented `python tests/golden/run.py --use-cache` command always fails during workspace initialization.

Evidence: `tests/golden/run.py:98`, `tests/golden/run.py:100`; slug contract in `scripts/_common.py:226` and `scripts/_common.py:238`.

Suggested fix:

- Generate a lowercase slug-safe timestamp, for example `%Y%m%dt%H%M%Sz`, or pass the generated name through `slugify()`.
- Add an integration test that runs the golden runner far enough to create its default workspace.

Tests to add:

- Default generated golden workspace name passes `is_valid_slug()`.
- Cached golden run starts successfully with no explicit `--workspace-name`.

### 4. Repair golden cache creation, clearing, and cache-key correctness

Severity: High

The reproducibility contract says the first live run caches search results and later runs reuse them. In the implementation, search results are only saved when `--use-cache` is already enabled. A normal live golden run therefore does not populate the cache. Additionally, the golden runner forwards `--clear-cache` to every search, so each query deletes caches written by earlier queries. For arXiv, cache keys omit category and sort order, allowing incompatible searches to reuse the same cached result.

Evidence: `requirements.md:510`, `requirements.md:513`; `scripts/search_web.py:115`, `scripts/search_web.py:295`; `scripts/search_arxiv.py:159`, `scripts/search_arxiv.py:205`; `tests/golden/run.py:103`, `tests/golden/run.py:145`, `tests/golden/run.py:164`.

Suggested fix:

- Save successful live search responses by default; treat `--use-cache` as "prefer/require cache" rather than "enable cache writes."
- Clear the cache once in the golden runner, before the search loop, and do not pass `--clear-cache` to each child search.
- Include every result-affecting input in cache keys, including arXiv category and sort order.
- Define whether a `--use-cache` miss may call the network. For reproducible golden runs, a cache miss should normally fail clearly.

Tests to add:

- A live search writes a reusable cache entry without `--use-cache`.
- Multiple searches after `--clear-cache` leave all newly generated cache entries intact.
- Different arXiv categories/sort orders produce different cache keys.
- Strict cached mode fails clearly on a cache miss without calling a provider.

### 5. Enforce citation coverage and make `--strict` meaningful

Severity: Medium

`check_against_expected()` records citation-coverage failures in a local `warnings` list, then returns only `failures`. The caller never receives warnings, and `--strict` checks the same failures list as non-strict mode. A run below the required 80% citation coverage can therefore pass in both modes.

Evidence: `requirements.md:545`, `requirements.md:546`; `tests/golden/compare.py:201`, `tests/golden/compare.py:245`, `tests/golden/compare.py:279`, `tests/golden/compare.py:325`.

Suggested fix:

- Return failures and warnings separately.
- Make `--strict` fail when warnings exist.
- Decide whether the stated `>=80%` citation requirement is always a failure; if so, record it directly as a failure and remove the warning ambiguity.

Tests to add:

- Comparison below minimum citation coverage fails in strict mode.
- Warning details are present in JSON output.
- Comparison at or above the threshold passes.

### 6. Fail the golden runner when child searches fail

Severity: Medium

The golden runner catches each search failure, archives the incomplete workspace, emits top-level `"status": "ok"`, and exits zero. Although `searches_failed` is included in the summary, automation and the plan's final verification cannot distinguish a successful end-to-end run from a partially failed one by exit code or top-level status.

Evidence: `tests/golden/run.py:167`, `tests/golden/run.py:170`, `tests/golden/run.py:205`, `tests/golden/run.py:239`.

Suggested fix:

- Emit a top-level partial/error status and nonzero exit code when any configured search fails.
- Preserve and report the partial workspace, consistent with the no-silent-failures principle.

Tests to add:

- A configured child-search failure produces nonzero golden-run exit status.
- The partial workspace and structured failure details remain available.

## Review Verdict

Not merge-ready. The workspace deletion traversal and broken Unix fresh install must be fixed before release. The golden runner, cache behavior, and comparison enforcement should then be repaired and covered by integration tests before the plan can accurately remain marked completed.
