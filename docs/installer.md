# Installer Behavior

Last updated: 2026-06-09

This document describes the supported installer behavior for `install.sh` and
`install.ps1`.

## Modes

The installer has two modes:

- Fresh install: runs in a verified empty directory and copies the full toolkit.
- Update: runs inside an existing Calixto toolkit root and updates toolkit
  files only while leaving standalone workspaces untouched.

These modes intentionally have different safety rules.

## Source Selection

The supported selectors are:

- default branch: `master`
- explicit branch: `--branch <branch>` or `CALIXTO_REPO_BRANCH=<branch>`
- explicit tag/version: `--version <tag>` or `CALIXTO_VERSION=<tag>`

Rules:

- Branch and version/tag are mutually exclusive.
- The default branch is applied only when no explicit version/tag or branch was
  supplied.
- Arbitrary refs are not supported.
- The repository currently uses `master` as its default branch. GitHub raw
  installer examples therefore pin `master`, while local installer runs without
  `--branch` follow the repository default branch dynamically.

## Repository URL Contract

Production `--repo` / `CALIXTO_REPO_URL` values must be GitHub repository URLs
in this form:

```text
https://github.com/<owner>/<repo>
https://github.com/<owner>/<repo>.git
```

Supported variations:

- the default `calixto/calixto` repository
- GitHub forks
- GitHub repositories with arbitrary names

Unsupported in production:

- plain HTTP repository URLs
- arbitrary hosts
- GitHub Enterprise hosts that do not use the `github.com` archive layout

## Git And Archive Fallback

The installer prefers `git clone` when `git` is available.

If `git` is unavailable, the installer downloads a GitHub archive:

- branch: `archive/refs/heads/<branch>.tar.gz`
- tag/version: `archive/refs/tags/<tag>.tar.gz`

Archive fallback prerequisites:

- `curl`
- Python 3.11+ (used for archive validation, extraction, and shared installer
  logic)

The archive root is discovered structurally after extraction. It is not derived
from the repository name.

## TLS Rules

Production archive downloads always verify TLS.

There is no production insecure-TLS escape hatch.

Installer integration tests may use these test-only overrides:

- `CALIXTO_TEST_MODE=1`
- `CALIXTO_TEST_ARCHIVE_URL=<https://...>`
- `CALIXTO_TEST_CA_CERT=<path-to-test-ca-or-self-signed-cert>`
- `CALIXTO_TEST_FAIL_AFTER_REPLACEMENTS=<n>`

The test-only variables are rejected unless `CALIXTO_TEST_MODE=1` is set.

The installer archive integration tests in CI expect the development
dependencies to be installed, including `cryptography`, so the test fixture can
generate a localhost HTTPS certificate.

## Fresh Install Contract

Fresh install:

- requires the target directory to be empty
- copies every staged top-level toolkit entry except source-control metadata
  such as `.git/`
- copies a root `config.json` if the downloaded source contains one
- writes `.calixto-managed-entries` only after the copied toolkit validates
  successfully
- rejects downloaded `workspaces/`, `notes/`, `outputs/`, and root `*.local`
  entries instead of installing them as toolkit content

## Update Contract

Update preserves these root entries:

- `.git/`
- `workspaces/`
- root `*.local` files

Update replaces or removes only toolkit-owned entries:

- entries listed in `.calixto-managed-entries`
- known historical toolkit entries from the legacy bootstrap allow-list when the
  ownership file does not exist yet

Update behavior is conservative:

- unknown root-level files are never deleted automatically
- a new toolkit entry that collides with an unknown root-level file or
  directory aborts the update before mutation
- a missing toolkit entry is retired only when managed-entry ownership proves
  the toolkit installed it previously

## Managed-Entry Metadata

`.calixto-managed-entries` is newline-delimited installer state written after a
successful install or update.

It records top-level toolkit-owned entries only. It does not record:

- `.git/`
- protected user-owned directories
- `config.json`
- root `*.local` files
- transaction state directories

Legacy installs without `.calixto-managed-entries` still update known
historical top-level toolkit entries, but they remain conservative for all
other collisions.

## Transactional Updates

Updates use `.calixto-update-transaction/` while applying file replacements.

The transaction contains:

```text
.calixto-update-transaction/
|-- source/
|-- rollback/
|-- diagnostics/
|-- state
|-- applied.txt
|-- replaced.txt
`-- added.txt
```

During update:

1. The installer fetches and validates the new source tree.
2. It moves replaced toolkit entries into `rollback/`.
3. It installs validated replacements one top-level entry at a time.
4. It verifies required toolkit markers and protected root data.
5. It writes the new `.calixto-managed-entries`.
6. It removes the transaction directory only after the filesystem update is
   committed successfully.

If replacement fails mid-update, the installer restores the previous toolkit and
leaves `.calixto-update-transaction/` behind for inspection.

If a later installer run finds an incomplete uncommitted transaction, it first
restores the old toolkit and then stops with an explicit diagnostic.
