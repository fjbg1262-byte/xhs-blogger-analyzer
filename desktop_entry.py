"""Windows desktop entry point for the packaged local analyzer."""

from __future__ import annotations

import os
import runpy
import socket
import sys
import threading
import time
import webbrowser

import uvicorn

from backend.runtime import configure_runtime_environment, find_resource


HOST = "127.0.0.1"
PORT = 8000


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.8)
        return sock.connect_ex((host, port)) == 0


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

        runtime = execjs.get()
        result = runtime.eval("1 + 1")
        if result != 2:
            raise RuntimeError(f"unexpected JavaScript result: {result!r}")
    except Exception as exc:
        print(f"SELF_CHECK_FAILED: execjs: {exc}", file=sys.stderr)
        return 1

    print(f"SELF_CHECK_OK: execjs={runtime.name}")
    return 0


def main() -> int:
    configure_runtime_environment()

    if len(sys.argv) == 2 and sys.argv[1] == "--xhs-self-check":
        return _run_self_check()

    if len(sys.argv) >= 3 and sys.argv[1] == "--xhs-run":
        return _run_script_mode(sys.argv[2], sys.argv[3:])

    if _port_open(HOST, PORT):
        print(f"Local service is already running: http://{HOST}:{PORT}")
        webbrowser.open(f"http://{HOST}:{PORT}")
        return 0

    print("XHS Blogger Analyzer")
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
