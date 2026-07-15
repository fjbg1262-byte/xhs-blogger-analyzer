"""Subprocess wrapper around analyze_all.py."""

import json
import subprocess
import sys
from pathlib import Path
from backend.config import settings, BASE_DIR
from backend.runtime import find_resource, is_frozen


def run_analysis(
    notes_path: str,
    profile_path: str,
    output_path: str,
    contents_path=None,
    quality_output_path=None,
    timeout: int = 120,
) -> dict:
    """Run analyze_all.py as a subprocess and return parsed results JSON."""
    if is_frozen():
        cmd = [
            sys.executable,
            "--xhs-run",
            "analyze_all",
            "--notes", notes_path,
            "--profile", profile_path,
            "--output", output_path,
        ]
    else:
        cmd = [
            settings.python_exe,
            str(find_resource("analyze_all.py")),
            "--notes", notes_path,
            "--profile", profile_path,
            "--output", output_path,
        ]
    if contents_path and Path(contents_path).exists():
        cmd.extend(["--contents", contents_path])
    if quality_output_path:
        cmd.extend(["--quality-output", quality_output_path])

    result = subprocess.run(
        cmd,
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"analyze_all.py failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout[-500:]}\n"
            f"stderr: {result.stderr[-500:]}"
        )

    with open(output_path, "r", encoding="utf-8") as f:
        return json.load(f)
