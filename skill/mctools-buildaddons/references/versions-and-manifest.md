# Versions, manifest.json, UUIDs, folder layout

Contents: 1. Version rules · 2. Snapshot (Nov 2026) · 3. Manifest templates · 4. UUID rules · 5. Folder layout · 6. Install paths

## 1. Version rules (why scripts silently fail)

- **Game versioning changed in 2026.** The game is now announced by year ("26.40") but files still use the internal `1.26.x` form. `min_engine_version` is written `[1, 26, 10]` (array) or `"1.26.10"` (string, with `format_version` 3). Never write the marketing number alone.
- Three independent version axes — never mix them:
  | Axis | Example | Lives in |
  |---|---|---|
  | `min_engine_version` | `[1, 26, 10]` | manifest header |
  | Script module version | `"2.4.0"` | manifest `dependencies` |
  | Content `format_version` | `"1.21.100"` (blocks), `2` (manifest) | each content file; unrelated to the game version |
- The game keeps supporting **older stable module versions**, so pinning an older stable module is safe on newer games. The reverse is not: a module version newer than the player's game fails to load (script does not run, only the Content Log says why). Therefore: choose module versions first, then set `min_engine_version` ≥ the game that introduced that module version. When unsure, lower the module version.
- Prerelease tags (`2.5.0-beta`, `-rc`, `-alpha`) need the "Beta APIs" experiment, break on game updates, and some versions embed the game build in the tag. Avoid them unless the user needs a beta-only feature.
- `@minecraft/server-ui` has a peer dependency on `@minecraft/server`. Pair a newer server-ui only with a `@minecraft/server` at least as new as its peer requirement (see the changelog on learn.microsoft.com). `server-ui` 2.0.0 + `server` ≥ 2.0.0 is the safe pair.

## 2. Snapshot — checked November 2026 (re-check if you can)

Treat these as hints, not truth; the scaffold defaults are the first row.

| Item | Value | Note |
|---|---|---|
| Scaffold default | `server 2.4.0`, `server-ui 2.0.0`, `min_engine [1,26,10]` | Same combination as an example published by the Bedrock Wiki |
| Newer stable seen | `server` 2.9.0 – 2.11.0 for games 1.26.40 – 1.26.50 | Use when a newer API is needed |
| `server-ui` | 2.0.0 stable; 2.1.0 adds `CustomForm`, `MessageBox`, observables; 2.2.0 adds `CustomForm.image` and `MessageBox` button options | Only bump when you use those |
| Custom commands | Stable in `@minecraft/server` 2.x (introduced as 2.0.0-beta in 1.21.80) | No beta needed anymore |
| Removed | `"type": "javascript"` modules, `mojang-minecraft*` package names | Do not use |
| Content formats (verified in Bedrock docs) | Items `format_version "1.21.60"` with `"minecraft:icon": "shortname"`; blocks `"1.21.110"` with `minecraft:geometry` + `minecraft:material_instances` | The scripts use these; blocks need `min_engine_version` ≥ 1.21.110 (the scripts raise it automatically) |

To check the latest quickly: `npm view @minecraft/server dist-tags` and `npm view @minecraft/server-ui dist-tags` (the `latest` tag is the newest stable), or the changelog pages on learn.microsoft.com/minecraft/creator/scriptapi.

## 3. Manifest templates

Behavior pack (scripts + data). Replace the UUID placeholders with fresh values from `scripts/new_uuid.py`; there must be five different values for BP+RP.

```json
{
  "format_version": 2,
  "header": {
    "name": "My Addon",
    "description": "What it does",
    "uuid": "<BP-HEADER-UUID>",
    "version": [1, 0, 0],
    "min_engine_version": [1, 26, 10]
  },
  "modules": [
    { "type": "data", "uuid": "<BP-DATA-UUID>", "version": [1, 0, 0] },
    {
      "type": "script",
      "language": "javascript",
      "uuid": "<BP-SCRIPT-UUID>",
      "version": [1, 0, 0],
      "entry": "scripts/main.js"
    }
  ],
  "dependencies": [
    { "uuid": "<RP-HEADER-UUID>", "version": [1, 0, 0] },
    { "module_name": "@minecraft/server", "version": "2.4.0" },
    { "module_name": "@minecraft/server-ui", "version": "2.0.0" }
  ]
}
```

Resource pack:

```json
{
  "format_version": 2,
  "header": {
    "name": "My Addon RP",
    "description": "Resources",
    "uuid": "<RP-HEADER-UUID>",
    "version": [1, 0, 0],
    "min_engine_version": [1, 26, 10]
  },
  "modules": [{ "type": "resources", "uuid": "<RP-RESOURCES-UUID>", "version": [1, 0, 0] }]
}
```

Notes:
- Only the BP depends on the RP (the game then enables the RP automatically). Do **not** make them depend on each other.
- The dependency `uuid` is the RP's **header** UUID, and `version` must equal the RP header version.
- Drop `@minecraft/server-ui` from `dependencies` if no script imports it; every imported `@minecraft/*` module must be listed (and every listed one should be used).
- Script-only add-on with no custom content still keeps the `data` module; the RP can be omitted entirely.
- A `.mcpack` is one pack zipped with `manifest.json` at the zip root; a `.mcaddon` is a zip containing several pack folders.

## 4. UUID rules

1. Generate with `python scripts/new_uuid.py` (random v4). Do not type, edit, copy from docs or increment digits.
2. Header UUID ≠ every module UUID ≠ other pack's UUIDs. A repeated UUID makes the second pack fail to load with no visible message.
3. Keep UUIDs stable across updates. Increase `header.version` (and module versions) to update an installed add-on; new UUIDs create a second, conflicting add-on.
4. Do not reuse UUIDs from tutorials/templates: thousands of add-ons share them and collide in the same world.

## 5. Folder layout

Only create the folders and files a feature needs. An RP exists only when something uses it (textures, sounds, models, names); no empty folders or placeholder files.

```
my_addon/
├── my_addon_BP/
│   ├── manifest.json
│   ├── pack_icon.png            (256x256 recommended)
│   ├── scripts/main.js          (entry; other files imported with explicit .js)
│   ├── entities/ items/ blocks/ recipes/ loot_tables/ functions/ texts/
└── my_addon_RP/
    ├── manifest.json
    ├── pack_icon.png
    ├── textures/ models/ entity/ texts/ (en_US.lang, languages.json)
    └── textures/item_texture.json, textures/terrain_texture.json, blocks.json (as needed)
```

TypeScript or npm libraries: build/bundle to a single `scripts/main.js` (e.g. esbuild, `--bundle --format=esm --external:@minecraft/*`). The game only reads the built `.js`.

## 6. Install / test locations

- Windows: `%LocalAppData%\Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\games\com.mojang\development_behavior_packs` (and `development_resource_packs`). Folder changes are picked up when the world is reloaded.
- Android: `/storage/emulated/0/games/com.mojang/development_behavior_packs` (Android 11+ may need file-manager access to `Android/data` or just open the `.mcaddon`).
- iOS/console/others: import the `.mcaddon`/`.mcpack` file; consoles may restrict scripting add-ons.
- Dedicated server: copy packs into `behavior_packs`/`resource_packs` and list them in the world's `world_behavior_packs.json` (pack_id = header UUID, version = header version array).
