from __future__ import annotations

from pathlib import Path

from app.core.config import BASE_DIR
from app.core.runtime import get_resource_root

ENV_PATH = BASE_DIR / ".env"
ENV_TEMPLATE_PATH = get_resource_root() / ".env.example"


def read_env_file(path: Path = ENV_PATH) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def ensure_env_file(path: Path = ENV_PATH) -> Path:
    if path.exists():
        return path

    if ENV_TEMPLATE_PATH.exists():
        path.write_text(ENV_TEMPLATE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        path.write_text("", encoding="utf-8")
    return path


def write_env_values(updates: dict[str, str], path: Path = ENV_PATH) -> Path:
    ensure_env_file(path)
    current = read_env_file(path)
    current.update(updates)
    server_host = current.get("SERVER_HOST", "").strip().lower()
    if server_host in {"127.0.0.1", "0.0.0.0", "::1", "[::1]"}:
        current["SERVER_HOST"] = "localhost"
    lines = [f"{key}={value}" for key, value in sorted(current.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
