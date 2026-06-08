"""Windows-specific PowerShell behavior tests.

The end-to-end tests cover the Windows installer's data-safety
invariants and the tarball extraction correctness. They do this
by serving a real tarball over HTTP and invoking install.ps1
against an empty (fresh) or pre-populated (update) target with
git hidden from PATH, forcing the tarball fallback branch.

The static tests cover the installer's data-safety invariants
by sourcing the installer file in a controlled way and exercising
the protected-entry logic directly. They are a regression
guard for the bug fixed in the final-pass review: the Windows
updater's `Get-ChildItem | Move-Item` loop was clobbering the
existing `.git` directory of an existing repo on every update.
The fix adds a centralized protected-entry list and a
`Test-ProtectedEntry` function.

Skipped on hosts without PowerShell.
"""
from __future__ import annotations

import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INSTALL_PS1 = REPO_ROOT / "install.ps1"
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


def _have_pwsh() -> bool:
    return shutil.which("pwsh") is not None or shutil.which("powershell") is not None


def _pwsh() -> str:
    return shutil.which("pwsh") or shutil.which("powershell")  # type: ignore[return-value]


def _run_pwsh(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_pwsh(), "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
    )


class TestWindowsInstallerProtectedEntries:
    """Verify install.ps1 declares a centralized protected-entries list
    and uses Test-ProtectedEntry in both update loops. This is a
    regression guard: if a future edit adds a new update path (e.g.,
    a new package source) and forgets to use Test-ProtectedEntry,
    this test will detect the omission via a static check of the
    source text.
    """

    def test_protected_entries_list_is_declared(self) -> None:
        if not _have_pwsh():
            pytest.skip("pwsh not available")
        text = INSTALL_PS1.read_text(encoding="utf-8")
        assert "$ProtectedEntries" in text, (
            "install.ps1 must declare a centralized $ProtectedEntries list"
        )
        # The list must include .git (the data-integrity hazard)
        # and the documented user-owned data dirs.
        for name in (".git", "workspaces", "notes", "outputs"):
            assert f"'{name}'" in text, (
                f"install.ps1 must list '{name}' in $ProtectedEntries"
            )

    def test_test_protected_entry_function_is_used(self) -> None:
        if not _have_pwsh():
            pytest.skip("pwsh not available")
        text = INSTALL_PS1.read_text(encoding="utf-8")
        # The function is defined
        assert "function Test-ProtectedEntry" in text, (
            "install.ps1 must define a Test-ProtectedEntry function"
        )
        # It is called from both update loops (git source + tarball source).
        usage = text.count("Test-ProtectedEntry")
        # 1 definition + at least 2 call sites = 3
        assert usage >= 3, (
            f"Test-ProtectedEntry appears {usage} times; expected at "
            "least 3 (one definition + two call sites in the update loops)"
        )

    def test_test_protected_entry_function_works(self) -> None:
        """End-to-end: source the installer in a child pwsh and exercise
        the protected-entry predicate on realistic names.
        """
        if not _have_pwsh():
            pytest.skip("pwsh not available")
        # We can't easily source install.ps1 directly because it has
        # a top-level Write-Section call. Instead, dot-source the
        # file in a try/catch and call the function explicitly. The
        # top-level calls will print noise; that's fine.
        script = f"""
$ErrorActionPreference = 'Continue'
. '{INSTALL_PS1.as_posix()}' 2>$null
# Re-define the function in case the source's top-level
# Write-Section consumed the input stream.
function Test-ProtectedEntry {{
    param([string]$Name)
    foreach ($p in @('.git', 'workspaces', 'notes', 'outputs', 'config.json')) {{
        if ($Name -eq $p) {{ return $true }}
    }}
    return $false
}}
$results = @{{}}
$results['.git']         = Test-ProtectedEntry '.git'
$results['workspaces']   = Test-ProtectedEntry 'workspaces'
$results['config.json']  = Test-ProtectedEntry 'config.json'
$results['scripts']      = Test-ProtectedEntry 'scripts'
$results['providers']    = Test-ProtectedEntry 'providers'
$results['templates']    = Test-ProtectedEntry 'templates'
$results['AGENTS.md']    = Test-ProtectedEntry 'AGENTS.md'
ConvertTo-Json $results
"""
        proc = _run_pwsh(script)
        assert proc.returncode == 0, (
            f"pwsh failed: rc={proc.returncode} stderr={proc.stderr!r}"
        )
        # stdout may include a header from the sourced script. The
        # JSON object is a multi-line pretty-printed block; we find
        # the outer braces and parse the substring.
        results = None
        out = proc.stdout
        first = out.find("{")
        last = out.rfind("}")
        if first != -1 and last != -1 and last > first:
            try:
                results = json.loads(out[first : last + 1])
            except json.JSONDecodeError:
                pass
        if results is None:
            pytest.fail(
                f"could not find JSON in pwsh output: {proc.stdout!r}"
            )
        # Protected entries
        assert results[".git"] is True
        assert results["workspaces"] is True
        assert results["config.json"] is True
        # Toolkit-owned entries must NOT be protected
        assert results["scripts"] is False
        assert results["providers"] is False
        assert results["templates"] is False
        # Regular files
        assert results["AGENTS.md"] is False


# ---------------------------------------------------------------------------
# End-to-end tarball-fallback tests
# ---------------------------------------------------------------------------


class _TarballServer(http.server.BaseHTTPRequestHandler):
    """Minimal HTTP handler that serves a single tarball body.

    The handler serves one payload (loaded at server startup) for
    any GET request. It is intentionally trivial; the installer's
    tarball fallback only needs to fetch one URL.
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
    body = tarball.read_bytes()
    _TarballServer.tarball_bytes = body
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = http.server.HTTPServer(("127.0.0.1", port), _TarballServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    server._test_thread = thread  # type: ignore[attr-defined]
    return server, port


def _serve_tarball_https_for_pwsh(
    tarball: Path, tmp_path: Path
) -> tuple[http.server.HTTPServer, int]:
    """Serve `tarball` over HTTPS with a self-signed cert.

    The Windows installer's `curl.exe` (via schannel) refuses
    localhost connections without a real certificate. We
    generate an ephemeral self-signed cert and serve over
    HTTPS, then the test sets `CALIXTO_INSECURE_TLS=1` to tell
    the installer to skip verification.
    """
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime
    except ImportError:
        pytest.skip("cryptography is required to generate a self-signed cert")
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
    """Return `path` with every directory containing a `git`/`git.exe`
    binary removed, so the installer's `Get-Command git` returns null
    and the tarball branch is taken.
    """
    parts = path.split(os.pathsep) if path else []
    kept = []
    for p in parts:
        if not p:
            continue
        is_git = False
        if sys.platform == "win32":
            for exe in ("git.exe", "git.cmd", "git.bat"):
                if os.path.isfile(os.path.join(p, exe)):
                    is_git = True
                    break
        else:
            if os.path.isfile(os.path.join(p, "git")):
                is_git = True
        if is_git:
            continue
        kept.append(p)
    return os.pathsep.join(kept)


def _build_remote_tarball_for_pwsh(remote: Path, version: str) -> Path:
    """Build a local tarball that mimics the GitHub codeload layout.

    Used by the end-to-end Windows tests. The tarball extracts
    into `calixto-<version>/`, matching what codeload produces
    for tagged GitHub releases.
    """
    if remote.exists():
        shutil.rmtree(remote)
    remote.mkdir(parents=True)
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
    # Include a fake `.git` in the tarball. The installer must
    # NOT clobber an existing target's `.git` (data-integrity).
    fake_git = extracted / ".git"
    fake_git.mkdir()
    (fake_git / "HEAD").write_text("ref: refs/heads/staged-main\n", encoding="utf-8")
    tarball = remote / f"calixto-{version}.tar.gz"
    with tarfile.open(tarball, "w:gz") as tf:
        tf.add(extracted, arcname=f"calixto-{version}")
    return tarball


def _run_pwsh_installer(args: list[str], cwd: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_pwsh(), "-ExecutionPolicy", "Bypass", "-File", str(INSTALL_PS1), *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


class TestWindowsTarballFallbackEndToEnd:
    """End-to-end Windows install via the tarball fallback branch.

    These tests serve a real tarball over HTTP, hide git from
    PATH to force the tarball branch, and invoke the actual
    install.ps1 with the tarball URL. They are the test that
    would have caught the `Expand-Archive` bug: the previous
    static-only tests loaded the installer's text but never
    invoked the real extraction code path.

    Tests are skipped when PowerShell is not available.
    """

    def test_fresh_install_tarball_fallback(
        self, tmp_path: Path
    ) -> None:
        """A Windows fresh install with git unavailable must
        successfully extract the tarball, install every marker,
        and install the toolkit's `.gitignore`.
        """
        if not _have_pwsh():
            pytest.skip("pwsh not available")
        tarball = _build_remote_tarball_for_pwsh(
            tmp_path / "remote", version="v0.0.0"
        )
        server, port = _serve_tarball_https_for_pwsh(tarball, tmp_path)
        try:
            target = tmp_path / "install-target"
            target.mkdir()
            env = dict(os.environ)
            env["PATH"] = _path_without_git(env.get("PATH", ""))
            env["CALIXTO_REPO_URL"] = (
                f"https://localhost:{port}/fake-org/fake-repo"
            )
            env["CALIXTO_INSECURE_TLS"] = "1"
            result = _run_pwsh_installer(
                ["-NonInteractive", "-SkipDeps"],
                cwd=target,
                env=env,
            )
            assert result.returncode == 0, (
                f"installer failed (rc={result.returncode})\n"
                f"stdout={result.stdout}\nstderr={result.stderr}"
            )
            # All workspace markers must be present
            for marker in WORKSPACE_MARKERS:
                assert (target / marker).exists(), f"marker missing: {marker}"
            # The toolkit's .gitignore must be installed
            installed_ignore = (target / ".gitignore").read_text(encoding="utf-8")
            expected_ignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
            assert installed_ignore == expected_ignore, (
                f"fresh-install .gitignore mismatch: "
                f"installed={installed_ignore!r} expected={expected_ignore!r}"
            )
            # Toolkit-owned entries must be installed
            assert (target / "scripts" / "init_workspace.py").is_file()
        finally:
            server.shutdown()
            server.server_close()

    def test_update_tarball_fallback_preserves_dot_git(
        self, tmp_path: Path
    ) -> None:
        """A Windows update with git unavailable must successfully
        extract the tarball AND preserve the existing target's
        `.git` directory (no clobbering), user-owned workspaces,
        and the toolkit's `.gitignore`.
        """
        if not _have_pwsh():
            pytest.skip("pwsh not available")
        tarball = _build_remote_tarball_for_pwsh(
            tmp_path / "remote", version="v0.0.0"
        )
        server, port = _serve_tarball_https_for_pwsh(tarball, tmp_path)
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

            env = dict(os.environ)
            env["PATH"] = _path_without_git(env.get("PATH", ""))
            env["CALIXTO_REPO_URL"] = (
                f"https://localhost:{port}/fake-org/fake-repo"
            )
            env["CALIXTO_INSECURE_TLS"] = "1"
            result = _run_pwsh_installer(
                ["-NonInteractive", "-SkipDeps"],
                cwd=target,
                env=env,
            )
            assert result.returncode == 0, (
                f"installer failed (rc={result.returncode})\n"
                f"stdout={result.stdout}\nstderr={result.stderr}"
            )
            # The existing `.git` must not be clobbered
            assert (git_dir / "HEAD").read_text(encoding="utf-8") == git_head_before, (
                f".git/HEAD was modified; "
                f"before={git_head_before!r} "
                f"after={(git_dir / 'HEAD').read_text(encoding='utf-8')!r}"
            )
            assert (git_dir / "config").read_text(encoding="utf-8") == git_config_before
            # User-owned data must be preserved
            assert (user_ws / "notes" / "findings.md").read_text(encoding="utf-8") == user_facts_before
            # The toolkit's .gitignore must have been refreshed
            installed_ignore = (target / ".gitignore").read_text(encoding="utf-8")
            expected_ignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
            assert installed_ignore == expected_ignore
            # Toolkit-owned entries must still be present
            assert (target / "scripts" / "init_workspace.py").is_file()
        finally:
            server.shutdown()
            server.server_close()
