"""把发布目录打成可移植 ZIP。

Windows 自带的 Compress-Archive 在大目录上会因内存失败，且部分 .NET 版本写入
反斜杠路径，飞书等第三方解压工具可能识别异常。这里用 Python zipfile 逐文件写入，
统一使用正斜杠，并保持流式压缩。
"""

import argparse
import os
import sys
import zipfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a release zip with forward-slash entries.")
    parser.add_argument("--root", required=True, help="Directory to zip")
    parser.add_argument("--out", required=True, help="Destination zip path")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out = Path(args.out).resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 1
    if out.exists():
        out.unlink()
    out.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort()
            for name in sorted(filenames):
                path = Path(dirpath) / name
                archive.write(path, path.relative_to(root).as_posix())
                count += 1

    print(f"zipped {count} files into {out} ({out.stat().st_size / 1048576:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
