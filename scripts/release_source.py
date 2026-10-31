"""Exact source snapshot, dependency locks and verifiable release inventory."""
import argparse
import hashlib
import importlib.metadata
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

SOURCE_DIRS = ("backend", "browser-extension", "frontend", "spider_xhs", "static", "scripts", "tests", "docs", "assets", "telemetry_server")
SOURCE_FILES = ("README.md", "requirements.txt", "requirements.lock.txt", "desktop_entry.py", "analyze_all.py", "generate_reports.py", "package.json", "package-lock.json", ".gitignore", ".env.example", "cookies.example.json", "start_windows.bat", "stop_windows.bat", "install_windows.bat")
EXCLUDE = {"node_modules", "__pycache__", ".git", "dist", "author", "data", "logs", "reports", "archive", "legacy"}
SECRET_PATTERNS = (
    ("private_key", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("openai_key", re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("session_cookie", re.compile(rb"\bweb_session=(?!xxxxx\b|yyyyy\b|test\b)[A-Za-z0-9%._~-]{20,}")),
    ("llm_api_key", re.compile(rb"""(?i)["']llm_api_key["']\s*:\s*["'](?!test-only["'])[^"']{12,}["']""")),
)
TEXT_SUFFIXES = {".txt", ".md", ".json", ".js", ".ts", ".vue", ".py", ".ps1", ".bat", ".html", ".css", ".toml", ".yaml", ".yml", ".ini", ".cfg"}


def sources(root):
    paths = [root / p for p in SOURCE_FILES if (root / p).is_file()]
    for name in SOURCE_DIRS:
        for path in (root / name).rglob("*"):
            rel = path.relative_to(root)
            if path.is_file() and not any(p in EXCLUDE for p in rel.parts) and path.suffix not in (".pyc", ".log", ".db") and path.name not in (".env", "cookies.json", "llm_config.json"):
                paths.append(path)
    return sorted(set(paths))


def git_info(root):
    result = {"commit": "unavailable", "dirty": True}
    try:
        args=["git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root)]
        result["commit"]=subprocess.check_output(args+["rev-parse","HEAD"],stderr=subprocess.DEVNULL,text=True).strip()
        result["dirty"]=bool(subprocess.check_output(args+["status","--porcelain"],stderr=subprocess.DEVNULL,text=True).strip())
    except Exception:
        pass
    return result


def snapshot(root, out, version):
    out.mkdir(parents=True, exist_ok=True)
    files=sources(root)
    entries={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    manifest={"version":version,"source":git_info(root),"python":sys.version,"files":entries}
    try:
        manifest["node"] = subprocess.check_output(["node", "--version"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        manifest["node"] = "unavailable"
    manifest["source_sha256"]=hashlib.sha256(json.dumps(entries,sort_keys=True).encode()).hexdigest()
    (out/"SOURCE_MANIFEST.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    with zipfile.ZipFile(out/f"source-{version}.zip","w",zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p,p.relative_to(root).as_posix())
        z.write(out/"SOURCE_MANIFEST.json","SOURCE_MANIFEST.json")
    return manifest


def scan(package):
    forbidden=[]
    secrets=[]
    text_files=[]
    for p in package.rglob("*"):
        if not p.is_file():
            continue
        parts=p.relative_to(package).parts
        if p.name in ("cookies.json",".env","app.db","database.db","llm_config.json") or p.suffix in (".db",".log") or parts[0] in ("data","logs","reports"):
            forbidden.append(str(p.relative_to(package)))
        elif p.suffix.lower() in TEXT_SUFFIXES and p.stat().st_size <= 8 * 1024 * 1024:
            text_files.append(p)
    if forbidden:
        raise RuntimeError("Release contains runtime data: " + ", ".join(forbidden))
    for p in text_files:
        content=p.read_bytes()
        for kind, pattern in SECRET_PATTERNS:
            if pattern.search(content):
                secrets.append(f"{kind}:{p.relative_to(package).as_posix()}")
    if secrets:
        raise RuntimeError("Release contains secret-like runtime values: " + ", ".join(secrets))
    rows=[]
    for p in sorted(package.rglob("*")):
        if p.is_file() and p.name != "checksums.sha256":
            rows.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(package).as_posix()}")
    (package/"checksums.sha256").write_text("\n".join(rows),encoding="utf-8")
    return len(rows)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['snapshot','scan','lock'])
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out',type=Path)
    parser.add_argument('--version',default='0.3.0-beta.4')
    args=parser.parse_args()
    if args.mode=='snapshot':
        m=snapshot(args.root,args.out,args.version)
        print(json.dumps({"source_sha256":m['source_sha256'],"files":len(m['files'])}))
    elif args.mode=='scan':
        print(f"Release clean: {scan(args.out)} files")
    else:
        packages=sorted({f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions()})
        (args.root/'requirements.lock.txt').write_text('\n'.join(packages)+'\n',encoding='utf-8')
        print(f"Locked {len(packages)} installed packages")
