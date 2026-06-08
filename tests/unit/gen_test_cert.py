"""Generate a self-signed cert+key pair for the localhost HTTPS
fixture used by the installer integration tests.

We commit the generated files to the test directory so the
tests do not depend on a `cryptography` or `openssl` install
at test time. Regenerate with:

    python -c "from tests.unit.gen_test_cert import main; main()"
"""
from __future__ import annotations

import datetime
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent
CERT_PATH = OUT_DIR / "test-cert.pem"
KEY_PATH = OUT_DIR / "test-key.pem"


def main() -> None:
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
    except ImportError:
        raise SystemExit(
            "cryptography is required to generate the test cert. "
            "Install it with: pip install cryptography"
        )
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
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    CERT_PATH.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    KEY_PATH.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    print(f"wrote {CERT_PATH}")
    print(f"wrote {KEY_PATH}")


if __name__ == "__main__":
    main()
