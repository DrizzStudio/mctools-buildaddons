---
name: mctools-buildaddons
description: Build original Minecraft Bedrock add-ons (behavior/resource packs, .mcaddon/.mcpack, Script API with @minecraft/server and @minecraft/server-ui) that load without errors on the first try. Handles manifest.json, self-generated UUIDs, pinned module versions, custom slash commands that really register, form UIs, custom items/blocks, original license-free textures generated and registered automatically, no empty filler files, and corrects the user's idea when it is wrong or impossible. Use whenever the user asks to make, fix, extend, debug or package a Minecraft add-on, mod, command, menu/GUI, item, block or texture for Bedrock (Windows, mobile, console, Realms, dedicated server), including Indonesian/Malay requests like "buatkan addon minecraft", "bikin command minecraft", "addon error", "buat texture", even if they never say Bedrock, manifest or script API.
---

# MCTools Build Addons

Goal: deliver a Bedrock add-on that **loads and works on the first import**, is **original**, and contains **only files that do something**. Most failed add-ons break for boring reasons: a hand-typed or duplicated UUID, a script module version the game does not have, a command registered in the wrong place, an API name that changed between versions, a texture that was never registered, or an idea the engine cannot do. This skill removes those failure points with a fixed workflow, helper scripts, and reference notes.

Reply to the user in the language they write in (Indonesian/Malay stays Indonesian/Malay). Keep code, file names and identifiers in English.

## Three standing rules

1. **Be original.** Do not clone other add-ons. Take the user's concept and build your own implementation, names, textures and mechanics. Details in `references/originality-and-textures.md`.
2. **No filler files.** Every file and folder you create must be used by the game or by the user. No empty files, no empty folders, no placeholder scripts, no dummy lang/JSON, no unused textures, no "TODO" stubs. If a feature is not requested, its files do not exist.
3. **Textures must be usable.** Generate original, license-free textures with `scripts/make_texture.py` / `scripts/add_content.py` (valid PNG, power-of-two size, registered, named). Never use or copy vanilla Minecraft textures, marketplace art, or images from the web.

## Workflow

### 1. Fix the idea first (before writing code)
Read `references/idea-correction.md`. For each feature the user wants, decide: **works as described / works with a different approach / not possible**. Then:
- Tell the user in 2–4 short lines what you changed and why (e.g. "a custom `/` command is done with the Custom Commands API, not a `.mcfunction` or a `!` chat hack").
- Build the closest working version. Never silently drop a feature and never promise something the engine cannot do.
- If the idea is "make X exactly like add-on Y", keep the concept but redesign names, visuals and code (see originality reference).
- Do not interrogate the user. Make reasonable assumptions, state them in one line, and build. Ask only when the answer changes the whole design.

### 2. Pin versions (do not guess)
Read `references/versions-and-manifest.md`. Module versions and `min_engine_version` change with every game release and a wrong value means the script silently does not run.
- If you can reach the network (web search, `npm view @minecraft/server dist-tags`), check the current **stable** versions and note the date.
- Otherwise use the scaffold defaults (conservative, known to load) and tell the user newer versions exist.
- Use stable versions only (`2.4.0`, not `2.5.0-beta`) unless the user explicitly needs a beta-only API; if so, warn them about the Beta APIs experiment toggle.

### 3. Scaffold with the script, never write manifests by hand
```bash
python scripts/scaffold_addon.py --name "My Addon" --namespace myaddon --out ./projects
# options: --no-ui  --no-script (data-only)  --with-rp  --pack  --server 2.x.y  --server-ui 2.x.y  --engine 1.26.xx
```
Creates `<slug>_BP` with fresh random UUIDs (all different), a valid manifest, an original generated pack icon and a working `scripts/main.js` that already registers a custom command. The resource pack is **not** created unless needed (commands and forms do not need one); `add_content.py` creates and links it automatically when you add the first item/block. Need extra UUIDs? `python scripts/new_uuid.py -n 3`. **Never type, copy from a tutorial, or "make up" a UUID**, and never regenerate UUIDs of an existing add-on when updating it (bump `version` instead, otherwise players get a second copy).

If scripts cannot run, create the same structure manually from the templates in `references/versions-and-manifest.md` with real UUIDv4 values, and still follow the no-filler rule.

Replace the demo `main.js` content with the features the user asked for; delete demo commands the user did not ask for.

### 4. Add items, blocks and textures
```bash
python scripts/add_content.py item  --project ./projects/my_addon --id ruby --name "Ruby" --style gem --color "#d81e5b"
python scripts/add_content.py block --project ./projects/my_addon --id ruby_block --name "Ruby Block" --style crystal --color "#d81e5b"
python scripts/make_texture.py --list     # styles: gem ingot orb potion sword wand | stone bricks planks ore metal crystal
```
Each call writes exactly: the definition JSON, the PNG, the texture registration, and the display name. Use `--seed` for variations, `--size 32|64|128` for higher resolution. For textures only (no definition) use `make_texture.py`. Read `references/originality-and-textures.md` for custom art, entity textures and the rules.

### 5. Implement the logic
Use the matching reference, and copy its patterns rather than improvising API calls:
- Custom commands → `references/custom-commands.md`
- Menus, forms, input dialogs → `references/server-ui.md`
- Anything throwing errors or silently not loading → `references/error-catalog.md`

Rules that prevent most runtime errors:
- Verify every API name, enum member and signature against the real type definitions of the pinned version. If npm works: `npm i --no-save @minecraft/server@<ver> @minecraft/server-ui@<ver>` and grep `node_modules/@minecraft/*/index.d.ts`. If not, check learn.microsoft.com/minecraft/creator/scriptapi. Memory of the API is the number-one source of errors because it is renamed often.
- Namespace everything: commands, enums, item/block/entity identifiers (`myaddon:thing`). Never use the `minecraft:` namespace for new things.
- Register commands only inside `system.beforeEvents.startup`, enums before commands. Do not touch `world` there.
- Changing the world from a callback that runs in a restricted context (command callbacks, `beforeEvents`) goes through `system.run(() => { ... })`.
- Do not use `fetch`, `require`, `process`, `window`, `document`, `localStorage`; prefer `system.runTimeout`, `system.runInterval`, `system.waitTicks` over `setTimeout`; persist data with dynamic properties.
- Wrap form code in `try/catch` or `.catch()`; the player can leave, die or have the chat open.
- Relative imports need the explicit `.js` extension and exact letter case (`./utils.js`).
- Prefer events over polling every tick.

### 6. Validate before delivering
```bash
python scripts/validate_addon.py ./projects/my_addon
```
Fix every `[ERROR]`; read every `[WARN]`. It checks UUID validity/uniqueness, module types, script entry path and letter case, undeclared `@minecraft/*` imports, banned globals, bare imports, command namespaces, enum registration order, **empty/placeholder files and empty folders, PNG validity and size, transparent or unregistered textures, missing item icons and display names**. When Node is available also run `node --check` on a `.mjs` copy of each script (syntax only). The validator is static; it never replaces an in-game test, so say honestly what was and was not verified.

### 7. Package and hand over
```bash
python scripts/pack_mcaddon.py ./projects/my_addon        # -> my_addon.mcaddon
```
Tell the user:
- How to install: open the `.mcaddon` (or copy `_BP`/`_RP` into `development_behavior_packs` / `development_resource_packs`), create a world, activate the packs. Experimental toggles are **not** needed for stable modules.
- The exact things to try, e.g. `/myaddon:hello friendly`, `/myaddon:menu`, `/give @s myaddon:ruby`.
- If something fails: Settings → Creator → enable **Content Log GUI**, reload the world, open the log with `Ctrl+H`, and send the first error line.
- Which versions the pack was pinned to, and that the textures are original CC0 art (free to use, no attribution needed).

## Output checklist (all must be true)
- [ ] Idea issues were explained in the user's language, briefly
- [ ] Concept follows the user's idea but is not a copy of another add-on (names, art, code are original)
- [ ] All UUIDs generated by script; header ≠ module UUIDs; BP depends on RP UUID if an RP exists
- [ ] Module versions are stable and match `min_engine_version`
- [ ] Every identifier is namespaced; commands registered in `startup`, enums first
- [ ] No empty/placeholder files or folders; no unused textures; demo code the user did not ask for is removed
- [ ] Every texture is a valid, registered PNG generated by the script (or user-supplied with a stated license)
- [ ] `validate_addon.py` reports 0 errors
- [ ] User got install steps + test commands + what to do if there is an error
