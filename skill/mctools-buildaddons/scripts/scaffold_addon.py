#!/usr/bin/env python3
"""Scaffold a Minecraft Bedrock add-on that loads on the first try.

Creates <out>/<slug>/<slug>_BP (and optionally <slug>_RP) with ONLY files that have a purpose:
  - fresh random UUIDs (header + every module are all different)
  - a valid manifest.json (format_version 2, pinned stable module dependencies)
  - scripts/main.js with a working custom command (and optional server-ui menu), unless --no-script
  - an original generated pack_icon.png (no copied art)
  - with --with-rp: a resource pack linked from the BP (add textures with make_texture.py / add_content.py)

No empty placeholder files or folders are created. The resource pack is NOT created by default because
commands and forms do not need one; add_content.py creates it automatically the first time you add an item or block.

Usage:
  python scaffold_addon.py --name "My Addon" --namespace myaddon --out ./projects
  python scaffold_addon.py --name "My Addon" --namespace myaddon --no-ui --pack
  python scaffold_addon.py --name "My Items" --namespace myitems --no-script --out ./projects   # data-only add-on

Versions default to a conservative, widely supported stable set. Override them when you have
checked the latest stable versions (see references/versions-and-manifest.md).
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
from pack_mcaddon import pack_project  # noqa: E402

DEFAULT_ENGINE = "1.26.10"
DEFAULT_SERVER = "2.4.0"
DEFAULT_SERVER_UI = "2.0.0"
GENERATOR_VERSION = "1.0.0"

# --------------------------------------------------------------------------- JS templates

JS_IMPORTS_BASE = """import {
  system,
  Player,
  CommandPermissionLevel,
  CustomCommandParamType,
  CustomCommandStatus,
} from "@minecraft/server";
"""

JS_IMPORTS_UI = """import { ActionFormData, ModalFormData, FormCancelationReason } from "@minecraft/server-ui";
"""

JS_COMMANDS_HEAD = """
// Namespace for every identifier in this add-on (commands, enums, items, entities...).
const NS = "__NS__";

// Custom commands can ONLY be registered inside the startup event.
// Do not touch `world` here: the world is not loaded yet (early-execution mode).
system.beforeEvents.startup.subscribe((init) => {
  const registry = init.customCommandRegistry;

  // 1) Enums must be registered BEFORE the commands that use them.
  registry.registerEnum(`${NS}:greeting_style`, ["friendly", "pirate"]);

  // 2) /__NS__:hello <friendly|pirate> [target]
  registry.registerCommand(
    {
      name: `${NS}:hello`,
      description: "Greet yourself or other players",
      permissionLevel: CommandPermissionLevel.Any,
      cheatsRequired: false,
      mandatoryParameters: [
        // For enum parameters, `name` must equal the registered enum name.
        { type: CustomCommandParamType.Enum, name: `${NS}:greeting_style` },
      ],
      optionalParameters: [{ type: CustomCommandParamType.PlayerSelector, name: "target" }],
    },
    // Arguments arrive in order: mandatory first, then optional.
    (origin, style, targets) => {
      const recipients =
        targets && targets.length > 0
          ? targets
          : origin.sourceEntity instanceof Player
            ? [origin.sourceEntity]
            : [];

      if (recipients.length === 0) {
        return { status: CustomCommandStatus.Failure, message: "No player to greet." };
      }

      const text = style === "pirate" ? "Ahoy, matey!" : "Hello there!";
      // Changing the world from a command callback must be deferred with system.run.
      system.run(() => {
        for (const player of recipients) player.sendMessage(text);
      });

      return { status: CustomCommandStatus.Success, message: `Greeted ${recipients.length} player(s).` };
    },
  );
"""

JS_COMMANDS_UI = """
  // 3) /__NS__:menu opens a form (needs @minecraft/server-ui).
  registry.registerCommand(
    {
      name: `${NS}:menu`,
      description: "Open the add-on menu",
      permissionLevel: CommandPermissionLevel.Any,
      cheatsRequired: false,
    },
    (origin) => {
      const player = origin.sourceEntity;
      if (!(player instanceof Player)) {
        return { status: CustomCommandStatus.Failure, message: "Only players can open the menu." };
      }
      system.run(() => {
        openMainMenu(player).catch((error) => console.warn(`[__NAME__] menu failed: ${error}`));
      });
      return { status: CustomCommandStatus.Success };
    },
  );
"""

JS_COMMANDS_TAIL = """});
"""

JS_UI_FUNCTIONS = """
/**
 * Show a form and retry while the player's chat window is still open.
 * Commands are typed in chat, so the first show() usually reports UserBusy.
 */
async function showWhenReady(player, form, maxTries = 30) {
  for (let attempt = 0; attempt < maxTries; attempt++) {
    const response = await form.show(player);
    if (response.cancelationReason !== FormCancelationReason.UserBusy) return response;
    await system.waitTicks(10);
  }
  return undefined;
}

async function openMainMenu(player) {
  const form = new ActionFormData()
    .title("__NAME__")
    .body("What would you like to do?")
    .button("Say hi")
    .button("Settings");

  const response = await showWhenReady(player, form);
  if (!response || response.canceled) return; // closed, or never became available

  if (response.selection === 0) player.sendMessage("Hi from __NAME__!");
  if (response.selection === 1) await openSettings(player);
}

async function openSettings(player) {
  const form = new ModalFormData()
    .title("Settings")
    .toggle("Enable sounds", { defaultValue: true })
    .slider("Volume", 0, 10, { valueStep: 1, defaultValue: 5 })
    .textField("Nickname", "Type a nickname", { defaultValue: "" })
    .dropdown("Theme", ["Light", "Dark"], { defaultValueIndex: 0 });

  const response = await showWhenReady(player, form);
  if (!response || response.canceled) return;

  const [sounds, volume, nickname, theme] = response.formValues;
  player.sendMessage(`Saved: sounds=${sounds}, volume=${volume}, nickname=${nickname || "-"}, theme=${theme}`);
}
"""

# --------------------------------------------------------------------------- helpers


def parse_version(text: str) -> list[int]:
    parts = text.strip().split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise SystemExit(f"Version must look like 1.26.10, got: {text!r}")
    return [int(p) for p in parts]


def check_module_version(label: str, text: str) -> str:
    if not re.fullmatch(r"\d+\.\d+\.\d+(-(beta|rc|alpha)[\w.\-]*)?", text):
        raise SystemExit(f"{label} must look like 2.4.0 (stable), got: {text!r}")
    return text


def build_main_js(namespace: str, name: str, with_ui: bool) -> str:
    parts = [JS_IMPORTS_BASE]
    if with_ui:
        parts.append(JS_IMPORTS_UI)
    parts.append(JS_COMMANDS_HEAD)
    if with_ui:
        parts.append(JS_COMMANDS_UI)
    parts.append(JS_COMMANDS_TAIL)
    if with_ui:
        parts.append(JS_UI_FUNCTIONS)
    js = "".join(parts)
    return js.replace("__NS__", namespace).replace("__NAME__", name.replace('"', "'"))


# --------------------------------------------------------------------------- main


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", required=True, help="display name of the add-on")
    parser.add_argument("--namespace", required=True, help="lowercase prefix for ids, e.g. myaddon (not 'minecraft')")
    parser.add_argument("--out", default=".", help="folder where the project folder is created")
    parser.add_argument("--description", default="", help="pack description")
    parser.add_argument("--author", default="Unknown", help="author name for manifest metadata")
    parser.add_argument("--version", default="1.0.0", help="pack version, e.g. 1.0.0")
    parser.add_argument("--engine", default=DEFAULT_ENGINE, help=f"min_engine_version (default {DEFAULT_ENGINE})")
    parser.add_argument("--server", default=DEFAULT_SERVER, help=f"@minecraft/server version (default {DEFAULT_SERVER})")
    parser.add_argument("--server-ui", default=DEFAULT_SERVER_UI, help=f"@minecraft/server-ui version (default {DEFAULT_SERVER_UI})")
    parser.add_argument("--no-ui", action="store_true", help="do not depend on @minecraft/server-ui")
    parser.add_argument("--no-script", action="store_true", help="data-only add-on: no script module, no main.js")
    parser.add_argument("--with-rp", action="store_true", help="also create a resource pack (add_content.py does this automatically)")
    parser.add_argument("--pack", action="store_true", help="also create a .mcaddon next to the project")
    parser.add_argument("--force", action="store_true", help="overwrite files in an existing project folder")
    args = parser.parse_args()

    namespace = args.namespace.strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,31}", namespace) or namespace == "minecraft":
        sys.exit("--namespace must be 2-32 chars of a-z, 0-9, _ (starting with a letter) and must not be 'minecraft'.")

    pack_version = parse_version(args.version)
    engine = parse_version(args.engine)
    server_version = check_module_version("--server", args.server)
    ui_version = check_module_version("--server-ui", args.server_ui)
    with_script = not args.no_script
    with_ui = with_script and not args.no_ui
    with_rp = args.with_rp

    slug = mclib.slugify(args.name)
    project = Path(args.out) / slug
    bp_dir = project / f"{slug}_BP"
    rp_dir = project / f"{slug}_RP"
    if project.exists() and not args.force:
        sys.exit(f"{project} already exists. Use --force to overwrite files in it.")

    description = args.description or f"{args.name} - behavior pack"

    # Every UUID is generated here, never typed by hand. All of them are different.
    ids = {k: str(uuid.uuid4()) for k in ("bp_header", "bp_data", "bp_script", "rp_header", "rp_resources")}

    # ---- behavior pack
    modules = [{"type": "data", "uuid": ids["bp_data"], "version": pack_version, "description": "Behavior data"}]
    dependencies = []
    if with_rp:
        dependencies.append({"uuid": ids["rp_header"], "version": pack_version})
    if with_script:
        modules.append({
            "type": "script",
            "language": "javascript",
            "uuid": ids["bp_script"],
            "version": pack_version,
            "entry": "scripts/main.js",
            "description": "Script entry point",
        })
        dependencies.append({"module_name": "@minecraft/server", "version": server_version})
        if with_ui:
            dependencies.append({"module_name": "@minecraft/server-ui", "version": ui_version})

    bp_manifest = {
        "format_version": 2,
        "header": {
            "name": args.name,
            "description": description,
            "uuid": ids["bp_header"],
            "version": pack_version,
            "min_engine_version": engine,
        },
        "modules": modules,
    }
    if dependencies:
        bp_manifest["dependencies"] = dependencies
    bp_manifest["metadata"] = {"authors": [args.author], "generated_with": {"mctools_buildaddons": [GENERATOR_VERSION]}}
    mclib.write_json(bp_dir / "manifest.json", bp_manifest)

    if with_script:
        scripts_dir = bp_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "main.js").write_text(build_main_js(namespace, args.name, with_ui), encoding="utf-8")
    mclib.write_png(bp_dir / "pack_icon.png", texgen.make_pack_icon(ids["bp_header"]), texgen.metadata("icon", "pack", args.name))

    # ---- resource pack (optional)
    if with_rp:
        mclib.write_json(rp_dir / "manifest.json", {
            "format_version": 2,
            "header": {
                "name": f"{args.name} RP",
                "description": f"{args.name} - resource pack",
                "uuid": ids["rp_header"],
                "version": pack_version,
                "min_engine_version": engine,
            },
            "modules": [{"type": "resources", "uuid": ids["rp_resources"], "version": pack_version, "description": "Resources"}],
            "metadata": {"authors": [args.author], "generated_with": {"mctools_buildaddons": [GENERATOR_VERSION]}},
        })
        mclib.write_png(rp_dir / "pack_icon.png", texgen.make_pack_icon(ids["rp_header"]), texgen.metadata("icon", "pack", args.name))

    print(f"Created project: {project}")
    print(f"  namespace        : {namespace}")
    print(f"  min_engine_version: {args.engine}")
    if with_script:
        print(f"  @minecraft/server : {server_version}")
        if with_ui:
            print(f"  @minecraft/server-ui: {ui_version}")
    print("  UUIDs (generated):")
    used = ["bp_header", "bp_data"] + (["bp_script"] if with_script else []) + (["rp_header", "rp_resources"] if with_rp else [])
    for key in used:
        print(f"    {key:<13} {ids[key]}")
    if with_script:
        print(f"  Commands in game  : /{namespace}:hello" + (f", /{namespace}:menu" if with_ui else ""))
    print(f"  Add content       : python add_content.py item --project {project} --namespace {namespace} --id ruby --name \"Ruby\" --style gem")

    if args.pack:
        out = pack_project(project, project.with_suffix(".mcaddon"))
        print(f"Packaged: {out}")


if __name__ == "__main__":
    main()
