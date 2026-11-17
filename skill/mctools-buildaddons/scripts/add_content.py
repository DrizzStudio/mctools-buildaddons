#!/usr/bin/env python3
"""Add a complete custom item or block to an add-on project.

One command creates every file the content needs, and nothing else:
  - BP/items/<id>.json  or  BP/blocks/<id>.json      (definition)
  - RP/textures/items|blocks/<id>.png                 (original CC0 texture, see make_texture.py)
  - RP/textures/item_texture.json | terrain_texture.json  (shortname registration)
  - RP/texts/en_US.lang                               (display name)
The resource pack is created (and linked from the behavior pack) automatically if missing.

Usage:
  python add_content.py item  --project proj/my_addon --id ruby --name "Ruby" --style gem --color "#d81e5b"
  python add_content.py block --project proj/my_addon --id ruby_block --name "Ruby Block" --style crystal --color "#d81e5b"

Options: --namespace (auto-detected from scripts/main.js 'const NS' if omitted), --category, --stack,
         --hardness, --size, --seed, --force.
Try in game: /give @s <namespace>:<id>
"""

from __future__ import annotations
import argparse
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mclib  # noqa: E402
import texgen  # noqa: E402
from make_texture import create_texture  # noqa: E402

ITEM_FORMAT = "1.21.60"
BLOCK_FORMAT = "1.21.110"
MIN_ENGINE = {"item": [1, 21, 60], "block": [1, 21, 110]}
ITEM_CATEGORIES = ["construction", "equipment", "items", "nature"]
SKIP_DIRS = {"node_modules", ".git", "__pycache__"}


def as_list(version):
    if isinstance(version, list):
        return version
    return [int(p) for p in str(version).split(".")]


def find_packs(project: Path):
    bp = rp = None
    for manifest in sorted(project.rglob("manifest.json")):
        if any(part in SKIP_DIRS for part in manifest.parts):
            continue
        data = mclib.read_json_strict(manifest)
        types = {m.get("type") for m in data.get("modules", []) if isinstance(m, dict)}
        if types & {"data", "script"} and bp is None:
            bp = manifest.parent
        elif "resources" in types and rp is None:
            rp = manifest.parent
    return bp, rp


def detect_namespace(bp: Path):
    """Namespace from `const NS = "..."` in scripts, or from identifiers of existing items/blocks."""
    for js in sorted(bp.rglob("*.js")):
        match = re.search(r"""const\s+NS\s*=\s*["']([a-z][a-z0-9_]*)["']""", js.read_text(encoding="utf-8", errors="replace"))
        if match:
            return match.group(1)
    for folder in ("items", "blocks"):
        for path in sorted((bp / folder).glob("*.json")) if (bp / folder).is_dir() else []:
            match = re.search(r'"identifier"\s*:\s*"([a-z][a-z0-9_]*):', path.read_text(encoding="utf-8", errors="replace"))
            if match and match.group(1) != "minecraft":
                return match.group(1)
    return None


def ensure_rp(project: Path, bp: Path, rp: Path | None) -> Path:
    if rp:
        return rp
    bp_manifest_path = bp / "manifest.json"
    bp_manifest = mclib.read_json_strict(bp_manifest_path)
    header = bp_manifest["header"]
    base = bp.name[:-3] if bp.name.endswith("_BP") else bp.name
    rp = project / f"{base}_RP"
    if rp.exists():
        sys.exit(f"{rp} already exists but has no resources manifest; fix or remove it first.")
    version = header["version"]
    rp_header_uuid = str(uuid.uuid4())
    mclib.write_json(rp / "manifest.json", {
        "format_version": 2,
        "header": {
            "name": f"{header['name']} RP",
            "description": f"{header['name']} - resource pack",
            "uuid": rp_header_uuid,
            "version": version,
            "min_engine_version": header["min_engine_version"],
        },
        "modules": [{"type": "resources", "uuid": str(uuid.uuid4()), "version": version, "description": "Resources"}],
    })
    mclib.write_png(rp / "pack_icon.png", texgen.make_pack_icon(rp_header_uuid), texgen.metadata("icon", "pack", header["name"]))
    deps = bp_manifest.setdefault("dependencies", [])
    deps.insert(0, {"uuid": rp_header_uuid, "version": version})
    mclib.write_json(bp_manifest_path, bp_manifest)
    print(f"Created resource pack {rp.name} and linked it from {bp.name}/manifest.json")
    return rp


def ensure_engine(bp: Path, kind: str) -> None:
    path = bp / "manifest.json"
    data = mclib.read_json_strict(path)
    current = as_list(data["header"].get("min_engine_version", [1, 0, 0]))
    needed = MIN_ENGINE[kind]
    if current < needed:
        data["header"]["min_engine_version"] = needed
        mclib.write_json(path, data)
        print(f"Raised {bp.name} min_engine_version to {needed} (required by the {kind} format used).")
        rp_path = path.parent.parent
        for manifest in rp_path.glob("*_RP/manifest.json"):
            rp_data = mclib.read_json_strict(manifest)
            if as_list(rp_data["header"].get("min_engine_version", [1, 0, 0])) < needed:
                rp_data["header"]["min_engine_version"] = needed
                mclib.write_json(manifest, rp_data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("kind", choices=["item", "block"])
    parser.add_argument("--project", type=Path, required=True, help="project folder holding the BP (and RP)")
    parser.add_argument("--id", required=True, help="lowercase id without namespace, e.g. ruby")
    parser.add_argument("--name", required=True, help="display name shown in game, e.g. Ruby")
    parser.add_argument("--style", required=True, help="texture style (python make_texture.py --list)")
    parser.add_argument("--color", help="base color hex, e.g. #d81e5b")
    parser.add_argument("--namespace", help="override the detected namespace")
    parser.add_argument("--category", default=None, help="creative menu category (items: construction|equipment|items|nature)")
    parser.add_argument("--stack", type=int, default=64, help="item max stack size (1-64)")
    parser.add_argument("--hardness", type=float, default=2.0, help="block seconds_to_destroy")
    parser.add_argument("--size", type=int, default=16, help="texture size 16/32/64/128")
    parser.add_argument("--seed", default="", help="texture variation seed")
    parser.add_argument("--force", action="store_true", help="overwrite an existing definition")
    args = parser.parse_args()

    if not args.project.is_dir():
        sys.exit(f"Project folder not found: {args.project}")
    if not mclib.valid_identifier_part(args.id):
        sys.exit("--id must be lowercase letters, digits or _ and start with a letter.")
    if not 1 <= args.stack <= 64:
        sys.exit("--stack must be between 1 and 64.")

    bp, rp = find_packs(args.project)
    if not bp:
        sys.exit(f"No behavior pack found in {args.project}. Run scaffold_addon.py first.")
    namespace = (args.namespace or detect_namespace(bp) or "").lower()
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,31}", namespace) or namespace == "minecraft":
        sys.exit("Could not determine a valid namespace. Pass --namespace myaddon (not 'minecraft').")

    folder = bp / ("items" if args.kind == "item" else "blocks")
    definition = folder / f"{args.id}.json"
    if definition.exists() and not args.force:
        sys.exit(f"{definition} already exists. Use --force to overwrite.")

    ensure_engine(bp, args.kind)
    rp = ensure_rp(args.project, bp, rp)
    identifier = f"{namespace}:{args.id}"

    png, shortname, rel = create_texture(args.kind, args.style, args.id, namespace, rp, args.color, args.size, args.seed)

    if args.kind == "item":
        category = args.category or "items"
        if category not in ITEM_CATEGORIES:
            sys.exit(f"--category must be one of {ITEM_CATEGORIES}")
        body = {
            "format_version": ITEM_FORMAT,
            "minecraft:item": {
                "description": {"identifier": identifier, "menu_category": {"category": category}},
                "components": {"minecraft:icon": shortname, "minecraft:max_stack_size": args.stack},
            },
        }
        lang_key = f"item.{identifier}.name"
    else:
        category = args.category or "construction"
        if category not in ITEM_CATEGORIES:
            sys.exit(f"--category must be one of {ITEM_CATEGORIES}")
        body = {
            "format_version": BLOCK_FORMAT,
            "minecraft:block": {
                "description": {"identifier": identifier, "menu_category": {"category": category}},
                "components": {
                    "minecraft:geometry": "minecraft:geometry.full_block",
                    "minecraft:material_instances": {"*": {"texture": shortname, "render_method": "opaque"}},
                    "minecraft:destructible_by_mining": {"seconds_to_destroy": args.hardness},
                },
            },
        }
        lang_key = f"tile.{identifier}.name"

    mclib.write_json(definition, body)
    lang = mclib.add_lang(rp, lang_key, args.name)

    print(f"Created {args.kind} {identifier}")
    for path in (definition, png, rp / "textures" / ("item_texture.json" if args.kind == "item" else "terrain_texture.json"), lang):
        print(f"  {path}")
    print(f"In game: /give @s {identifier}")


if __name__ == "__main__":
    main()
