"""Windows desktop entry point for the packaged local analyzer."""

from __future__ import annotations

import os
import runpy
import socket
import sys
import threading
import time
import webbrowser
import json
import urllib.request
from io import BytesIO

import uvicorn

from backend.runtime import configure_runtime_environment, find_resource


HOST = "127.0.0.1"
PORT = 8000
EXPECTED_REPORT_RENDERER = "customer-eight-dimension-v2"


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.8)
        return sock.connect_ex((host, port)) == 0


def _health_payload() -> dict:
    try:
        with urllib.request.urlopen(f"http://{HOST}:{PORT}/api/health", timeout=1.5) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return {}


def _open_browser_when_ready() -> None:
    url = f"http://{HOST}:{PORT}"
    for _ in range(40):
        if _port_open(HOST, PORT):
            webbrowser.open(url)
            return
        time.sleep(0.5)
    webbrowser.open(url)


def _run_script_mode(script_name: str, argv: list[str]) -> int:
    script_map = {
        "analyze_all": find_resource("analyze_all.py"),
        "generate_reports": find_resource("generate_reports.py"),
    }
    script = script_map.get(script_name)
    if not script or not script.exists():
        print(f"Unknown or missing script mode: {script_name}", file=sys.stderr)
        return 2

    old_argv = sys.argv[:]
    old_cwd = os.getcwd()
    try:
        sys.argv = [str(script)] + argv
        os.chdir(str(find_resource(".")))
        runpy.run_path(str(script), run_name="__main__")
        return 0
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)


def _run_self_check() -> int:
    """Verify dependencies that are easy to miss in the frozen release."""
    try:
        import execjs
        import httpx
        import openpyxl
        from backend.app import app
        from backend.services.library_analysis import Analysis, DIMENSIONS
        from backend.services.note_library import COLUMNS, finalize, make_row, xlsx_bytes
        if len(COLUMNS) != 28:
            raise RuntimeError("unexpected organizer schema")
        if set(Analysis.schema().get("properties", {})) != {
            "priority_dimension", "dimensions", "drafts", "strategy"
        }:
            raise RuntimeError("unexpected AI report schema")
        if len(DIMENSIONS) != 8:
            raise RuntimeError("unexpected AI dimensions")
        route_paths = {getattr(route, "path", "") for route in app.routes}
        if "/api/library/{task_id}/analysis" not in route_paths:
            raise RuntimeError("AI analysis route missing")
        if not find_resource("frontend", "dist", "index.html").is_file():
            raise RuntimeError("frontend build missing")

        sample = make_row({"note_id": "self-check-note", "display_title": "自检", "type": "normal",
                           "interact_info": {"liked_count": "0"}},
                          "https://www.xiaohongshu.com/user/profile/selfcheck", 1)
        workbook = openpyxl.load_workbook(BytesIO(xlsx_bytes(finalize({"rows": [sample]}), [sample], True)))
        if workbook.active.max_row != 2:
            raise RuntimeError("XLSX export self-check failed")

        runtime = execjs.get()
        result = runtime.eval("1 + 1")
        if result != 2:
            raise RuntimeError(f"unexpected JavaScript result: {result!r}")
    except Exception as exc:
        print(f"SELF_CHECK_FAILED: execjs: {exc}", file=sys.stderr)
        return 1

    print(f"SELF_CHECK_OK: app=AI-delivery, xlsx=ok, execjs={runtime.name}")
    return 0


def main() -> int:
    configure_runtime_environment()

    if len(sys.argv) == 2 and sys.argv[1] == "--xhs-self-check":
        return _run_self_check()

    if len(sys.argv) >= 3 and sys.argv[1] == "--xhs-run":
        return _run_script_mode(sys.argv[2], sys.argv[3:])

    if len(sys.argv) == 3 and sys.argv[1] == "--xhs-serve":
        # Headless local diagnostics; never expose the server to the network.
        from backend.app import app
        uvicorn.run(app, host=HOST, port=int(sys.argv[2]), access_log=False)
        return 0

    if _port_open(HOST, PORT):
        health = _health_payload()
        if health.get("organizer_schema") == "1.0":
            print(f"Local service is already running: http://{HOST}:{PORT}")
            webbrowser.open(f"http://{HOST}:{PORT}")
            return 0
        print("An older XHS Analyzer service is still using port 8000.")
        print("Please run 关闭本地工具.bat, then start this version again.")
        print("Your existing tasks and reports will not be deleted.")
        try:
            input("Press Enter to close this window...")
        except EOFError:
            time.sleep(8)
        return 2

    print("XHS Homepage Organizer")
    print(f"Starting local service: http://{HOST}:{PORT}")
    print("Keep this window open while using the tool.")

    from backend.app import app

    threading.Thread(target=_open_browser_when_ready, daemon=True).start()
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
