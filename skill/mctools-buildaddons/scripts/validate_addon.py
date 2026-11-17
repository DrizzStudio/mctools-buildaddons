#!/usr/bin/env python3
"""Static validator for Minecraft Bedrock add-on projects.

It cannot replace testing in the game, but it catches the mistakes that make a pack
silently fail to load: bad/duplicate UUIDs, wrong module types, missing script entry,
undeclared @minecraft/* dependencies, unsupported JS globals, and custom commands that
are not registered the way the game requires.

Usage:
  python validate_addon.py path/to/project        # folder holding one or more packs
  python validate_addon.py path/to/pack_BP

Exit code: 0 = no errors (warnings allowed), 1 = at least one error.
"""

from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mclib import read_png_info  # noqa: E402

SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".vscode", ".idea"}
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(-(beta|rc|alpha)[\w.\-]*)?$")
PLAIN_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
MODULE_TYPES = {"data", "resources", "script", "client_data", "interface", "world_template", "skin_pack", "plugin"}
KNOWN_MODULES = {
    "@minecraft/server",
    "@minecraft/server-ui",
    "@minecraft/server-net",
    "@minecraft/server-admin",
    "@minecraft/server-gametest",
    "@minecraft/debug-utilities",
    "@minecraft/diagnostics",
    "@minecraft/server-editor",
}

errors: list[str] = []
warnings: list[str] = []


def err(path: Path | str, msg: str) -> None:
    errors.append(f"[ERROR] {path}: {msg}")


def warn(path: Path | str, msg: str) -> None:
    warnings.append(f"[WARN]  {path}: {msg}")


# ----------------------------------------------------------------------------- JSON helpers


def strip_json_comments(text: str) -> str:
    """Remove // and /* */ comments that are outside of strings."""
    out, i, n, in_str, esc = [], 0, len(text), False, False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
        elif c == '"':
            in_str = True
            out.append(c)
            i += 1
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def load_json(path: Path):
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    try:
        data = json.loads(strip_json_comments(raw))
        warn(path, "contains comments; Minecraft tolerates this in some files but plain JSON is safer")
        return data
    except json.JSONDecodeError as exc:
        err(path, f"invalid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})")
        return None


# ----------------------------------------------------------------------------- UUID / version checks


def check_uuid(path: Path, where: str, value) -> bool:
    if not isinstance(value, str) or not UUID_RE.match(value):
        err(path, f"{where}: '{value}' is not a valid UUID. Generate one with scripts/new_uuid.py")
        return False
    compact = value.replace("-", "").lower()
    if (
        len(set(compact)) < 7
        or re.search(r"01234|12345|23456|34567|45678|56789|abcde|bcdef", compact)
        or re.fullmatch(r"(.{4})\1{7}", compact)
    ):
        err(path, f"{where}: '{value}' looks hand-typed or a placeholder. Generate a random UUID with scripts/new_uuid.py")
    return True  # format is valid, so it still takes part in the duplicate check


def check_version_field(path: Path, where: str, value) -> None:
    if isinstance(value, list):
        if len(value) != 3 or not all(isinstance(x, int) and x >= 0 for x in value):
            err(path, f"{where}: version array must be three non-negative integers, e.g. [1, 0, 0]")
    elif isinstance(value, str):
        if not PLAIN_VERSION_RE.match(value):
            err(path, f"{where}: version string must look like \"1.0.0\"")
    else:
        err(path, f"{where}: missing or invalid version")


def exact_case_exists(root: Path, rel: str) -> bool:
    """True only if rel exists under root with exactly matching letter case (Android/Linux are case-sensitive)."""
    current = root
    for part in Path(rel).parts:
        if not current.is_dir():
            return False
        if part not in {p.name for p in current.iterdir()}:
            return False
        current = current / part
    return current.exists()


# ----------------------------------------------------------------------------- manifest validation


def validate_manifest(path: Path, data: dict, header_uuids: dict, all_uuids: dict) -> dict:
    root = path.parent
    info = {"root": root, "deps_modules": {}, "has_script": False, "dep_uuids": [], "module_types": set()}

    if not isinstance(data, dict):
        err(path, "manifest root must be an object")
        return info

    fmt = data.get("format_version")
    if fmt not in (1, 2, 3):
        err(path, f"format_version must be 2 (or 3), got {fmt!r}")

    header = data.get("header")
    if not isinstance(header, dict):
        err(path, "missing 'header' object")
        header = {}
    if not header.get("name"):
        err(path, "header.name is missing")
    if check_uuid(path, "header.uuid", header.get("uuid")):
        all_uuids.setdefault(header["uuid"].lower(), []).append((path, "header.uuid"))
        header_uuids[header["uuid"].lower()] = path
    check_version_field(path, "header.version", header.get("version"))
    if "min_engine_version" not in header:
        err(path, "header.min_engine_version is required for behavior/resource packs")
    else:
        check_version_field(path, "header.min_engine_version", header["min_engine_version"])

    modules = data.get("modules")
    if not isinstance(modules, list) or not modules:
        err(path, "'modules' must be a non-empty array")
        modules = []

    for idx, module in enumerate(modules):
        where = f"modules[{idx}]"
        if not isinstance(module, dict):
            err(path, f"{where} must be an object")
            continue
        mtype = module.get("type")
        info["module_types"].add(mtype)
        if mtype == "javascript":
            err(path, f"{where}.type 'javascript' is obsolete and will not load. Use type 'script' with language 'javascript'")
        elif mtype not in MODULE_TYPES:
            err(path, f"{where}.type {mtype!r} is not a valid module type")
        if check_uuid(path, f"{where}.uuid", module.get("uuid")):
            all_uuids.setdefault(module["uuid"].lower(), []).append((path, f"{where}.uuid"))
        check_version_field(path, f"{where}.version", module.get("version"))

        if mtype == "script":
            info["has_script"] = True
            if module.get("language") != "javascript":
                err(path, f"{where}.language must be 'javascript'")
        if mtype in ("script", "javascript"):
            entry = module.get("entry")
            if not entry or not isinstance(entry, str):
                err(path, f"{where}.entry is required for script modules (e.g. 'scripts/main.js')")
            elif not exact_case_exists(root, entry):
                err(path, f"{where}.entry '{entry}' not found under {root} (check the path AND the letter case)")

    deps = data.get("dependencies", [])
    if not isinstance(deps, list):
        err(path, "'dependencies' must be an array")
        deps = []
    for idx, dep in enumerate(deps):
        where = f"dependencies[{idx}]"
        if not isinstance(dep, dict):
            err(path, f"{where} must be an object")
            continue
        if "module_name" in dep:
            name, version = dep["module_name"], dep.get("version")
            info["deps_modules"][name] = version
            if name not in KNOWN_MODULES:
                warn(path, f"{where}: unknown module '{name}' (typo?)")
            if not isinstance(version, str) or not SEMVER_RE.match(version):
                err(path, f"{where}.version for {name} must be a string like \"2.4.0\"")
            elif "-" in version:
                warn(path, f"{name}@{version} is a prerelease; it needs the 'Beta APIs' experiment and can break on game updates")
        elif "uuid" in dep:
            if check_uuid(path, f"{where}.uuid", dep.get("uuid")):
                info["dep_uuids"].append(dep["uuid"].lower())
            check_version_field(path, f"{where}.version", dep.get("version"))
        else:
            err(path, f"{where} needs either 'module_name' or 'uuid'")

    if info["has_script"] and "@minecraft/server" not in info["deps_modules"]:
        err(path, "has a script module but no '@minecraft/server' dependency")

    if not (root / "pack_icon.png").is_file():
        warn(path, "no pack_icon.png next to manifest.json (pack still loads, but shows no icon)")

    return info


# ----------------------------------------------------------------------------- JS validation

BANNED_GLOBALS = [
    (r"(?<![.\w$])fetch\s*\(", "fetch() does not exist in the Bedrock script engine (HTTP needs @minecraft/server-net on a dedicated server)"),
    (r"(?<![.\w$])require\s*\(", "require() is not available; use ES module 'import' (bundle npm packages first)"),
    (r"(?<![.\w$])process\.", "'process' (Node.js) does not exist in the Bedrock script engine"),
    (r"(?<![.\w$])(window|document|localStorage|sessionStorage)\b", "browser globals do not exist in the Bedrock script engine"),
]
WARN_GLOBALS = [
    (r"(?<![.\w$])(setTimeout|setInterval|clearTimeout|clearInterval)\s*\(", "prefer system.runTimeout / system.runInterval / system.waitTicks (tick based, always available)"),
]


def strip_js_comments(code: str) -> str:
    code = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), code, flags=re.S)
    return re.sub(r"(?m)(?<![:\"'`])//.*$", "", code)


def line_of(code: str, pos: int) -> int:
    return code.count("\n", 0, pos) + 1


def validate_js_file(path: Path, root: Path, deps_modules: dict) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    code = strip_js_comments(raw)
    rel = path.relative_to(root.parent)

    # imports
    for match in re.finditer(r"""(?:import|export)\s+(?:[^'"`;]*?\sfrom\s+)?["']([^"']+)["']""", code):
        spec = match.group(1)
        line = line_of(code, match.start())
        if spec.startswith("@minecraft/"):
            if spec not in deps_modules:
                err(f"{rel}:{line}", f"imports '{spec}' but manifest.json has no dependency on it (script will fail to load)")
        elif spec in ("mojang-minecraft", "mojang-minecraft-ui", "mojang-gametest", "mojang-net", "mojang-minecraft-server-admin"):
            err(f"{rel}:{line}", f"'{spec}' is the pre-1.19 module name; use the '@minecraft/...' equivalent")
        elif spec.startswith("."):
            target = (path.parent / spec)
            candidates = [target, Path(str(target) + ".js"), target / "index.js"]
            if not any(c.is_file() for c in candidates):
                err(f"{rel}:{line}", f"relative import '{spec}' does not resolve to a file")
            elif not spec.endswith((".js", ".mjs")):
                warn(f"{rel}:{line}", f"relative import '{spec}' has no .js extension; write the extension explicitly to be safe")
        else:
            err(f"{rel}:{line}", f"bare import '{spec}' cannot be resolved at runtime; bundle it (esbuild) or remove it")

    for pattern, message in BANNED_GLOBALS:
        for match in re.finditer(pattern, code):
            err(f"{rel}:{line_of(code, match.start())}", message)
    for pattern, message in WARN_GLOBALS:
        for match in re.finditer(pattern, code):
            warn(f"{rel}:{line_of(code, match.start())}", message)

    # custom commands
    if "registerCommand(" in code:
        if not re.search(r"beforeEvents\s*\.\s*startup", code):
            err(rel, "registerCommand() found but not inside system.beforeEvents.startup; commands registered anywhere else are rejected")
        first_cmd = code.find("registerCommand(")
        last_enum = code.rfind("registerEnum(")
        if last_enum != -1 and last_enum > first_cmd:
            warn(rel, "registerEnum() is called after registerCommand(); every enum must be registered BEFORE the commands that use it")
        # Command objects have `name` immediately followed by `description`; parameters do not.
        for nm in re.finditer(r"""\bname\s*:\s*(["'`])([^"'`]*)\1\s*,\s*description\s*:""", code):
            value = nm.group(2)
            line = line_of(code, nm.start())
            if "${" in value:
                continue  # templated name such as `${NS}:hello` cannot be checked statically
            if ":" not in value:
                err(f"{rel}:{line}", f"command name '{value}' has no namespace; custom commands must look like 'myaddon:command'")
            elif value.split(":", 1)[0] == "minecraft":
                err(f"{rel}:{line}", f"command name '{value}' uses the reserved 'minecraft' namespace")
    if "CustomCommandPermissionLevel" in code:
        warn(rel, "CustomCommandPermissionLevel is the older name; recent versions export CommandPermissionLevel (check index.d.ts of your version)")
    return code


# ----------------------------------------------------------------------------- content JSON checks


def validate_content_json(path: Path, root: Path) -> None:
    data = load_json(path)
    if not isinstance(data, dict):
        return
    rel = path.relative_to(root)
    for key in ("minecraft:entity", "minecraft:item", "minecraft:block", "minecraft:client_entity"):
        body = data.get(key)
        if isinstance(body, dict):
            if "format_version" not in data:
                warn(rel, "missing top-level format_version")
            ident = (body.get("description") or {}).get("identifier")
            if not ident:
                err(rel, f"{key}.description.identifier is missing")
            elif ":" not in ident:
                err(rel, f"identifier '{ident}' needs a namespace, e.g. 'myaddon:thing'")


# ----------------------------------------------------------------------------- useless files, textures, names


def check_useless_files(root: Path) -> None:
    """Flag files and folders that have no purpose (empty files, empty folders, comment-only scripts)."""
    rel_root = root.parent
    for path in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        rel = path.relative_to(rel_root)
        if path.is_dir():
            if not any(path.iterdir()):
                warn(rel, "empty folder; remove it (nothing in the pack needs it)")
        elif path.is_file():
            if path.stat().st_size == 0:
                err(rel, "empty file; delete it or put real content in it (empty files add nothing and some are invalid)")
            elif path.suffix in (".json", ".js", ".lang", ".mcfunction", ".txt", ".md"):
                text = path.read_text(encoding="utf-8", errors="replace")
                if not text.strip():
                    err(rel, "file contains only whitespace; delete it or put real content in it")
                elif path.suffix == ".js" and not strip_js_comments(text).strip():
                    warn(rel, "script contains only comments (a placeholder); remove it or implement it")


BP_CONTENT = {"scripts", "items", "blocks", "entities", "recipes", "loot_tables", "functions", "trading", "spawn_rules",
              "feature_rules", "features", "biomes", "structures", "animations", "animation_controllers", "dialogue",
              "texts", "item_catalog", "cameras", "volumes"}
RP_CONTENT = {"textures", "models", "entity", "sounds", "texts", "ui", "particles", "animations", "animation_controllers",
              "render_controllers", "attachables", "materials", "fogs", "items", "blocks", "biomes", "font", "shaders"}


def check_pack_has_content(root: Path, module_types: set) -> None:
    present = {p.name for p in root.iterdir() if p.is_dir()}
    present |= {p.name for p in root.iterdir() if p.is_file() and p.name in ("blocks.json", "sounds.json", "biomes_client.json")}
    if "resources" in module_types and not (present & RP_CONTENT or present & {"blocks.json", "sounds.json", "biomes_client.json"}):
        warn(root.name, "resource pack has no content (no textures, models, sounds, text...); it does nothing, so remove it or add content")
    if module_types & {"data", "script"} and not (present & BP_CONTENT):
        warn(root.name, "behavior pack has no content (no scripts, items, blocks, entities, recipes...); it does nothing yet")


def load_texture_registry(root: Path):
    """Return {shortname: relative_path_without_ext} for item_texture.json / terrain_texture.json in this pack."""
    registry = {"item": {}, "block": {}}
    for kind, name in (("item", "item_texture.json"), ("block", "terrain_texture.json")):
        path = root / "textures" / name
        if not path.is_file():
            continue
        data = load_json(path)
        if not isinstance(data, dict) or not isinstance(data.get("texture_data"), dict):
            err(path.relative_to(root.parent), "must be an object with a 'texture_data' object")
            continue
        for short, entry in data["texture_data"].items():
            textures = entry.get("textures") if isinstance(entry, dict) else None
            paths = []
            if isinstance(textures, str):
                paths = [textures]
            elif isinstance(textures, list):
                paths = [t if isinstance(t, str) else (t or {}).get("path") for t in textures]
            elif isinstance(textures, dict):
                paths = [(v if isinstance(v, str) else (v or {}).get("path")) for v in textures.get("variations", [])]
            registry[kind][short] = [p for p in paths if p]
    return registry


def check_textures(root: Path) -> dict:
    """Validate PNGs and the texture registration. Returns the shortname registry."""
    rel_root = root.parent
    registry = load_texture_registry(root)
    registered_paths = {p for kind in registry.values() for paths in kind.values() for p in paths}

    for kind in ("item", "block"):
        for short, paths in registry[kind].items():
            for rel in paths:
                if not any((root / f"{rel}{ext}").is_file() for ext in (".png", ".tga", ".jpg", ".jpeg")):
                    err(root.name + "/" + rel, f"registered as '{short}' but no image file exists (expected {rel}.png)")

    tex_dir = root / "textures"
    if not tex_dir.is_dir():
        return registry
    for png in sorted(tex_dir.rglob("*.png")):
        rel = png.relative_to(rel_root)
        info = read_png_info(png)
        if not info["ok"]:
            err(rel, f"invalid PNG: {info['problem']}")
            continue
        w, h = info["width"], info["height"]
        if w > 1024 or h > 1024:
            err(rel, f"{w}x{h} is too large for a Bedrock texture (keep it 1024 or smaller; 16-128 is typical)")
        elif w & (w - 1) or h & (h - 1):
            warn(rel, f"{w}x{h} is not a power of two; Bedrock expects 16, 32, 64, 128... (it may render blurry or fail to stitch)")
        if info["visible"] is False:
            err(rel, "image is completely transparent; it would be invisible in game")
        if re.search(r"[A-Z\s]", png.name):
            warn(rel, "file name has uppercase letters or spaces; use lowercase_with_underscores (case matters on Android/Linux)")
        rel_no_ext = png.relative_to(root).with_suffix("").as_posix()
        in_atlas_dir = rel_no_ext.startswith(("textures/items/", "textures/blocks/"))
        if in_atlas_dir and rel_no_ext not in registered_paths:
            warn(rel, "texture is not registered in item_texture.json / terrain_texture.json, so nothing can use it (register it or delete the file)")
    return registry


def check_display_names(bp_root: Path, rp_roots: list) -> None:
    """Warn when a custom item/block has no display name in any resource pack lang file."""
    keys = set()
    for rp in rp_roots:
        for lang in (rp / "texts").glob("*.lang") if (rp / "texts").is_dir() else []:
            for line in lang.read_text(encoding="utf-8", errors="replace").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    keys.add(line.split("=", 1)[0].strip())
    for folder, prefix, root_key in (("items", "item", "minecraft:item"), ("blocks", "tile", "minecraft:block")):
        for path in sorted((bp_root / folder).glob("*.json")) if (bp_root / folder).is_dir() else []:
            try:
                data = json.loads(strip_json_comments(path.read_text(encoding="utf-8-sig")))
            except json.JSONDecodeError:
                continue
            body = data.get(root_key) if isinstance(data, dict) else None
            if not isinstance(body, dict):
                continue
            ident = (body.get("description") or {}).get("identifier")
            comps = body.get("components") or {}
            if ident and ident.split(":")[0] != "minecraft" and f"{prefix}.{ident}.name" not in keys and "minecraft:display_name" not in comps:
                warn(path.relative_to(bp_root.parent), f"no display name; add '{prefix}.{ident}.name=Your Name' to texts/en_US.lang in the resource pack")


def check_texture_references(bp_root: Path, registries: list) -> None:
    """Item icons and block textures must point at a registered shortname."""
    items = {s for reg in registries for s in reg["item"]}
    blocks = {s for reg in registries for s in reg["block"]}
    for folder, root_key in (("items", "minecraft:item"), ("blocks", "minecraft:block")):
        for path in sorted((bp_root / folder).glob("*.json")) if (bp_root / folder).is_dir() else []:
            try:
                data = json.loads(strip_json_comments(path.read_text(encoding="utf-8-sig")))
            except json.JSONDecodeError:
                continue
            body = data.get(root_key) if isinstance(data, dict) else None
            if not isinstance(body, dict):
                continue
            ident = (body.get("description") or {}).get("identifier", "")
            custom = ident.split(":")[0] != "minecraft"
            comps = body.get("components") or {}
            rel = path.relative_to(bp_root.parent)
            if root_key == "minecraft:item":
                icon = comps.get("minecraft:icon")
                short = icon if isinstance(icon, str) else (icon or {}).get("textures", {}).get("default") if isinstance(icon, dict) else None
                if custom and not icon:
                    warn(rel, "custom item without minecraft:icon shows a missing-texture cube; add an icon (make_texture.py / add_content.py)")
                elif short and short not in items:
                    warn(rel, f"icon shortname '{short}' is not in any item_texture.json of this project (fine only if it is a vanilla shortname)")
            else:
                mats = comps.get("minecraft:material_instances")
                if custom and isinstance(mats, dict):
                    for inst in mats.values():
                        short = inst.get("texture") if isinstance(inst, dict) else inst
                        if isinstance(short, str) and short not in blocks:
                            warn(rel, f"block texture shortname '{short}' is not in any terrain_texture.json of this project (fine only if it is a vanilla shortname)")


# ----------------------------------------------------------------------------- main


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    base = args.path.resolve()
    if not base.is_dir():
        sys.exit(f"Not a folder: {base}")

    manifests = [p for p in base.rglob("manifest.json") if not any(part in SKIP_DIRS for part in p.parts)]
    if not manifests:
        sys.exit(f"No manifest.json found under {base}")

    header_uuids: dict = {}
    all_uuids: dict = {}
    infos = []

    for manifest in sorted(manifests):
        data = load_json(manifest)
        if data is None:
            continue
        info = validate_manifest(manifest, data, header_uuids, all_uuids)
        infos.append((manifest, info))

    for value, places in all_uuids.items():
        if len(places) > 1:
            where = "; ".join(f"{p.parent.name}:{w}" for p, w in places)
            err(places[0][0], f"UUID {value} is used more than once ({where}). Every header and module needs its own UUID")

    registries, rp_roots, bp_roots = [], [], []
    for manifest, info in infos:
        root = info["root"]
        check_useless_files(root)
        check_pack_has_content(root, info["module_types"])
        registries.append(check_textures(root))
        if info["has_script"] or (root / "items").is_dir() or (root / "blocks").is_dir() or (root / "entities").is_dir():
            bp_roots.append(root)
        if (root / "textures").is_dir() or (root / "texts").is_dir():
            rp_roots.append(root)
    for bp_root in bp_roots:
        check_texture_references(bp_root, registries)
        check_display_names(bp_root, rp_roots)

    for manifest, info in infos:
        for dep in info["dep_uuids"]:
            if dep not in header_uuids:
                warn(manifest, f"depends on pack UUID {dep} which is not in this project (fine only if that pack is installed separately)")

        root = info["root"]
        for js in sorted(root.rglob("*.js")):
            if any(part in SKIP_DIRS for part in js.relative_to(root).parts):
                continue
            validate_js_file(js, root, info["deps_modules"])
        for js_file in sorted(root.rglob("*.json")):
            if js_file.name == "manifest.json" or any(part in SKIP_DIRS for part in js_file.relative_to(root).parts):
                continue
            validate_content_json(js_file, root)

    for line in errors + warnings:
        print(line)
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s) in {len(infos)} pack(s).")
    if not errors:
        print("Static checks passed. Still test in the game and read the Content Log (Settings > Creator).")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
