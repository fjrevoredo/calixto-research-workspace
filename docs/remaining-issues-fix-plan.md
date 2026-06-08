# Remaining Issues Fix Plan

Date: 2026-06-08  
Scope: Remaining findings from `docs/initial-implementation-additional-pass-review.md`

## Goal

Make fresh installation and workspace updates reliable across:

- Unix and Windows
- Git clone and archive fallback sources
- Default, forked, and custom repository names
- Mid-update failures

The work is complete only when the real installer paths run in CI without relying on copied snippets, redefined helpers, or skipped required tests.

## Implementation Principles

1. Fresh installation and update are separate operations with separate safety rules.
2. Fresh installation into a verified empty directory copies the complete toolkit.
3. Update mode preserves user-owned data and repository metadata.
4. Update mode must either complete successfully or restore the previous toolkit.
5. Archive handling must not depend on the repository being named `calixto`.
6. Required installer integration tests must run, not silently skip.
7. Existing installs without new metadata must update conservatively; never infer that an unknown user file is toolkit-owned.
8. Dry-run mode must not create staging, backup, transaction, certificate, or manifest files.

## Phase 1: Centralize Installer Contracts

### Task 1.1: Define protected and toolkit-owned entries

Document the shared contract in both installers:

**Protected during updates:**

- `.git/`
- `workspaces/`
- `notes/`
- `outputs/`
- `config.json`
- Root `*.local` files

**Toolkit-owned and replaceable during updates:**

- Entries identified as toolkit-owned by managed-entry metadata, including `.gitignore`
- Newly introduced staged entries only when no target entry with the same name exists

If a newly introduced toolkit entry collides with an unknown target entry, stop before mutation and report the conflict. Do not overwrite it automatically.

**Fresh installation:**

- Copy every staged entry into the verified empty target.
- Exclude only staged source-control metadata such as `.git/`.
- Do not apply update-mode user-data protection rules.
- Write installer ownership metadata only after the copied toolkit validates successfully.
- Reject unexpected protected user-data directories in the downloaded source rather than installing them as toolkit content.

`config.json` is not currently a tracked root toolkit file. The contract is:

- If an existing installation has a root `config.json`, update mode preserves it.
- If a future or custom source contains a root `config.json`, fresh-install mode copies it because the target is empty.

### Task 1.2: Split fresh-install and update helpers

Refactor the shared movement logic into explicit operations:

- Unix:
  - `move_fresh_install_contents`
  - `apply_update_contents`
- Windows:
  - `Move-FreshInstallContents`
  - `Apply-UpdateContents`

Do not use a mode-agnostic protected-entry helper for both operations.

### Task 1.3: Define managed-entry ownership

An update cannot safely delete a removed toolkit entry unless it knows that the entry came from a previous toolkit installation. Add a small persistent ownership file, for example:

```text
.calixto-managed-entries
```

It records toolkit-owned top-level entries installed by the last successful install/update. Prefer a sorted, newline-delimited format so Bash and PowerShell can read and write it without adding a JSON parser dependency. Reject source entry names containing control characters or newlines.

Rules:

- Fresh install records every installed top-level entry except protected/user-owned entries and `.git/`.
- Update replaces entries present in the new source only when they are already managed, match the documented legacy bootstrap allow-list, or do not collide with an existing target entry.
- Update removes entries absent from the new source only when the previous ownership file identifies them as toolkit-owned.
- A new staged entry that collides with a target entry not listed as managed is a conflict and aborts before mutation.
- Existing installations without an ownership file use a documented legacy bootstrap allow-list containing only top-level entries known to have shipped before managed-entry metadata existed. They may replace those known entries, add non-colliding new entries, and must stop on all other collisions.
- The ownership file itself is toolkit metadata and participates in rollback.
- The ownership file is generated installer state, not content copied from the downloaded source. Reject or ignore a source-supplied ownership-state file.

### Acceptance Criteria

- A fresh install copies a root-level `config.json`.
- An update preserves an existing root-level `config.json`.
- Fresh and update behavior is equivalent across Unix and Windows.
- A removed toolkit-owned entry is retired after an update when ownership metadata exists.
- An unknown root-level user file is never deleted.
- A future toolkit entry colliding with an unknown user file causes a pre-mutation conflict.
- A legacy installation without ownership metadata can still update known historical toolkit entries.

## Phase 2: Make Archive Extraction Repository-Agnostic

### Task 2.1: Add archive-root discovery

After extracting an archive into an empty staging directory:

1. List top-level directories.
2. Exclude known installer artifacts such as the downloaded archive.
3. Require exactly one candidate directory.
4. Resolve and verify that the candidate remains inside the staging directory.
5. Use that directory as the extracted repository root.
6. Fail clearly when zero or multiple candidates exist.

Do not search for `calixto-*`.

Suggested interfaces:

```bash
find_extracted_root "$staging"
```

```powershell
Find-ExtractedRoot -StagingDirectory $staging
```

### Task 2.2: Keep branch, tag, and arbitrary-ref behavior explicit

Required source rules:

- Branch: `archive/refs/heads/<branch>.tar.gz`
- Version/tag: `archive/refs/tags/<version>.tar.gz`

Arbitrary-ref support is not required by the original plan. Either remove the newly introduced Windows-only `-Ref` option to preserve cross-platform parity, or explicitly approve it as a new feature and implement the same behavior on Unix. Do not leave it Windows-only.

Reject conflicting selectors such as branch plus version/tag rather than silently choosing one.

Because branch currently defaults to `main`, selector parsing must distinguish an explicitly supplied branch from the default. Apply `main` only when no version/tag or other approved selector was supplied.

Keep the supported host contract narrow and accurate:

- `RepoUrl` may identify the default GitHub repository or a GitHub fork/custom repository name.
- Do not claim generic GitHub Enterprise or arbitrary-host compatibility unless its archive URL format is separately implemented and tested.
- Tests may use an explicit test-only archive URL override; production repository URL validation must continue to reject insecure HTTP sources.
- Remove `CALIXTO_INSECURE_TLS` as a production-facing escape hatch. Integration tests should trust their dedicated test certificate through a test-only CA configuration or use another test-only transport override; production downloads must verify TLS.

### Task 2.3: Validate archive contents before applying them

Before extracting:

- Inspect archive member names and link targets.
- Reject absolute paths, `..` traversal, drive-qualified paths, symlinks/hardlinks escaping staging, and platform-specific reparse-point hazards.
- Extract only after the member preflight passes.

Before fresh installation or update target mutation:

- Verify every required workspace marker exists in the extracted root.
- Validate the complete staged source tree, including symlinks/reparse points, regardless of whether the source came from Git or an archive.
- Fail before modifying the target if validation fails.

### Acceptance Criteria

- Archive fallback works for repositories named `calixto`, `fake-repo`, and another arbitrary name.
- Branch and tag archive URLs are covered by tests.
- Invalid or ambiguous archives fail before the target is modified.
- Malicious archive paths cannot write outside staging.
- Unix and Windows expose the same documented source selectors.

## Phase 3: Add Transactional Update Rollback

### Task 3.1: Prepare and validate before mutation

Before replacing target files:

1. Download or clone into staging.
2. Discover the source root.
3. Validate required workspace markers.
4. Build the list of toolkit-owned top-level entries to replace.
5. Detect unknown-entry collisions.
6. Confirm protected entries, transaction metadata, and unknown user entries will not be touched.

### Task 3.2: Create a rollback snapshot

Create a rollback directory separate from the source staging directory:

```text
.calixto-update-transaction/
|-- source/
|-- rollback/
|-- state
`-- diagnostics/
```

Do not require a JSON transaction manifest unless the implementation already has a portable JSON-writing mechanism available in both installers. A simple state marker plus the persistent managed-entry ownership file is sufficient.

Move existing toolkit-owned entries into `rollback/` before installing replacements. Do not delete them.

The transaction directory itself must always be excluded from source application and managed-entry ownership.

Keep the existing timestamped user-data backup behavior. The transaction rollback protects toolkit files during the update; the preserved user-data backup remains the user's post-update recovery copy.

### Task 3.3: Apply replacements

Move validated staged entries into the target one top-level entry at a time.

On any failure:

1. Remove newly applied replacement entries.
2. Restore originals from `rollback/`.
3. Leave the transaction directory and diagnostics for inspection.
4. Exit nonzero.

Error propagation must permit rollback:

- Unix: install an `EXIT`, `INT`, and `TERM` trap while a transaction is active.
- Windows: perform update mutation inside `try/catch/finally`; update helpers must throw rather than call an immediate process `exit` that bypasses recovery logic.

### Task 3.4: Validate and commit the transaction

After replacement:

- Verify required workspace markers.
- Compare protected user data, root config/local overrides, and `.git/` against pre-update snapshots or sentinel hashes.
- Write the new managed-entry ownership file.
- Run setup only after filesystem replacement is committed.
- Remove rollback contents only after filesystem validation succeeds.

Setup failure should return nonzero but does not require rolling back toolkit files unless that policy is explicitly chosen and documented.

Mark the filesystem transaction committed before optional setup starts, so a setup failure cannot later be mistaken for an interrupted file replacement.

### Task 3.5: Handle interrupted transactions

At installer startup, detect an existing incomplete transaction directory.

Default behavior:

- If state says replacement was not committed, automatically restore from rollback, then stop with a clear diagnostic.
- If state is ambiguous or rollback is incomplete, stop with explicit manual recovery instructions.
- Never silently overwrite or discard an incomplete transaction.

### Acceptance Criteria

- Injected failures after the first, middle, and final replacement restore the original toolkit.
- User workspaces, config, local overrides, and `.git/` remain unchanged.
- Successful updates leave no active transaction directory.
- Dry-run creates no transaction or backup artifacts.
- An interrupted transaction is either automatically restored or stops without further mutation.

## Phase 4: Make Installer Integration Tests Mandatory

### Task 4.1: Remove undeclared test prerequisites

Use one explicit, reproducible approach:

**Preferred:** Add `cryptography` to the development dependency group that CI actually installs, and assert the dependency is available in installer-test jobs.

Do not rely on an undeclared transitive dependency. Do not commit a reusable private key unless repository security policy explicitly permits public test keys. Remove unused certificate-generation scripts and untracked fixtures.

### Task 4.2: Run real archive fallback tests

For both Unix and Windows, execute the actual installer with:

- Git hidden from `PATH`
- A local HTTPS archive server
- `--skip-deps` / `-SkipDeps`
- Fresh-install and update targets
- The actual installer source-selection, download, extraction, validation, and application code

Test archive roots:

- `calixto-main`
- `fake-repo-main`
- `another-tool-v1.2.3`

Also test:

- An archive with zero candidate roots
- An archive with multiple candidate roots
- An archive missing a required workspace marker
- A path-traversal archive
- A custom repository URL whose archive root matches the custom repository name

### Task 4.3: Add rollback failure-injection tests

Add a test-only environment variable:

```text
CALIXTO_TEST_FAIL_AFTER_REPLACEMENTS=N
```

It must only affect tests and should cause a controlled failure after `N` replacements.

Guard it behind an explicit test mode such as `CALIXTO_TEST_MODE=1`; otherwise reject or ignore it. Production users must not accidentally trigger failure injection.

Verify rollback after multiple failure points.

### Task 4.4: Enforce platform coverage in CI

Add CI jobs:

- Windows: PowerShell installer git and archive paths
- Linux: Bash installer git and archive paths

Required installer-path tests must fail CI if skipped unexpectedly.

Use explicit pytest markers such as:

```python
@pytest.mark.installer_windows
@pytest.mark.installer_unix
@pytest.mark.installer_archive
```

At the end of each platform job, verify the expected installer tests ran.

Register all custom markers in pytest configuration and run installer jobs with `--strict-markers`. On the platform where a test is required, missing prerequisites must fail preflight rather than call `pytest.skip`.

### Acceptance Criteria

- Windows archive tests no longer skip due missing `cryptography`.
- Unix installer integration tests execute in Linux CI.
- A required installer path cannot disappear behind a skip while CI remains green.
- Test helpers import files from the isolated checkout under test, not from the developer's original working tree.

## Phase 5: Documentation and Decision Log

### Task 5.1: Document installer source selection

Update user-facing installer documentation with:

- Branch, version/tag, and arbitrary-ref behavior
- The decision to support or remove arbitrary refs
- Git-to-archive fallback prerequisites
- Supported custom repository URL format
- Update transaction and recovery behavior
- Managed-entry ownership and conservative behavior for legacy installs
- TLS verification requirements and archive-fallback tool prerequisites

### Task 5.2: Add decision-log entries

Record:

1. Fresh-install and update protection rules are intentionally separate.
2. Archive roots are discovered structurally, not by repository name.
3. Updates use a rollback transaction.
4. Required installer integration tests must execute on their native platform.
5. Managed-entry metadata is the only authority for deleting toolkit files absent from a later release.

### Task 5.3: Remove obsolete comments and tests

Delete:

- Copied shell-snippet tests superseded by actual installer execution
- Tests that redefine implementation helpers
- Comments that claim behavior no longer matching the implementation
- Temporary certificate-generation files not part of the chosen fixture strategy

## Recommended Implementation Order

1. Split fresh-install and update helpers.
2. Implement repository-agnostic archive-root discovery.
3. Add pre-mutation source validation.
4. Add managed-entry ownership metadata.
5. Implement transactional update rollback.
6. Replace skipped/static tests with real platform integration tests.
7. Add CI enforcement for installer test execution.
8. Update documentation and decision log.
9. Run final validation from clean checkouts.

## Final Validation Checklist

Run from clean checkouts on Windows and Linux:

```text
python -m pytest -q
python tests/validate_skills.py
python tests/golden/run.py --use-cache
python tests/golden/compare.py <known-compatible-run-a> <known-compatible-run-b>
```

Record expected exit codes and stream contracts for each command. The comparison inputs must be known-compatible runs when exit code 0 is required; do not use an intentionally incomplete source-only run and then treat its expected comparison failure as a regression.

Installer scenarios that must pass:

1. Fresh install via Git.
2. Fresh install via archive fallback.
3. Update via Git.
4. Update via archive fallback.
5. Branch source.
6. Tagged-version source.
7. Default repository name.
8. Custom repository name.
9. Failed update followed by successful rollback.
10. Interrupted transaction recovery.
11. Legacy install without managed-entry metadata.
12. Removal of a previously managed toolkit entry.
13. Preservation of an unknown root-level user file.
14. Malformed and path-traversal archives.
15. Dry-run with no filesystem changes.

## Completion Gate

The remaining issues are fixed only when:

- No installer mode depends on a `calixto-*` archive root.
- Fresh installs copy all intended toolkit files.
- Updates preserve protected entries.
- Failed updates restore the previous toolkit.
- Updates only delete absent entries proven toolkit-owned by managed-entry metadata.
- Invalid or malicious archives fail before target mutation.
- Required installer integration tests execute on their native CI platforms.
- Full clean-checkout validation passes on Windows and Linux.
