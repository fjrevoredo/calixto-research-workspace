"""Windows installer integration tests."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from tests.unit.installer_test_support import (
    TOOLKIT_ROOT_ENTRIES,
    WORKSPACE_MARKERS,
    assert_no_installer_artifacts,
    create_isolated_checkout,
    create_repo_metadata,
    ensure_user_workspace,
    have_pwsh,
    installer_artifacts,
    invoke_windows_installer,
    install_toolkit_tree,
    make_remote_git_repo,
    path_without_git,
    serve_archive_https,
    stage_archive_root,
    build_archive,
)

pytestmark = [pytest.mark.installer_windows]


def require_windows_prereqs() -> None:
    if sys.platform != "win32":
        pytest.skip("install.ps1 is required in Windows CI, not on Unix hosts")
    if not have_pwsh() or shutil.which("git") is None:
        if os.environ.get("CALIXTO_ENFORCE_INSTALLER_PREREQS") == "1":
            pytest.fail("pwsh and git must be available for installer_windows tests")
        pytest.skip("pwsh and git are required for installer_windows tests")


def managed_entries_from_checkout(checkout: Path) -> list[str]:
    protected = {".git", "workspaces", "notes", "outputs", "config.json"}
    return sorted(
        name
        for name in TOOLKIT_ROOT_ENTRIES
        if name not in protected and not name.endswith(".local")
    )


def base_env() -> dict[str, str]:
    env = dict(os.environ)
    env["CALIXTO_TEST_MODE"] = "1"
    return env


def assert_install_metadata(target: Path, repo_url: str) -> None:
    metadata = json.loads((target / ".calixto-toolkit-install.json").read_text(encoding="utf-8"))
    assert metadata["metadata_version"] == 1
    assert metadata["repo_url"] == repo_url
    assert metadata["selector_kind"] == "default_branch"
    assert metadata["selector_value"] is None
    assert metadata["toolkit_ref_name"] == "main"
    assert isinstance(metadata["toolkit_commit"], str) and metadata["toolkit_commit"]
    assert metadata["source_history"] in {"full", "shallow"}
    if metadata["source_history"] == "full":
        assert isinstance(metadata["toolkit_build_number"], int)
        assert metadata["toolkit_build_number"] > 0
    else:
        assert metadata["toolkit_build_number"] is None


def test_fresh_install_copies_root_config_and_writes_managed_entries(
    tmp_path: Path,
) -> None:
    require_windows_prereqs()
    checkout = create_isolated_checkout(tmp_path)
    remote = make_remote_git_repo(
        checkout,
        tmp_path / "remote.git",
        add_text_files={
            "config.json": '{"fresh": true}\n',
            ".calixto-dotfile": "dot\n",
        },
    )
    target = tmp_path / "install-target"
    target.mkdir()

    env = base_env()
    env["CALIXTO_REPO_URL"] = str(remote)
    result = invoke_windows_installer(
        checkout,
        target,
        env,
        args=["-NonInteractive", "-SkipDeps"],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    for marker in WORKSPACE_MARKERS:
        assert (target / marker).exists(), f"missing marker {marker}"
    assert (target / "config.json").read_text(encoding="utf-8") == '{"fresh": true}\n'
    assert (target / ".calixto-dotfile").read_text(encoding="utf-8") == "dot\n"
    managed = (target / ".calixto-managed-entries").read_text(encoding="utf-8")
    assert "config.json" not in managed
    assert ".gitignore" in managed
    assert_install_metadata(target, str(remote))
    assert_no_installer_artifacts(target)


def test_fresh_install_retries_setup_once_after_incomplete_venv(
    tmp_path: Path,
) -> None:
    require_windows_prereqs()
    checkout = create_isolated_checkout(tmp_path)
    remote = make_remote_git_repo(
        checkout,
        tmp_path / "remote.git",
        add_text_files={
            "setup.ps1": """
#!/usr/bin/env pwsh
$attemptFile = Join-Path (Get-Location) 'setup-attempts.txt'
$count = 0
if (Test-Path -LiteralPath $attemptFile) {
    $count = [int](Get-Content -LiteralPath $attemptFile -Raw)
}
$count += 1
Set-Content -LiteralPath $attemptFile -Value $count -NoNewline
$venvPython = Join-Path (Get-Location) '.venv\\Scripts\\python.exe'
if ($count -eq 1) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $venvPython) -Force | Out-Null
    exit 1
}
New-Item -ItemType Directory -Path (Split-Path -Parent $venvPython) -Force | Out-Null
New-Item -ItemType File -Path $venvPython -Force | Out-Null
exit 0
""",
        },
    )
    target = tmp_path / "install-target"
    target.mkdir()

    env = base_env()
    env["CALIXTO_REPO_URL"] = str(remote)
    result = invoke_windows_installer(
        checkout,
        target,
        env,
        args=["-NonInteractive"],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (target / "setup-attempts.txt").read_text(encoding="utf-8") == "2"
    assert (target / ".venv" / "Scripts" / "python.exe").exists()
    assert "Retrying once." in result.stdout
    assert_no_installer_artifacts(target)


def test_fresh_install_accepts_successful_setup_output(
    tmp_path: Path,
) -> None:
    require_windows_prereqs()
    checkout = create_isolated_checkout(tmp_path)
    remote = make_remote_git_repo(
        checkout,
        tmp_path / "remote.git",
        add_text_files={
            "setup.ps1": """
#!/usr/bin/env pwsh
Write-Host 'setup output line'
exit 0
""",
        },
    )
    target = tmp_path / "install-target"
    target.mkdir()

    env = base_env()
    env["CALIXTO_REPO_URL"] = str(remote)
    result = invoke_windows_installer(
        checkout,
        target,
        env,
        args=["-NonInteractive"],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "setup output line" in result.stdout
    assert_no_installer_artifacts(target)


def test_update_preserves_user_data_and_retires_removed_managed_entry(
    tmp_path: Path,
) -> None:
    require_windows_prereqs()
    checkout = create_isolated_checkout(tmp_path)
    remote = make_remote_git_repo(
        checkout,
        tmp_path / "remote.git",
        remove_entries={"examples"},
    )
    target = tmp_path / "install-target"
    install_toolkit_tree(checkout, target)
    (target / ".calixto-managed-entries").write_text(
        "".join(f"{name}\n" for name in managed_entries_from_checkout(checkout)),
        encoding="utf-8",
    )
    (target / "config.json").write_text('{"user": true}\n', encoding="utf-8")
    (target / "settings.local").write_text("local\n", encoding="utf-8")
    (target / "user-owned.txt").write_text("keep\n", encoding="utf-8")
    findings = ensure_user_workspace(target)
    git_dir = create_repo_metadata(target)

    config_before = (target / "config.json").read_text(encoding="utf-8")
    local_before = (target / "settings.local").read_text(encoding="utf-8")
    findings_before = findings.read_text(encoding="utf-8")
    git_head_before = (git_dir / "HEAD").read_text(encoding="utf-8")

    env = base_env()
    env["CALIXTO_REPO_URL"] = str(remote)
    result = invoke_windows_installer(
        checkout,
        target,
        env,
        args=["-NonInteractive", "-SkipDeps"],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (target / "config.json").read_text(encoding="utf-8") == config_before
    assert (target / "settings.local").read_text(encoding="utf-8") == local_before
    assert findings.read_text(encoding="utf-8") == findings_before
    assert (git_dir / "HEAD").read_text(encoding="utf-8") == git_head_before
    assert (target / "user-owned.txt").read_text(encoding="utf-8") == "keep\n"
    assert not (target / "examples").exists()
    assert_install_metadata(target, str(remote))
    assert_no_installer_artifacts(target)


def test_update_conflicts_on_unknown_new_entry_collision(tmp_path: Path) -> None:
    require_windows_prereqs()
    checkout = create_isolated_checkout(tmp_path)
    remote = make_remote_git_repo(
        checkout,
        tmp_path / "remote.git",
        add_text_files={"custom-tooling": "toolkit\n"},
    )
    target = tmp_path / "install-target"
    install_toolkit_tree(checkout, target)
    (target / "custom-tooling").write_text("user-owned\n", encoding="utf-8")
    original = (target / "custom-tooling").read_text(encoding="utf-8")

    env = base_env()
    env["CALIXTO_REPO_URL"] = str(remote)
    result = invoke_windows_installer(
        checkout,
        target,
        env,
        args=["-NonInteractive", "-SkipDeps"],
    )

    assert result.returncode != 0
    assert (target / "custom-tooling").read_text(encoding="utf-8") == original
    assert not (target / ".calixto-update-transaction").exists()


def test_legacy_install_updates_known_toolkit_entries(tmp_path: Path) -> None:
    require_windows_prereqs()
    checkout = create_isolated_checkout(tmp_path)
    remote = make_remote_git_repo(
        checkout,
        tmp_path / "remote.git",
        add_text_files={"README.md": "updated readme\n"},
    )
    target = tmp_path / "install-target"
    install_toolkit_tree(checkout, target)
    (target / "user-owned.txt").write_text("keep\n", encoding="utf-8")

    env = base_env()
    env["CALIXTO_REPO_URL"] = str(remote)
    result = invoke_windows_installer(
        checkout,
        target,
        env,
        args=["-NonInteractive", "-SkipDeps"],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (target / "README.md").read_text(encoding="utf-8") == "updated readme\n"
    assert (target / "user-owned.txt").read_text(encoding="utf-8") == "keep\n"


@pytest.mark.installer_archive
@pytest.mark.parametrize(
    ("archive_root", "repo_url"),
    [
        ("calixto-main", "https://github.com/calixto/calixto.git"),
        ("fake-repo-main", "https://github.com/fake-org/fake-repo.git"),
        ("another-tool-v1.2.3", "https://github.com/another-org/another-tool.git"),
    ],
)
def test_archive_fallback_accepts_repository_agnostic_root_names(
    tmp_path: Path,
    archive_root: str,
    repo_url: str,
) -> None:
    require_windows_prereqs()
    checkout = create_isolated_checkout(tmp_path)
    source_root = stage_archive_root(checkout, tmp_path / "archive-src", archive_root)
    tarball = build_archive(tmp_path / f"{archive_root}.tar.gz", [source_root])
    server, archive_url, cert_path = serve_archive_https(tarball, tmp_path)
    try:
        target = tmp_path / f"target-{archive_root}"
        target.mkdir()
        env = base_env()
        env["PATH"] = path_without_git(env.get("PATH", ""))
        env["CALIXTO_REPO_URL"] = repo_url
        env["CALIXTO_TEST_ARCHIVE_URL"] = archive_url
        env["CALIXTO_TEST_CA_CERT"] = cert_path
        result = invoke_windows_installer(
            checkout,
            target,
            env,
            args=["-NonInteractive", "-SkipDeps"],
        )
        assert result.returncode == 0, result.stdout + result.stderr
        for marker in WORKSPACE_MARKERS:
            assert (target / marker).exists(), f"missing marker {marker}"
        assert_no_installer_artifacts(target)
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.installer_archive
@pytest.mark.parametrize(
    "archive_builder",
    [
        pytest.param("multiple_roots", id="multiple-roots"),
        pytest.param("missing_marker", id="missing-marker"),
        pytest.param("path_traversal", id="path-traversal"),
    ],
)
def test_invalid_archives_fail_before_target_mutation(
    tmp_path: Path,
    archive_builder: str,
) -> None:
    require_windows_prereqs()
    checkout = create_isolated_checkout(tmp_path)
    archive_source = tmp_path / "archive-src"
    archive_source.mkdir()
    roots: list[Path] = []
    extra_members: list[tuple[str, bytes, int]] = []
    if archive_builder == "multiple_roots":
        roots.append(stage_archive_root(checkout, archive_source, "root-a"))
        roots.append(stage_archive_root(checkout, archive_source, "root-b"))
    elif archive_builder == "missing_marker":
        roots.append(
            stage_archive_root(
                checkout,
                archive_source,
                "root-missing",
                remove_entries={"AGENTS.md"},
            )
        )
    else:
        roots.append(stage_archive_root(checkout, archive_source, "root-ok"))
        extra_members.append(("../escape.txt", b"escape", 0o644))

    tarball = build_archive(tmp_path / f"{archive_builder}.tar.gz", roots, extra_members=extra_members)
    server, archive_url, cert_path = serve_archive_https(tarball, tmp_path)
    try:
        target = tmp_path / f"target-{archive_builder}"
        target.mkdir()
        env = base_env()
        env["PATH"] = path_without_git(env.get("PATH", ""))
        env["CALIXTO_REPO_URL"] = "https://github.com/fake-org/fake-repo.git"
        env["CALIXTO_TEST_ARCHIVE_URL"] = archive_url
        env["CALIXTO_TEST_CA_CERT"] = cert_path
        result = invoke_windows_installer(
            checkout,
            target,
            env,
            args=["-NonInteractive", "-SkipDeps"],
        )
        assert result.returncode != 0
        assert list(target.iterdir()) == []
    finally:
        server.shutdown()
        server.server_close()


def test_update_rollback_restores_original_toolkit(tmp_path: Path) -> None:
    require_windows_prereqs()
    checkout = create_isolated_checkout(tmp_path)
    remote = make_remote_git_repo(
        checkout,
        tmp_path / "remote.git",
        add_text_files={"README.md": "updated readme\n"},
    )
    target = tmp_path / "install-target"
    install_toolkit_tree(checkout, target)
    (target / ".calixto-managed-entries").write_text(
        "".join(f"{name}\n" for name in managed_entries_from_checkout(checkout)),
        encoding="utf-8",
    )
    readme_before = (target / "README.md").read_text(encoding="utf-8")
    findings = ensure_user_workspace(target)
    findings_before = findings.read_text(encoding="utf-8")
    git_dir = create_repo_metadata(target)
    git_head_before = (git_dir / "HEAD").read_text(encoding="utf-8")

    env = base_env()
    env["CALIXTO_REPO_URL"] = str(remote)
    env["CALIXTO_TEST_FAIL_AFTER_REPLACEMENTS"] = "2"
    result = invoke_windows_installer(
        checkout,
        target,
        env,
        args=["-NonInteractive", "-SkipDeps"],
    )

    assert result.returncode != 0
    assert (target / "README.md").read_text(encoding="utf-8") == readme_before
    assert findings.read_text(encoding="utf-8") == findings_before
    assert (git_dir / "HEAD").read_text(encoding="utf-8") == git_head_before
    assert (target / ".calixto-update-transaction").exists()


def test_interrupted_transaction_is_restored_before_update(tmp_path: Path) -> None:
    require_windows_prereqs()
    checkout = create_isolated_checkout(tmp_path)
    remote = make_remote_git_repo(checkout, tmp_path / "remote.git")
    target = tmp_path / "install-target"
    install_toolkit_tree(checkout, target)

    transaction = target / ".calixto-update-transaction"
    rollback = transaction / "rollback"
    rollback.mkdir(parents=True)
    (transaction / "state").write_text("phase=replacing\n", encoding="utf-8")
    (transaction / "applied.txt").write_text("README.md\n", encoding="utf-8")
    original_readme = (target / "README.md").read_text(encoding="utf-8")
    (rollback / "README.md").write_text(original_readme, encoding="utf-8")
    (target / "README.md").write_text("partially updated\n", encoding="utf-8")

    env = base_env()
    env["CALIXTO_REPO_URL"] = str(remote)
    result = invoke_windows_installer(
        checkout,
        target,
        env,
        args=["-NonInteractive", "-SkipDeps"],
    )

    assert result.returncode != 0
    assert (target / "README.md").read_text(encoding="utf-8") == original_readme
    assert (transaction / "state").read_text(encoding="utf-8") == "phase=restored_pending_inspection\n"


def test_dry_run_creates_no_installer_artifacts(tmp_path: Path) -> None:
    require_windows_prereqs()
    checkout = create_isolated_checkout(tmp_path)

    fresh_target = tmp_path / "fresh-target"
    fresh_target.mkdir()
    fresh_env = base_env()
    fresh_env["CALIXTO_REPO_URL"] = str(tmp_path / "unused.git")
    fresh = invoke_windows_installer(
        checkout,
        fresh_target,
        fresh_env,
        args=["-DryRun", "-NonInteractive", "-SkipDeps"],
    )
    assert fresh.returncode == 0
    assert list(fresh_target.iterdir()) == []

    update_target = tmp_path / "update-target"
    install_toolkit_tree(checkout, update_target)
    update_env = base_env()
    update_env["CALIXTO_REPO_URL"] = str(tmp_path / "unused.git")
    update = invoke_windows_installer(
        checkout,
        update_target,
        update_env,
        args=["-DryRun", "-NonInteractive", "-SkipDeps"],
    )
    assert update.returncode == 0
    assert not any(path.exists() for path in installer_artifacts(update_target))
    assert not any(child.name.startswith(".calixto-backup-") for child in update_target.iterdir())
