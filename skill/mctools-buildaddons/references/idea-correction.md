# Correcting the user's idea

Many requests describe the wrong tool, a Java-edition concept, or something Bedrock cannot do. Your job is to translate the wish into something that works, tell the user briefly, and build it.

Contents: 1. How to respond · 2. Common corrections · 3. Feasibility quick check · 4. Template wording

## 1. How to respond

1. Classify each feature: **A** works as asked · **B** works, but by a different approach · **C** not possible in Bedrock add-ons.
2. For B and C, say it in 1–3 lines in the user's language: what they asked → what actually works → what you are building. No lecture, no blame.
3. For C, always offer the nearest feasible alternative and build it unless the user declines.
4. Do not ask a list of questions. Assume sensible defaults (single add-on, one namespace, stable modules, Bedrock) and state the assumptions.
5. If you are not sure whether something is possible in the current version, check the docs (learn.microsoft.com/minecraft/creator, Bedrock Wiki) or the pinned type definitions instead of promising.

## 2. Common corrections

| User says / assumes | Reality | Do this instead |
|---|---|---|
| "Make a new command like `/shop`" | Needs the Custom Commands API in `@minecraft/server` 2.x; must be namespaced (`/myaddon:shop`) | `custom-commands.md`. Mention that the namespace prefix is required |
| "Add a command with `!shop` in chat" | Works only as a chat hack; no autocomplete or permissions | Real custom command; keep `!` only if the user insists |
| "Custom menu / shop GUI / popup" | Done with `@minecraft/server-ui` forms, not JSON UI or HTML | `server-ui.md` (ActionForm for menus, ModalForm for input) |
| "Chest-like GUI with item slots", "custom HUD", "custom inventory screen" | Not available through Script API | ActionForm with icons; or a real container block. JSON UI hacks break on updates |
| "Make a Forge/Fabric/Java mod", "use Java/Kotlin" | Bedrock add-ons are JSON + JavaScript (TypeScript compiles to JS) | Explain once; build the Bedrock add-on |
| "Edit the game files / replace vanilla assets in the app" | Add-ons never modify the game installation | Override via packs (same identifier/path in the RP/BP); packs apply per world |
| "Add a new dimension" / "new biome type with script" | Script cannot create dimensions; custom biomes are limited JSON features | Use a structure/void-world area with teleport, or custom features/biome tags within what is supported |
| "Use `setTimeout`, `fetch`, `require`, npm packages, a database, files" | None exist in the script engine; npm code must be bundled; HTTP only via `@minecraft/server-net` on dedicated servers | `system.runTimeout` / `runInterval` / `waitTicks`; save data with dynamic properties; bundle libraries with esbuild |
| "Save player data permanently" | There is no file I/O | `player.setDynamicProperty(key, value)` / `world.setDynamicProperty`; keep values small, store JSON strings, prefix keys with the namespace |
| "Run this every tick" | Possible but expensive | Use events (`world.afterEvents.*`); if polling is needed, `system.runInterval(fn, 20)` or longer |
| "Give item with NBT/enchants from a command" | Bedrock has no NBT editing | `ItemStack` components, enchantable component, lore, dynamic properties on items |
| "Detect who is op/admin" | No `isOp` flag as in Java plugins | Command permission levels on the command; or tags (`player.addTag("admin")`) managed by the owner |
| "Make the add-on work on any version forever" | Module versions are tied to game versions | Pin stable versions, document them, re-check on game updates |
| "Use the latest beta API" | Needs Beta APIs experiment and breaks on updates; achievements are disabled | Stable alternative first; beta only on explicit request with a warning |
| "Copy UUIDs from a tutorial" | Collides with other add-ons | Always generate with `scripts/new_uuid.py` |
| "Make it exactly like add-on X / the Marketplace pack" | Cloning another creator's add-on (code, art, names) is not something to reproduce, and it usually fails on version differences anyway | Keep the concept, build an original version with own names, textures and code (`originality-and-textures.md` §2) |
| "Use Minecraft's textures / download textures from the internet" | Vanilla and random web images are not free to redistribute | Generate original CC0 textures with `make_texture.py`, or use art the user owns/has a license for |
| "Make a texture for my custom mob/face/logo" | The generator covers items and blocks only; entity skins need a model-matched UV layout | Say so; offer a generated item/block texture, or guide the user to draw the skin in Blockbench |
| "Create all the folders/files first, I'll fill them later" | Empty files and folders do nothing and can break loading | Create files only when they have content (`originality-and-textures.md` §8) |
| "Put everything in one file, no folders" | Packs need the BP/RP folder structure and manifests | Use the scaffold; one manifest per pack |
| "Works on Realms / consoles / iOS the same" | Platform support for scripting varies | State the target platform; script features are safest on Windows/Android/iOS/dedicated server; verify console limits before promising |
| "Make a custom mob with complex smart AI only in script" | Entity behavior is mostly JSON components; script adds events/logic around it | Entity JSON for behavior + script for extras |
| "Make blocks/items with mcfunction only" | Custom items/blocks are JSON definitions; functions only run commands | Item/block JSON (correct `format_version`), namespaced identifiers; script for logic |

## 3. Feasibility quick check

Before promising a feature, ask yourself:
1. Is the data/behavior reachable from `@minecraft/server` (events, entities, blocks, items, dimensions, commands)? If not → C.
2. Does the feature need a screen layout beyond forms? → C, offer forms.
3. Does it need outside access (web, files, other servers)? → C, offer dynamic properties; or dedicated-server-only `server-net` if they run a server.
4. Does it need a stable API that is still beta? → B, warn.
5. Does it affect only visuals (models, textures, sounds, particles)? → resource pack work, no script.

## 4. Template wording (adapt to the user's language)

> Dua penyesuaian supaya addon-nya jalan tanpa error: (1) command `/shop` harus pakai namespace, jadi dipanggil `/myaddon:shop`; (2) menu toko saya buat dengan form `@minecraft/server-ui`, karena GUI peti kustom tidak bisa dibuat lewat Script API. Fitur lain tetap sesuai permintaanmu.

Keep it that short. Then deliver.
