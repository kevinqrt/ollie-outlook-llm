from __future__ import annotations

import ipaddress
import platform
import subprocess
import textwrap
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.core.config import BASE_DIR
from app.core.env_manager import write_env_values

CERT_DIR = BASE_DIR / "certs"
CERT_PATH = CERT_DIR / "localhost.pem"
KEY_PATH = CERT_DIR / "localhost-key.pem"


def ensure_localhost_certificate() -> tuple[Path, Path]:
    CERT_DIR.mkdir(parents=True, exist_ok=True)

    if CERT_PATH.exists() and KEY_PATH.exists():
        return CERT_PATH, KEY_PATH

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "DE"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Ollie Local Development"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ]
    )

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]
            ),
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
    return CERT_PATH, KEY_PATH


def ensure_https_env() -> tuple[Path, Path]:
    cert_path, key_path = ensure_localhost_certificate()
    write_env_values(
        {
            "SSL_CERTFILE": str(cert_path),
            "SSL_KEYFILE": str(key_path),
        }
    )
    return cert_path, key_path


def trust_certificate_for_current_user(cert_path: Path = CERT_PATH) -> tuple[bool, str]:
    if platform.system() != "Windows":
        return False, "Automatic certificate trust is currently only implemented for Windows."

    if not cert_path.exists():
        return False, f"Certificate not found: {cert_path}"

    script = textwrap.dedent(
        f"""
        $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2('{cert_path}')
        foreach ($storeName in @('TrustedPeople', 'Root')) {{
            $store = New-Object System.Security.Cryptography.X509Certificates.X509Store($storeName, 'CurrentUser')
            $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
            $existing = $store.Certificates | Where-Object {{ $_.Thumbprint -eq $cert.Thumbprint }}
            if (-not $existing) {{
                $store.Add($cert)
            }}
            $store.Close()
        }}
        Write-Output 'trusted'
        """
    ).strip()

    try:
        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return True, "Certificate trusted for the current Windows user (TrustedPeople and Root)."
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        details = stderr or stdout or str(exc)
        return False, f"Failed to trust certificate: {details}"
