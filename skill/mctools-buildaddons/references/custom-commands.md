# Custom commands that actually register

Contents: 1. Checklist · 2. Full template · 3. Parameter types · 4. Permissions · 5. Origins and results · 6. When a command does not show up · 7. Alternatives

Script custom commands are part of `@minecraft/server` 2.x (first shipped as 2.0.0-beta in 1.21.80, now stable). Verify exact enum member names in `node_modules/@minecraft/server/index.d.ts` of the pinned version before using them; a few were renamed during the beta (see the notes below).

## 1. Checklist (each item is a real cause of "command not found")

1. Register inside `system.beforeEvents.startup.subscribe((init) => { ... })`, using `init.customCommandRegistry`. Registering later (worldLoad, a tick, an event) is rejected. Do not use `world` inside this callback (early-execution mode).
2. Command name is **namespaced**: `myaddon:hello`. No namespace, or `minecraft:`, fails. In chat you type `/myaddon:hello`.
3. **`registerEnum` before `registerCommand`**, and the parameter `name` of an enum parameter must equal the registered enum name (also namespaced, e.g. `myaddon:mode`).
4. Parameter order: all `mandatoryParameters` first, then `optionalParameters`. The callback receives `(origin, ...args)` in exactly that order; missing optional args are `undefined`.
5. The callback must return `{ status: CustomCommandStatus.Success | Failure, message?: string }` (or `undefined` for success in some versions; return an object to be safe).
6. `description` is required; set `permissionLevel` and `cheatsRequired` explicitly.
7. The manifest depends on `@minecraft/server` **2.x** (not 1.x) with a stable version that the game supports.
8. Command names are unique across the add-on; registering the same name twice throws.
9. World changes inside the callback go through `system.run(() => ...)`.

## 2. Full template

```js
import {
  system,
  world,
  Player,
  CommandPermissionLevel,
  CustomCommandParamType,
  CustomCommandStatus,
} from "@minecraft/server";

const NS = "myaddon";

system.beforeEvents.startup.subscribe((init) => {
  const registry = init.customCommandRegistry;

  // enums first
  registry.registerEnum(`${NS}:mode`, ["easy", "normal", "hard"]);

  registry.registerCommand(
    {
      name: `${NS}:setmode`,
      description: "Set the game mode of this add-on",
      permissionLevel: CommandPermissionLevel.GameDirectors, // operators / command blocks
      cheatsRequired: true,
      mandatoryParameters: [{ type: CustomCommandParamType.Enum, name: `${NS}:mode` }],
      optionalParameters: [{ type: CustomCommandParamType.Integer, name: "amount" }],
    },
    (origin, mode, amount) => {
      const count = amount ?? 1;
      system.run(() => {
        // safe place to change the world / players
        world.sendMessage(`Mode ${mode} x${count}`);
      });
      return { status: CustomCommandStatus.Success, message: `Mode set to ${mode}` };
    },
  );
});
```

Failure example: `return { status: CustomCommandStatus.Failure, message: "Target not found" };`

## 3. Parameter types (`CustomCommandParamType`)

| Type | Callback receives |
|---|---|
| `Boolean` | `boolean` |
| `Integer` / `Float` | `number` |
| `String` | `string` |
| `Enum` | `string` (one of the registered values) |
| `PlayerSelector` | `Player[]` (can be empty) |
| `EntitySelector` | `Entity[]` (can be empty) |
| `Location` (older docs: `Position`) | `Vector3` |
| `BlockType` / `ItemType` | `BlockType` / `ItemType` |

Always handle empty selector arrays. If a member name does not exist in your version's `index.d.ts`, use the one that does; do not guess.

## 4. Permissions

`permissionLevel` (`CommandPermissionLevel`; older betas called the type `CustomCommandPermissionLevel`):
- `Any` — everyone (use with `cheatsRequired: false` for public commands)
- `GameDirectors` — operators and also command blocks/functions
- `Admin` — operators only; **cannot** be run from command blocks, functions or scripts
- `Host`, `Owner` — only the world host / the dedicated-server console

`cheatsRequired: true` means the world needs cheats enabled for the command to run.

## 5. Origins and results

`origin.sourceType` (`Block`, `Entity`, `NPCDialogue`, `Server`), `origin.sourceEntity`, `origin.sourceBlock`, `origin.initiator`. For player-only commands:

```js
const player = origin.sourceEntity;
if (!(player instanceof Player)) {
  return { status: CustomCommandStatus.Failure, message: "Only players can use this command." };
}
```

Opening a form from a command: see `server-ui.md` (the chat window is open when the command runs, so retry on `UserBusy`).

## 6. When a command does not show up

| Symptom | Likely cause |
|---|---|
| Not in autocomplete, "Unknown command" | not registered in `startup`; script failed to load (check Content Log); missing/old `@minecraft/server` dependency; name without namespace |
| Script loads but error mentions enum | `registerEnum` after `registerCommand`, or param `name` ≠ enum name |
| Works for you but not command blocks | permission `Admin`; use `GameDirectors` |
| "Native function ... does not have required privileges" | changing the world directly in the callback; wrap in `system.run` |
| `TypeError: ... is not a function/undefined` on registry | `@minecraft/server` 1.x in manifest, or a game older than the module version |

## 7. Alternatives (only when custom commands are impossible)

- Game too old for server 2.x commands: `/scriptevent myaddon:action arg` + `system.afterEvents.scriptEventReceive.subscribe(...)` (id must be namespaced; works from chat for operators, command blocks and functions).
- Fixed command sequences without logic: a `.mcfunction` file in `functions/` and `/function name`.
- `!command` chat prefixes via `world.beforeEvents.chatSend` are a last resort: they are not real commands (no autocomplete/permissions) and the event's availability changes between versions.
