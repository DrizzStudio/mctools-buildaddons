# Error catalog: symptom → cause → fix

Contents: 1. Read the Content Log · 2. Pack does not appear / not active · 3. Script does not run · 4. Runtime errors · 5. Commands · 6. UI · 7. Content (items/blocks/entities) · 8. Before replying "it should work"

## 1. Read the Content Log first

Settings → Creator → turn on **Enable Content Log GUI** (and **Enable Content Log File**, optional). Reload the world, then open the log with `Ctrl+H` (or the on-screen log button). Errors show the file and line. Ask the user for the first error line; later errors are usually consequences. Use `console.warn("text")` in scripts to see output there; `console.log` may be hidden depending on the log level.

## 2. Pack does not appear or cannot be activated

| Cause | Fix |
|---|---|
| `manifest.json` is not valid JSON (trailing comma, comment, wrong quotes) | Run `validate_addon.py`; fix syntax |
| Duplicate or hand-typed UUIDs; header UUID equals a module UUID | Generate with `scripts/new_uuid.py`; all different |
| Missing `min_engine_version` | Add `[1, 26, 10]` (or the version you pinned) |
| `min_engine_version` is higher than the player's game | Lower it, only as far as the module versions allow |
| Manifest is not at the pack's root (extra folder level in the zip) | `.mcaddon` should contain `my_BP/manifest.json`; `.mcpack` should have `manifest.json` at the root |
| BP depends on an RP UUID/version that does not match the RP header | Copy the exact RP header UUID and version |
| Pack imported as new copy instead of updating | UUIDs were changed; keep UUIDs, bump `version` |

## 3. Pack activates but the script does not run

| Symptom | Cause | Fix |
|---|---|---|
| Nothing happens, log says module/version not found or unsupported | Module version newer than the game, or a prerelease (`-beta`) without the Beta APIs experiment | Use a stable version the game supports; lower the version |
| Log: cannot resolve `@minecraft/server-ui` (or similar) | Import without manifest dependency | Add it to `dependencies`, or remove the import |
| Script silently absent | `"type": "javascript"` or missing `"type": "script"`, `"language": "javascript"`, `"entry"` | Use the scaffold's script module |
| "Cannot find module" for `./utils` | Relative import without extension, wrong path, wrong letter case (Android/Linux are case-sensitive) | `import { x } from "./utils.js"`; match the exact file name |
| Entire script fails at load | A syntax error or a top-level call to an API that is unavailable in early execution | `node --check` a `.mjs` copy; move world access out of top level |
| Imported npm package | Bare imports cannot be resolved | Bundle with esbuild, or remove |

## 4. Runtime errors

| Message / symptom | Cause | Fix |
|---|---|---|
| `... can't be read in early-execution mode` / world not available | Touching `world`, entities, or dimensions in top-level code or in the startup event | Do world work after the world has loaded (e.g. `world.afterEvents.worldLoad` if your version has it) or inside events |
| `Native function [...] does not have required privileges` | Changing the world inside a read-only context (`beforeEvents`, command callbacks) | `system.run(() => { ...change... })` |
| `TypeError: x is not a function` / `undefined` | API renamed or moved between versions (for example method became property, enum member renamed) | Read `index.d.ts` of the pinned version; do not rely on memory or old tutorials |
| `ReferenceError: setTimeout/fetch/require is not defined` | Not available in the engine | `system.runTimeout`, dynamic properties, bundling |
| `Error: Failed to get property ... / entity is invalid` | The entity/player was removed or unloaded | Check validity (`isValid` — a property or a method depending on version; check d.ts) before use, and re-fetch after delays |
| Unhandled promise rejection from a form | Player left or the form failed | `try/catch` or `.catch` around `await form.show(...)` |
| Watchdog / "script hang" | Long synchronous loops or per-tick scans of many entities | Spread work over ticks with `system.runJob` (generator) or smaller intervals |
| Properties / dynamic property errors | Value too big or wrong type | Store small strings/numbers; serialize JSON; prefix keys with the namespace |

## 5. Commands

See the table in `custom-commands.md` §6. Quick list: register in `system.beforeEvents.startup`; namespace; enum before command; mandatory before optional; return a result; `system.run` for changes; permission level matches the caller; `@minecraft/server` 2.x.

## 6. UI

| Symptom | Cause | Fix |
|---|---|---|
| Form never appears after a command | Chat is open → `UserBusy` | Retry loop (`server-ui.md` §3) |
| `selection` undefined / crash on cancel | Reading `selection`/`formValues` after `canceled` | Check `response.canceled` first |
| Wrong values in `formValues` | Index shift caused by `label`/`header`/`divider` slots (undefined) | Account for those slots; keep control order and destructuring in sync |
| Old tutorial code throws on `.toggle(label, true)` / `.slider(..., step, default)` | server-ui 2.x uses an options object | `{ defaultValue, valueStep, defaultValueIndex }` |
| Icon is missing | Wrong texture path or file extension included | Path relative to the RP without `.png`, e.g. `textures/items/apple` |

## 7. Content (items/blocks/entities)

| Symptom | Cause | Fix |
|---|---|---|
| Item/block/entity absent with no error shown | A component not supported for that `format_version`, or invalid JSON component | Check the Content Log; compare with the Bedrock Wiki/`bedrock-samples` example of the same `format_version` |
| Identifier error | No namespace, `minecraft:` used for a new thing, uppercase/spaces | `myaddon:thing_name`, lowercase with underscores |
| Texture shows as a purple/black cube | Shortname missing from `terrain_texture.json` / `item_texture.json`, path wrong, file missing, or the item/block does not use the shortname | `python scripts/validate_addon.py`; register the shortname (path without extension) and reference it in `minecraft:icon` / `material_instances` |
| Item shows a missing-texture cube although the PNG exists | The item has no `minecraft:icon`, or the BP is not linked to the RP | Add `"minecraft:icon": "shortname"`; BP `dependencies` must contain the RP header UUID |
| New texture does not update | Old pack cached in the world | Bump pack `version`, reapply the pack to the world, or re-import |
| Name shows as `item.myaddon:thing.name` / `tile.myaddon:thing.name` | Missing lang entry | In `RP/texts/en_US.lang` add `item.myaddon:thing.name=My Thing` (items) or `tile.myaddon:thing.name=My Thing` (blocks), and keep `RP/texts/languages.json` = `["en_US"]` |
| `format_version` copied from a tutorial of another era | Components differ between versions | Use the version the current docs/wiki sample uses for that file type |

## 8. Before replying "it should work"

Run `python scripts/validate_addon.py <project>`, `node --check` on a `.mjs` copy of each script, confirm UUIDs are unique, confirm the versions are pinned and stable, and tell the user plainly what you could not verify without running the game.
