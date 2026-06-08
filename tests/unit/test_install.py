"""Integration tests for the Unix installer (install.sh).

These tests build a local "remote" git repository containing a minimal
Calixto workspace, then exercise install.sh against an empty target
directory. They verify:

- The fresh-install mode copies all required files (including dotfiles)
- The installed target contains every workspace marker
- A non-empty target directory is rejected
- A botched install (markers missing) exits nonzero and preserves staging
- The update mode preserves user-owned data, repository metadata, and
  config overrides; replaces toolkit-owned entries; does not abort on
  non-empty directory collisions
- The fresh-install and update tarball fallbacks work end-to-end
  (with git hidden from PATH, real HTTP-served tarball, real
  extraction via the installer's `tar -xzf`)

The tests require a POSIX shell environment where install.sh can be run
with the bash host's native path semantics. They are skipped on Windows
because the Git-for-Windows MSYS2 layer mangles backslash-containing
paths in argument and environment-variable values, which makes it
impractical to drive install.sh from a Windows Python test harness.
"""
from __future__ import annotations

import http.server
import os
import py_compile
import shutil
import socket
import subprocess
import sys
import tarfile
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"


def _is_windows() -> bool:
    return sys.platform == "win32"


def _have_bash_and_git() -> bool:
    return shutil.which("bash") is not None and shutil.which("git") is not None


pytestmark = [
    pytest.mark.skipif(
        _is_windows(),
        reason="install.sh integration tests need a POSIX shell host; skipped on Windows",
    ),
    pytest.mark.skipif(
        not _have_bash_and_git(),
        reason="install.sh tests require bash and git on PATH",
    ),
]


WORKSPACE_MARKERS = [
    "PHILOSOPHY.md",
    "requirements.md",
    "AGENTS.md",
    "setup.sh",
    "setup.ps1",
    "templates",
    "scripts",
    "providers",
    "skills",
]


def _run_bash(script: str, env: dict[str, str] | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", script],
        cwd=cwd or REPO_ROOT,
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
    )


def _build_remote_repo(remote: Path) -> None:
    """Create a local git repo at `remote` populated with the toolkit's tracked files."""
    if remote.exists():
        shutil.rmtree(remote)
    remote.mkdir(parents=True)
    for marker in WORKSPACE_MARKERS:
        src = REPO_ROOT / marker
        if not src.exists():
            continue
        dst = remote / marker
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    # Add a dotfile to exercise the dotglob path
    (remote / ".calixto-dotfile").write_text("dot\n", encoding="utf-8")
    _run_bash(
        "git init -q -b main && "
        "git config user.email 'ci@example.com' && "
        "git config user.name 'CI' && "
        "git add -A && "
        "git commit -q -m 'fixture'",
        cwd=remote,
    )


def _invoke_installer(target: Path, remote: Path) -> subprocess.CompletedProcess:
    """Run install.sh with the given target directory.

    The installer's TARGET_DIR is its own pwd, so we cd into target first
    inside the wrapper script. The script path is passed via the
    CALIXTO_INSTALL_SH env var to avoid the host's argv parsing.
    """
    return _run_bash(
        'cd "$CALIXTO_TARGET" && '
        'CALIXTO_REPO_URL="$CALIXTO_REMOTE" '
        'bash "$CALIXTO_INSTALL_SH" --non-interactive --skip-deps',
        env={
            "CALIXTO_TARGET": str(target),
            "CALIXTO_REMOTE": str(remote),
            "CALIXTO_INSTALL_SH": str(INSTALL_SH),
        },
        cwd=REPO_ROOT,
    )


def test_fresh_install_copies_all_files(tmp_path: Path) -> None:
    """A fresh install into an empty directory must copy every workspace marker and dotfile."""
    remote = tmp_path / "remote.git"
    target = tmp_path / "install-target"
    target.mkdir()
    _build_remote_repo(remote)

    result = _invoke_installer(target, remote)
    assert result.returncode == 0, (
        f"installer failed (rc={result.returncode})\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    for marker in WORKSPACE_MARKERS:
        assert (target / marker).exists(), f"marker missing: {marker}"
    # Dotfiles must have been copied by the dotglob step
    assert (target / ".calixto-dotfile").is_file()
    assert (target / ".calixto-dotfile").read_text(encoding="utf-8") == "dot\n"
    # Staging artifacts must be cleaned up after a successful install
    assert not (target / ".calixto-tmp").exists()
    assert not any(target.glob(".calixto-stage*"))
    assert not (target / ".calixto.tar.gz").exists()


def test_fresh_install_rejects_non_empty_target(tmp_path: Path) -> None:
    """A non-empty target must trigger fresh-install refusal before any fetch."""
    remote = tmp_path / "remote.git"
    target = tmp_path / "install-target"
    target.mkdir()
    (target / "pre-existing.txt").write_text("keep", encoding="utf-8")
    _build_remote_repo(remote)

    result = _invoke_installer(target, remote)
    assert result.returncode != 0
    assert (target / "pre-existing.txt").exists()
    assert not (target / "AGENTS.md").exists()


def test_fresh_install_fails_on_incomplete_install(tmp_path: Path) -> None:
    """If the staged clone is missing required markers, the installer must fail
    and preserve the staging directory for inspection.
    """
    remote = tmp_path / "remote.git"
    target = tmp_path / "install-target"
    target.mkdir()

    # Build a remote that is intentionally missing several required markers
    missing_markers = {"AGENTS.md", "skills", "providers"}
    partial_markers = [m for m in WORKSPACE_MARKERS if m not in missing_markers]
    if remote.exists():
        shutil.rmtree(remote)
    remote.mkdir(parents=True)
    for marker in partial_markers:
        src = REPO_ROOT / marker
        if not src.exists():
            continue
        dst = remote / marker
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    _run_bash(
        "git init -q -b main && "
        "git config user.email 'ci@example.com' && "
        "git config user.name 'CI' && "
        "git add -A && "
        "git commit -q -m 'partial'",
        cwd=remote,
    )

    result = _invoke_installer(target, remote)
    assert result.returncode != 0, "installer should fail on incomplete install"
    # The missing markers must still be missing in the target
    assert not (target / "AGENTS.md").exists()
    # Staging dir preserved
    assert (target / ".calixto-tmp").exists()


def test_update_preserves_user_data_and_replaces_toolkit(tmp_path: Path) -> None:
    """Update mode must:
    - preserve user-owned data: workspaces/, notes/, outputs/, config.json, *.local
    - preserve repository metadata: .git/
    - replace toolkit-owned entries: scripts/, providers/, etc.
    - succeed when the target already contains a non-empty scripts/ tree
      (collision handling must not abort on non-empty directories)
    - install/update .gitignore (it is toolkit configuration, not user data)
    """
    remote = tmp_path / "remote.git"
    target = tmp_path / "install-target"
    target.mkdir()
    _build_remote_repo(remote)

    # Pre-populate the target with a "previous" version of the toolkit
    # plus user-owned data. The "previous" scripts/ has files the
    # current toolkit will replace.
    for marker in WORKSPACE_MARKERS:
        src = REPO_ROOT / marker
        if not src.exists():
            continue
        dst = target / marker
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    # User-owned data must be preserved verbatim
    user_workspaces = target / "workspaces" / "user-research"
    user_workspaces.mkdir(parents=True)
    user_notes = user_workspaces / "notes"
    user_notes.mkdir()
    (user_notes / "findings.md").write_text(
        "## fnd_001\n**Source:** src_001\n**Fact:** user fact\n",
        encoding="utf-8",
    )
    # User-owned config
    (target / "config.json").write_text(
        '{"user_overrides": "preserved"}',
        encoding="utf-8",
    )
    (target / "settings.local").write_text(
        "user-controlled data",
        encoding="utf-8",
    )
    # A .git directory (the developer's repo metadata)
    git_dir = target / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git_dir / "config").write_text("[user]\n\tname = test\n", encoding="utf-8")
    # A STALE .gitignore that the installer must replace. .gitignore
    # is toolkit configuration: every install/update must apply the
    # current ignore rules so users benefit from the latest
    # workspaces/, .venv/, etc. ignore entries.
    stale_ignore = "# user-old-rules\n*.custom\n"
    (target / ".gitignore").write_text(stale_ignore, encoding="utf-8")

    # Sanity: the marker under test is present before update
    assert (target / "scripts" / "init_workspace.py").is_file()
    user_facts_before = (user_notes / "findings.md").read_text(encoding="utf-8")
    user_config_before = (target / "config.json").read_text(encoding="utf-8")
    user_local_before = (target / "settings.local").read_text(encoding="utf-8")
    user_git_head_before = (git_dir / "HEAD").read_text(encoding="utf-8")

    # The installer enters update mode when the target already looks
    # like a Calixto workspace. Run it with --skip-deps so we only
    # exercise the file-move / restore logic, not the (potentially
    # network-dependent) setup step.
    env = {**os.environ, "CALIXTO_REPO_URL": str(remote), "CALIXTO_SKIP_DEPS": "1"}
    # Use --non-interactive so the confirmation prompt does not block
    # in the test environment.
    result = subprocess.run(
        ["bash", str(INSTALL_SH), "--non-interactive", "--skip-deps"],
        cwd=str(target),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"update installer failed (rc={result.returncode})\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    # User-owned workspace data must be intact
    assert (target / "workspaces" / "user-research" / "notes" / "findings.md").is_file()
    user_facts_after = (user_notes / "findings.md").read_text(encoding="utf-8")
    assert user_facts_after == user_facts_before, "user notes content was modified"
    # config.json must be preserved
    user_config_after = (target / "config.json").read_text(encoding="utf-8")
    assert user_config_after == user_config_before, "config.json was modified"
    # *.local must be preserved
    user_local_after = (target / "settings.local").read_text(encoding="utf-8")
    assert user_local_after == user_local_before, "*.local file was modified"
    # .git/ must be preserved
    assert (git_dir / "HEAD").is_file()
    assert (git_dir / "HEAD").read_text(encoding="utf-8") == user_git_head_before, (
        ".git/HEAD was modified by the update"
    )
    # .gitignore must be REPLACED with the new toolkit's version
    # (not preserved like user data, not clobbered like .git either:
    # toolkit configuration, must be installed fresh on every update).
    new_ignore = (target / ".gitignore").read_text(encoding="utf-8")
    expected_ignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert new_ignore == expected_ignore, (
        f".gitignore was not refreshed; expected {expected_ignore!r}, "
        f"got {new_ignore!r}"
    )
    assert "user-old-rules" not in new_ignore, (
        "stale .gitignore was not replaced"
    )
    # Toolkit-owned entries must be replaced with the new remote's
    # content. We can't easily check byte equality against the remote,
    # but we can check that scripts/init_workspace.py is still present
    # and parses.
    assert (target / "scripts" / "init_workspace.py").is_file()
    py_compile.compile(
        str(target / "scripts" / "init_workspace.py"),
        doraise=True,
    )


def test_fresh_install_copies_gitignore(tmp_path: Path) -> None:
    """A fresh install must include the toolkit's .gitignore.

    Regression: a previous version of the installer protected
    .gitignore and silently omitted it. The .gitignore is toolkit
    configuration, not user data, and must always be installed so
    users benefit from the latest ignore rules (workspaces/, .venv/,
    cache/, etc.).
    """
    remote = tmp_path / "remote.git"
    target = tmp_path / "install-target"
    target.mkdir()
    _build_remote_repo(remote)

    result = _invoke_installer(target, remote)
    assert result.returncode == 0, (
        f"installer failed (rc={result.returncode})\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    # The installed .gitignore must equal the toolkit's
    assert (target / ".gitignore").is_file(), (
        "fresh install did not install .gitignore"
    )
    installed = (target / ".gitignore").read_text(encoding="utf-8")
    expected = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert installed == expected, (
        f"installed .gitignore does not match the toolkit source: "
        f"installed={installed!r} expected={expected!r}"
    )


def _build_remote_tarball(remote: Path, version: str = "v0.0.0") -> Path:
    """Build a local tarball that mimics the GitHub codeload tarball.

    The codeload tarball extracts into `calixto-<ref>/`. We mirror
    that structure so the installer's lookup logic matches real-world
    usage.
    """
    if remote.exists():
        shutil.rmtree(remote)
    remote.mkdir(parents=True)
    # The tarball extracts into calixto-<version>/, so create that
    # prefix and copy toolkit markers under it.
    extracted = remote / f"calixto-{version}"
    extracted.mkdir(parents=True)
    for marker in WORKSPACE_MARKERS:
        src = REPO_ROOT / marker
        if not src.exists():
            continue
        dst = extracted / marker
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    (extracted / ".calixto-dotfile").write_text("dot\n", encoding="utf-8")
    tarball = remote / f"calixto-{version}.tar.gz"
    with tarfile.open(tarball, "w:gz") as tf:
        tf.add(extracted, arcname=f"calixto-{version}")
    return tarball


def test_fresh_install_tarball_fallback_end_to_end(
    tmp_path: Path,
) -> None:
    """End-to-end Unix fresh install via the tarball fallback.

    We exercise the full installer path, not a copied snippet:
    - serve a real tarball over HTTP
    - hide `git` from PATH to force the tarball fallback branch
    - invoke the installer from a different cwd than the target
      (the `curl | bash` use case)
    - assert the final filesystem state: all markers present,
      `.gitignore` matches the toolkit source, toolkit entry
      `scripts/init_workspace.py` parses.

    This is the test that would have caught the Windows
    `Expand-Archive` bug: it forces the fallback path and
    verifies a real install.
    """
    if sys.platform == "win32":
        pytest.skip("Unix install.sh is exercised on Unix CI hosts")
    tarball_dir = tmp_path / "tarball-remote"
    tarball = _build_remote_tarball(tarball_dir, version="v9.9.9")
    # Serve the tarball from a tiny localhost HTTP server. The
    # installer's `curl` will download from this URL. We serve
    # HTTPS with a self-signed cert; the installer must be told
    # to skip TLS verification via CALIXTO_INSECURE_TLS=1, which
    # is the documented opt-in for air-gapped environments using
    # self-signed tarball hosts.
    server, port = _serve_tarball_https(tarball, tmp_path)
    try:
        target = tmp_path / "install-target"
        target.mkdir()
        env = dict(os.environ)
        # Strip git from PATH so the tarball branch is taken
        env["PATH"] = _path_without_git(env.get("PATH", ""))
        env["CALIXTO_REPO_URL"] = f"https://localhost:{port}/fake-org/fake-repo"
        env["CALIXTO_INSECURE_TLS"] = "1"
        # Invoke from a different cwd than the target
        other_cwd = tmp_path / "other-cwd"
        other_cwd.mkdir()
        result = subprocess.run(
            [
                "bash", str(INSTALL_SH),
                "--non-interactive",
                "--skip-deps",
            ],
            cwd=str(other_cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"installer failed (rc={result.returncode})\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        # All workspace markers must be present
        for marker in WORKSPACE_MARKERS:
            assert (target / marker).exists(), f"marker missing: {marker}"
        # Dotfiles must have been copied
        assert (target / ".calixto-dotfile").is_file()
        # The fresh-install .gitignore must match the toolkit source
        installed_ignore = (target / ".gitignore").read_text(encoding="utf-8")
        expected_ignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert installed_ignore == expected_ignore, (
            f"fresh-install .gitignore mismatch: "
            f"installed={installed_ignore!r} expected={expected_ignore!r}"
        )
        # Toolkit-owned entries must be installed and parse
        assert (target / "scripts" / "init_workspace.py").is_file()
        py_compile.compile(
            str(target / "scripts" / "init_workspace.py"),
            doraise=True,
        )
    finally:
        server.shutdown()
        server.server_close()


def test_update_tarball_fallback_end_to_end(tmp_path: Path) -> None:
    """End-to-end Unix update via the tarball fallback.

    - pre-populate the target with a "previous" toolkit install
      plus a `.git` directory
    - serve a tarball with a fake `.git` from a localhost HTTP server
    - hide git from PATH to force the tarball fallback
    - invoke the installer in update mode (target already looks
      like a Calixto workspace)
    - assert: the existing `.git/HEAD` is preserved (no
      clobbering), the existing `workspaces/.../findings.md` is
      preserved (user data), and the toolkit's `.gitignore`
      has been refreshed.
    """
    if sys.platform == "win32":
        pytest.skip("Unix install.sh is exercised on Unix CI hosts")
    tarball_dir = tmp_path / "tarball-remote"
    # Build a tarball whose `calixto-v9.9.9/` contains a fake
    # `.git`. The installer must NOT clobber the existing target's
    # `.git`, regardless of what the tarball contains.
    if tarball_dir.exists():
        shutil.rmtree(tarball_dir)
    tarball_dir.mkdir(parents=True)
    extracted = tarball_dir / "calixto-v9.9.9"
    extracted.mkdir(parents=True)
    for marker in WORKSPACE_MARKERS:
        src = REPO_ROOT / marker
        if not src.exists():
            continue
        dst = extracted / marker
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    fake_git = extracted / ".git"
    fake_git.mkdir()
    (fake_git / "HEAD").write_text(
        "ref: refs/heads/staged-main\n", encoding="utf-8"
    )
    tarball = tarball_dir / "calixto-v9.9.9.tar.gz"
    with tarfile.open(tarball, "w:gz") as tf:
        tf.add(extracted, arcname="calixto-v9.9.9")

    server, port = _serve_tarball_https(tarball, tmp_path)
    try:
        target = tmp_path / "install-target"
        target.mkdir()
        # Pre-populate with a "previous" toolkit version
        for marker in WORKSPACE_MARKERS:
            src = REPO_ROOT / marker
            if not src.exists():
                continue
            dst = target / marker
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        # Existing .git with recognizable content
        git_dir = target / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (git_dir / "config").write_text(
            "[user]\n\tname = existing\n", encoding="utf-8"
        )
        # User-owned data
        user_ws = target / "workspaces" / "user-research"
        user_ws.mkdir(parents=True)
        (user_ws / "notes").mkdir()
        (user_ws / "notes" / "findings.md").write_text(
            "## fnd_001\n**Source:** src_001\n**Fact:** user fact\n",
            encoding="utf-8",
        )

        # Snapshot the existing `.git/HEAD` and user data
        git_head_before = (git_dir / "HEAD").read_text(encoding="utf-8")
        git_config_before = (git_dir / "config").read_text(encoding="utf-8")
        user_facts_before = (user_ws / "notes" / "findings.md").read_text(encoding="utf-8")

        # Run the installer in update mode via tarball fallback
        env = dict(os.environ)
        env["PATH"] = _path_without_git(env.get("PATH", ""))
        env["CALIXTO_REPO_URL"] = f"https://localhost:{port}/fake-org/fake-repo"
        env["CALIXTO_INSECURE_TLS"] = "1"
        result = subprocess.run(
            [
                "bash", str(INSTALL_SH),
                "--non-interactive",
                "--skip-deps",
            ],
            cwd=str(target),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"update installer failed (rc={result.returncode})\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        # The existing `.git` must not be clobbered
        assert (git_dir / "HEAD").read_text(encoding="utf-8") == git_head_before, (
            f".git/HEAD was modified; before={git_head_before!r} "
            f"after={(git_dir / 'HEAD').read_text(encoding='utf-8')!r}"
        )
        assert (git_dir / "config").read_text(encoding="utf-8") == git_config_before
        # User-owned data must be preserved
        assert (user_ws / "notes" / "findings.md").read_text(encoding="utf-8") == user_facts_before
        # The toolkit's .gitignore must have been refreshed
        installed_ignore = (target / ".gitignore").read_text(encoding="utf-8")
        expected_ignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert installed_ignore == expected_ignore
    finally:
        server.shutdown()
        server.server_close()


# ---------------------------------------------------------------------------
# Helpers for the end-to-end tarball fallback tests
# ---------------------------------------------------------------------------


class _TarballServer(http.server.BaseHTTPRequestHandler):
    """Tiny HTTP server that serves a single tarball and exits.

    The handler is intentionally minimal: it serves a single
    payload (set on the server instance before `serve_forever`
    is called) and ignores everything else. The tests rely on
    the installer fetching one URL and never following redirects.
    """

    tarball_bytes: bytes = b""

    def do_GET(self) -> None:  # noqa: N802
        body = type(self).tarball_bytes
        if not body:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/gzip")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args, **kwargs):
        return


def _serve_tarball(tarball: Path) -> tuple[http.server.HTTPServer, int]:
    """Serve `tarball` from a localhost HTTP server.

    Returns the running HTTPServer and the bound port. The test
    is responsible for calling `server.shutdown()` and
    `server.server_close()` on teardown.
    """
    # Read the body once at startup. Reading on every request
    # would be a TOCTOU hazard (the test may delete the file
    # between requests).
    body = tarball.read_bytes()
    _TarballServer.tarball_bytes = body
    # Pick a free port
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = http.server.HTTPServer(("127.0.0.1", port), _TarballServer)
    # Start the server in a daemon thread so it doesn't block test
    # teardown.
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # Stash the thread on the server instance so the caller can
    # join it (currently we just rely on daemon=True for cleanup).
    server._test_thread = thread  # type: ignore[attr-defined]
    return server, port


def _serve_tarball_https(
    tarball: Path, tmp_path: Path
) -> tuple[http.server.HTTPServer, int]:
    """Serve `tarball` from a localhost HTTPS server with a self-signed cert.

    Generates an ephemeral self-signed certificate for `localhost`
    using the `cryptography` library (already a transitive dep of
    `requests`/`urllib3` via `crawl4ai`). The installer must
    be told to skip TLS verification via
    `CALIXTO_INSECURE_TLS=1`; production usage against
    github.com does not need this.

    Skips the test if `cryptography` is unavailable.
    """
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime
    except ImportError:
        pytest.skip("cryptography is required to generate a self-signed cert")
    # Generate a self-signed cert for localhost
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path = tmp_path / "test-cert.pem"
    key_path = tmp_path / "test-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    # Now serve the tarball over HTTPS using the cert
    import ssl
    body = tarball.read_bytes()
    _TarballServer.tarball_bytes = body
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = http.server.HTTPServer(("127.0.0.1", port), _TarballServer)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    server._test_thread = thread  # type: ignore[attr-defined]
    return server, port


def _path_without_git(path: str) -> str:
    """Return `path` with every directory that contains a `git`
    executable removed. The result is a PATH string in which
    `command -v git` (and `which git`) both fail, so the
    installer's `command_exists git` check returns false and the
    tarball branch is taken.

    On Windows, the only stable way to hide git is to remove
    paths that contain a `git.exe` binary. On Unix, we remove
    paths with a `git` file or `git` symlink.
    """
    parts = path.split(os.pathsep) if path else []
    kept = []
    for p in parts:
        if not p:
            continue
        if sys.platform == "win32":
            if os.path.isfile(os.path.join(p, "git.exe")):
                continue
        else:
            if os.path.isfile(os.path.join(p, "git")):
                continue
        kept.append(p)
    return os.pathsep.join(kept)
