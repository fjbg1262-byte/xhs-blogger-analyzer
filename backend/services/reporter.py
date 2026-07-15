"""Subprocess wrapper around generate_reports.py."""

import subprocess
from pathlib import Path
from backend.config import settings, BASE_DIR


def generate_reports(
    results_path: str,
    output_dir: str,
    timeout: int = 60,
) -> str:
    """Run generate_reports.py as a subprocess.

    Returns the output directory path containing the markdown reports.
    """
    cmd = [
        settings.python_exe,
        str(BASE_DIR / "generate_reports.py"),
        "--input", results_path,
        "--output", output_dir,
    ]

    result = subprocess.run(
        cmd,
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"generate_reports.py failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout[-500:]}\n"
            f"stderr: {result.stderr[-500:]}"
        )

    return output_dir


def read_reports(reports_dir: str) -> dict[str, str]:
    """Read all markdown reports from a directory into a dict keyed by report type."""
    reports = {}
    reports_path = Path(reports_dir)
    if not reports_path.exists():
        return reports

    for f in sorted(reports_path.glob("*.md")):
        if f.name == "README.md":
            continue
        body = f.read_text(encoding="utf-8")
        # Extract report type from filename (e.g. "00_博主画像卡片.md" -> "00")
        report_type = f.stem  # "00_博主画像卡片"
        reports[report_type] = body

    return reports
