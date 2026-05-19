"""Small stdlib-only environment file loader.

The project intentionally avoids adding a dependency just to read local
developer secrets. This parser supports the simple `.env` shape we need:
`KEY=value`, optional `export KEY=value`, comments, and quoted values.
Existing process environment values win unless `override=True`.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_env_file(path: Path | str, *, override: bool = False) -> dict[str, str]:
    """Load environment variables from `path`; return the values applied."""
    env_path = Path(path)
    if not env_path.exists():
        return {}

    loaded: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = _strip_inline_comment(value.strip())
        value = _strip_matching_quotes(value)
        if override or key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded


def load_default_env_files(*, start_dir: Path | str | None = None) -> dict[str, str]:
    """Load local env files from the workspace root, if present.

    `.env` is the canonical filename. `.emv` is accepted as a forgiving alias
    because it is easy to mistype and was used in one setup request.
    """
    root = Path(start_dir or Path.cwd())
    loaded: dict[str, str] = {}
    for name in (".env", ".emv"):
        loaded.update(load_env_file(root / name))
    return loaded


def _strip_matching_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _strip_inline_comment(value: str) -> str:
    if not value or value[0] in {"'", '"'}:
        return value
    marker = value.find(" #")
    if marker == -1:
        return value
    return value[:marker].rstrip()


__all__ = ["load_default_env_files", "load_env_file"]
