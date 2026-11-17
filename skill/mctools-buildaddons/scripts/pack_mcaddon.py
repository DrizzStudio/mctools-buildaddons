#!/usr/bin/env python3
"""Zip a Bedrock add-on project into a .mcaddon (or a single pack into .mcpack).

A project folder contains one sub-folder per pack (e.g. my_addon_BP, my_addon_RP),
each with its own manifest.json. Each pack folder lands at the root of the zip.

Usage:
  python pack_mcaddon.py path/to/project                 -> path/to/project.mcaddon
  python pack_mcaddon.py path/to/project -o out.mcaddon
  python pack_mcaddon.py path/to/my_addon_BP --mcpack    -> single pack as .mcpack
"""

from __future__ import annotations
import argparse
import sys
import zipfile
from pathlib import Path

SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".vscode", ".idea"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}
SKIP_SUFFIXES = {".ts", ".map", ".psd", ".blend", ".ase", ".aseprite"}


def iter_files(pack_dir: Path):
    for path in sorted(pack_dir.rglob("*")):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(pack_dir).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        if path.name in SKIP_FILES or path.suffix.lower() in SKIP_SUFFIXES:
            continue
        yield path


def pack_project(project_dir: Path, out_path: Path, single_pack: bool = False) -> Path:
    project_dir = project_dir.resolve()
    if single_pack:
        pack_dirs = [project_dir]
    else:
        pack_dirs = sorted(p for p in project_dir.iterdir() if p.is_dir() and (p / "manifest.json").is_file())

    if not pack_dirs or not all((p / "manifest.json").is_file() for p in pack_dirs):
        raise SystemExit(f"No manifest.json found in {project_dir} (or its direct sub-folders).")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for pack_dir in pack_dirs:
            for file in iter_files(pack_dir):
                if single_pack:
                    arcname = file.relative_to(pack_dir).as_posix()  # .mcpack: manifest at zip root
                else:
                    arcname = (Path(pack_dir.name) / file.relative_to(pack_dir)).as_posix()
                zf.write(file, arcname)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=Path, help="project folder (or a single pack folder with --mcpack)")
    parser.add_argument("-o", "--out", type=Path, help="output file path")
    parser.add_argument("--mcpack", action="store_true", help="package ONE pack folder as .mcpack")
    args = parser.parse_args()

    if not args.path.is_dir():
        sys.exit(f"Not a folder: {args.path}")

    suffix = ".mcpack" if args.mcpack else ".mcaddon"
    out = args.out or args.path.resolve().with_suffix(suffix)
    result = pack_project(args.path, out, single_pack=args.mcpack)
    print(f"Created {result}")


if __name__ == "__main__":
    main()
