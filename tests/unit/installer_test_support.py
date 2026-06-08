"""Shared helpers for installer integration tests."""

from __future__ import annotations

import http.server
import os
import shutil
import socket
import ssl
import subprocess
import sys
import tarfile
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

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

TOOLKIT_ROOT_ENTRIES = [
    ".gitignore",
    ".python-version",
    "AGENTS.md",
    "LICENSE",
    "PHILOSOPHY.md",
    "README.md",
    "adapters",
    "docs",
    "examples",
    "install.ps1",
    "install.sh",
    "providers",
    "pyproject.toml",
    "requirements.md",
    "scripts",
    "setup.ps1",
    "setup.sh",
    "skills",
    "templates",
    "tests",
]


def have_pwsh() -> bool:
    return shutil.which("pwsh") is not None or shutil.which("powershell") is not None


def pwsh_executable() -> str:
    exe = shutil.which("pwsh") or shutil.which("powershell")
    assert exe is not None
    return exe


def have_git_bash() -> bool:
    if sys.platform != "win32":
        return shutil.which("bash") is not None
    return any(Path(candidate).exists() for candidate in _bash_candidates())


def bash_executable() -> str:
    if sys.platform != "win32":
        exe = shutil.which("bash")
        assert exe is not None
        return exe
    for candidate in _bash_candidates():
        if Path(candidate).exists():
            return candidate
    raise AssertionError("Git Bash is not available.")


def _bash_candidates() -> list[str]:
    return [
        "C:/Program Files/Git/bin/bash.exe",
        "C:/Program Files/Git/usr/bin/bash.exe",
    ]


def create_isolated_checkout(tmp_path: Path) -> Path:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    for entry_name in TOOLKIT_ROOT_ENTRIES:
        source = REPO_ROOT / entry_name
        destination = checkout / entry_name
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    return checkout


def copy_checkout_tree(checkout: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for entry_name in TOOLKIT_ROOT_ENTRIES:
        source = checkout / entry_name
        target = destination / entry_name
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def init_git_repo(path: Path, branch: str = "main") -> None:
    subprocess.run(["git", "init", "-q", "-b", branch], cwd=path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "ci@example.com"],
        cwd=path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "CI"],
        cwd=path,
        check=True,
    )
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=path, check=True)


def install_toolkit_tree(checkout: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for entry_name in TOOLKIT_ROOT_ENTRIES:
        source = checkout / entry_name
        destination = target / entry_name
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def stage_archive_root(
    checkout: Path,
    parent: Path,
    root_name: str,
    *,
    remove_entries: set[str] | None = None,
    add_text_files: dict[str, str] | None = None,
    add_directories: list[str] | None = None,
    include_fake_git: bool = False,
) -> Path:
    root = parent / root_name
    install_toolkit_tree(checkout, root)
    for entry_name in remove_entries or set():
        path = root / entry_name
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    for relative, content in (add_text_files or {}).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    for relative in add_directories or []:
        (root / relative).mkdir(parents=True, exist_ok=True)
    if include_fake_git:
        fake_git = root / ".git"
        fake_git.mkdir()
        (fake_git / "HEAD").write_text("ref: refs/heads/staged-main\n", encoding="utf-8")
    return root


def build_archive(
    archive_path: Path,
    roots: list[Path],
    *,
    extra_members: list[tuple[str, bytes, int]] | None = None,
) -> Path:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "w:gz") as tf:
        for root in roots:
            tf.add(root, arcname=root.name)
        for name, payload, mode in extra_members or []:
            info = tarfile.TarInfo(name=name)
            info.size = len(payload)
            info.mode = mode
            tf.addfile(info, fileobj=_BytesReader(payload))
    return archive_path


class _BytesReader:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._offset = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._payload) - self._offset
        chunk = self._payload[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


class _TarballHandler(http.server.BaseHTTPRequestHandler):
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

    def log_message(self, *args, **kwargs) -> None:
        return


def serve_archive_https(
    tarball: Path, tmp_path: Path
) -> tuple[http.server.HTTPServer, str, str]:
    try:
        import datetime

        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError as exc:  # pragma: no cover - enforced in CI
        raise AssertionError(
            "cryptography must be installed for installer archive tests"
        ) from exc

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
        .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(minutes=1))
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    cert_path = tmp_path / "archive-cert.pem"
    key_path = tmp_path / "archive-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

    _TarballHandler.tarball_bytes = tarball.read_bytes()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    server = http.server.HTTPServer(("127.0.0.1", port), _TarballHandler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    server._test_thread = thread  # type: ignore[attr-defined]
    return server, f"https://localhost:{port}/archive.tar.gz", str(cert_path)


def path_without_git(path: str) -> str:
    parts = path.split(os.pathsep) if path else []
    kept: list[str] = []
    for part in parts:
        if not part:
            continue
        if sys.platform == "win32":
            if any(
                os.path.isfile(os.path.join(part, candidate))
                for candidate in ("git.exe", "git.cmd", "git.bat")
            ):
                continue
        else:
            if os.path.isfile(os.path.join(part, "git")):
                continue
        kept.append(part)
    return os.pathsep.join(kept)


def invoke_unix_installer(
    checkout: Path,
    cwd: Path,
    env: dict[str, str],
    args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [bash_executable(), str(checkout / "install.sh"), *(args or [])]
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


def invoke_windows_installer(
    checkout: Path,
    cwd: Path,
    env: dict[str, str],
    args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        pwsh_executable(),
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(checkout / "install.ps1"),
        *(args or []),
    ]
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


def installer_artifacts(target: Path) -> list[Path]:
    names = [
        ".calixto-install-source",
        ".calixto-update-source",
        ".calixto-update-transaction",
    ]
    return [target / name for name in names]


def assert_no_installer_artifacts(target: Path) -> None:
    leftovers = [path for path in installer_artifacts(target) if path.exists()]
    assert not leftovers, f"unexpected installer artifacts left behind: {leftovers}"


def ensure_user_workspace(target: Path) -> Path:
    workspace = target / "workspaces" / "user-research"
    (workspace / "notes").mkdir(parents=True, exist_ok=True)
    findings = workspace / "notes" / "findings.md"
    findings.write_text(
        "## fnd_001\n**Source:** src_001\n**Fact:** user fact\n",
        encoding="utf-8",
    )
    return findings


def create_repo_metadata(target: Path) -> Path:
    git_dir = target / ".git"
    git_dir.mkdir(parents=True, exist_ok=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git_dir / "config").write_text("[user]\n\tname = existing\n", encoding="utf-8")
    return git_dir


def make_remote_git_repo(
    checkout: Path,
    remote: Path,
    *,
    remove_entries: set[str] | None = None,
    add_text_files: dict[str, str] | None = None,
) -> Path:
    copy_checkout_tree(checkout, remote)
    for entry_name in remove_entries or set():
        path = remote / entry_name
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    for relative, content in (add_text_files or {}).items():
        target = remote / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    init_git_repo(remote)
    return remote
