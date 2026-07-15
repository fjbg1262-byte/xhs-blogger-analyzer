"""Runtime path helpers for source and packaged Windows builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """Writable app folder: source root in dev, exe folder when packaged."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return SOURCE_ROOT


def bundled_root() -> Path:
    """PyInstaller internal resource folder, falling back to app root."""
    return Path(getattr(sys, "_MEIPASS", app_root())).resolve()


def find_resource(*parts: str) -> Path:
    """Find a read-only resource in the external app folder, bundle, or source."""
    relative = Path(*parts)
    candidates = [
        app_root() / relative,
        bundled_root() / relative,
        SOURCE_ROOT / relative,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def writable_path(*parts: str) -> Path:
    """Return a path intended for user data generated at runtime."""
    base = Path(os.environ.get("XHS_APP_HOME") or app_root())
    return base.joinpath(*parts)


def configure_runtime_environment() -> None:
    """Prefer packaged Node and Spider_XHS dependencies when present."""
    node_candidates = [
        app_root() / "runtime" / "node" / "node.exe",
        bundled_root() / "runtime" / "node" / "node.exe",
    ]
    for node_exe in node_candidates:
        if node_exe.exists():
            os.environ["PATH"] = str(node_exe.parent) + os.pathsep + os.environ.get("PATH", "")
            os.environ.setdefault("EXECJS_RUNTIME", "Node")
            break

    node_modules = find_resource("spider_xhs", "node_modules")
    if node_modules.exists():
        existing = os.environ.get("NODE_PATH", "")
        node_path = str(node_modules)
        if node_path not in existing:
            os.environ["NODE_PATH"] = node_path + (os.pathsep + existing if existing else "")
