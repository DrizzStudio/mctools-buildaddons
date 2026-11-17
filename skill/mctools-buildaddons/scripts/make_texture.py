#!/usr/bin/env python3
"""Create an original, license-free (CC0) texture and register it in the resource pack.

The art is generated procedurally (no vanilla Minecraft textures, nothing copied), so it is
safe to ship in any add-on. A tEXt chunk inside each PNG records the CC0 license.

Item (transparent 16x16 icon) styles : gem, ingot, orb, potion, sword, wand
Block (opaque, tileable) styles      : stone, bricks, planks, ore, metal, crystal

Usage:
  python make_texture.py --list
  python make_texture.py item  --rp proj/my_addon_RP --namespace myaddon --id ruby --style gem --color "#d81e5b"
  python make_texture.py block --rp proj/my_addon_RP --namespace myaddon --id ruby_ore --style ore --color "#d81e5b"
  python make_texture.py item  --out ./preview/ruby.png --style gem --color "#d81e5b"    # just write a PNG

With --rp the PNG goes to textures/items|blocks/<id>.png and the shortname "<namespace>_<id>" is
added to textures/item_texture.json or textures/terrain_texture.json (created if missing).
Use the printed shortname in "minecraft:icon" (items) or "minecraft:material_instances" (blocks).
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mclib  # noqa: E402
import texgen  # noqa: E402


def pack_name_from(rp_dir: Path) -> str:
    manifest = rp_dir / "manifest.json"
    if manifest.is_file():
        data = mclib.read_json_strict(manifest)
        name = (data.get("header") or {}).get("name")
        if name:
            return mclib.slugify(name)
    return mclib.slugify(rp_dir.name)


def create_texture(kind, style, tex_id, namespace, rp_dir: Path, color=None, size=16, seed=""):
    """Generate the PNG, register the shortname, return (png_path, shortname, relative_path)."""
    if not mclib.valid_identifier_part(tex_id):
        raise SystemExit(f"--id must be lowercase letters, digits or _ (starting with a letter), got {tex_id!r}")
    folder = "items" if kind == "item" else "blocks"
    rel = f"textures/{folder}/{tex_id}"
    shortname = f"{namespace}_{tex_id}"
    rows = texgen.generate(kind, style, color, size, seed or f"{namespace}:{tex_id}")
    png_path = rp_dir / f"{rel}.png"
    mclib.write_png(png_path, rows, texgen.metadata(kind, style, tex_id))
    mclib.register_texture(rp_dir, kind, shortname, rel, pack_name_from(rp_dir))
    return png_path, shortname, rel


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("kind", nargs="?", choices=["item", "block"])
    parser.add_argument("--list", action="store_true", help="list available styles")
    parser.add_argument("--style", help="texture style (see --list)")
    parser.add_argument("--color", help="base color as hex, e.g. #d81e5b (default depends on style)")
    parser.add_argument("--size", type=int, default=16, help="16, 32, 64 or 128 (default 16)")
    parser.add_argument("--seed", default="", help="change this to get a different variation")
    parser.add_argument("--rp", type=Path, help="resource pack folder (contains manifest.json)")
    parser.add_argument("--namespace", help="add-on namespace, used for the texture shortname")
    parser.add_argument("--id", help="texture/file id, e.g. ruby")
    parser.add_argument("--out", type=Path, help="write just a PNG to this path (no registration)")
    args = parser.parse_args()

    if args.list:
        print("item styles :", ", ".join(texgen.ITEM_STYLES))
        print("block styles:", ", ".join(texgen.BLOCK_STYLES))
        return
    if not args.kind or not args.style:
        parser.error("kind (item|block) and --style are required (use --list to see styles)")

    if args.out:
        rows = texgen.generate(args.kind, args.style, args.color, args.size, args.seed or args.out.stem)
        mclib.write_png(args.out, rows, texgen.metadata(args.kind, args.style, args.out.stem))
        print(f"Wrote {args.out}")
        return

    if not (args.rp and args.namespace and args.id):
        parser.error("--rp, --namespace and --id are required unless --out is used")
    if not (args.rp / "manifest.json").is_file():
        sys.exit(f"{args.rp} is not a resource pack folder (no manifest.json). Create one with scaffold_addon.py --with-rp")

    png, shortname, rel = create_texture(args.kind, args.style, args.id, args.namespace.lower(), args.rp, args.color, args.size, args.seed)
    print(f"Texture : {png}")
    print(f"Shortname: {shortname}  ->  {rel}")
    if args.kind == "item":
        print(f'Use in item JSON : "minecraft:icon": "{shortname}"')
    else:
        print(f'Use in block JSON: "minecraft:material_instances": {{ "*": {{ "texture": "{shortname}", "render_method": "opaque" }} }}')


if __name__ == "__main__":
    main()
