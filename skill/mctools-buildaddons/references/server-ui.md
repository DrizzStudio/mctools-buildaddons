# UI with @minecraft/server-ui

Contents: 1. Setup · 2. Which form to use · 3. Showing forms safely · 4. ActionFormData · 5. ModalFormData · 6. MessageFormData · 7. Newer 2.1+ features · 8. Limits and corrections

Use `@minecraft/server-ui` for any menu, shop, settings screen, confirmation or text input. It needs no resource pack and no JSON UI.

## 1. Setup

Manifest `dependencies` must contain both modules (see `versions-and-manifest.md`):

```json
{ "module_name": "@minecraft/server", "version": "2.4.0" },
{ "module_name": "@minecraft/server-ui", "version": "2.0.0" }
```

```js
import { ActionFormData, ModalFormData, MessageFormData, FormCancelationReason } from "@minecraft/server-ui";
```

If a script imports `@minecraft/server-ui` and the manifest does not list it, the whole script fails to load.

## 2. Which form to use

| Need | Form |
|---|---|
| A list of buttons (menu, shop, teleport list), optional icons | `ActionFormData` |
| Inputs: toggle, slider, dropdown, text field | `ModalFormData` |
| Yes/No or OK/Cancel | `MessageFormData` |
| Dynamic live-updating screens (needs server-ui 2.1+) | `CustomForm` (section 7) |

## 3. Showing forms safely

`form.show(player)` returns a Promise. Rules:
- Always `await`/`.then` inside `try/catch` or `.catch`, so a player who leaves does not produce an unhandled error.
- Check `response.canceled` before reading `selection` / `formValues`.
- If the form is triggered by a **chat command**, the chat window is still open, so the first `show()` is canceled with `cancelationReason === FormCancelationReason.UserBusy`. Retry until it opens. Forms started from an item use (`world.afterEvents.itemUse`) or a button interaction do not have this problem.

```js
async function showWhenReady(player, form, maxTries = 30) {
  for (let i = 0; i < maxTries; i++) {
    const response = await form.show(player);
    if (response.cancelationReason !== FormCancelationReason.UserBusy) return response;
    await system.waitTicks(10); // 0.5 s
  }
  return undefined; // gave up
}
```

From a command callback: `system.run(() => { openMenu(player).catch((e) => console.warn(e)); });` then `return { status: CustomCommandStatus.Success };`.

If your pinned version's `index.d.ts` shows different behavior (for example `show` throwing instead of returning a canceled response), adapt the loop; read the d.ts, do not assume.

## 4. ActionFormData

```js
const form = new ActionFormData()
  .title("Shop")
  .body("Choose an item")
  .button("Diamond Sword\n§210 coins", "textures/items/diamond_sword") // icon path is relative to the resource pack, no extension
  .button("Close");

const res = await showWhenReady(player, form);
if (!res || res.canceled) return;
switch (res.selection) { // index of the button, in the order added
  case 0: /* buy */ break;
  default: break;
}
```

Icons are optional. Vanilla texture paths (`textures/items/...`, `textures/blocks/...`) work without a resource pack; custom icons need the texture in the RP and registered in `item_texture.json`/`terrain_texture.json` if referenced by name elsewhere.

## 5. ModalFormData (server-ui 2.x signatures)

In 2.x the optional values moved into an options object. Older tutorials (`.toggle(label, true)`, `.slider(label, min, max, step, default)`) are wrong for 2.x.

```js
const form = new ModalFormData()
  .title("Settings")
  .toggle("Enable sounds", { defaultValue: true })
  .slider("Volume", 0, 10, { valueStep: 1, defaultValue: 5 })
  .textField("Nickname", "Type here", { defaultValue: "" })
  .dropdown("Theme", ["Light", "Dark"], { defaultValueIndex: 0 })
  .submitButton("Save");

const res = await showWhenReady(player, form);
if (!res || res.canceled) return;
const [sounds, volume, nickname, theme] = res.formValues; // boolean, number, string, number (dropdown = selected index)
```

- Decorative elements `.header(text)`, `.label(text)`, `.divider()` exist in 2.x. In `formValues` they occupy a slot with value `undefined`, so indexes shift. Destructure with the placeholders in the same order as the controls were added.
- `formValues` entries can be `undefined`; validate (trim and length-check text, clamp numbers) before using them.
- Text input is user-controlled: never use it directly as a command string or identifier.

## 6. MessageFormData

```js
const form = new MessageFormData()
  .title("Delete home?")
  .body("This cannot be undone.")
  .button1("No")   // selection 0
  .button2("Yes"); // selection 1

const res = await showWhenReady(player, form);
if (!res || res.canceled || res.selection !== 1) return;
```

Closing the form (X, Esc) is reported as `canceled`; treat it as "No".

## 7. Newer features (server-ui 2.1.0+)

`CustomForm`, `MessageBox`, and observables (`ObservableBoolean`, `ObservableNumber`, `ObservableString`, `ObservableUIRawMessage`) exist only from 2.1.0; `CustomForm.image` and `MessageBox` button options from 2.2.0 (which needs a newer `@minecraft/server`). Use them only when the user needs live-updating or richer layouts, bump the manifest versions accordingly, raise `min_engine_version`, and read the type definitions first because this API is newer and still evolving.

## 8. Limits and idea corrections

- Forms are per player; there is no server-wide shared UI, no persistent HUD, no drag-and-drop inventory, and no arbitrary layouts or custom fonts.
- No images from URLs; only texture paths from packs.
- A player can only have one form open; calling `show` while another is open returns `UserBusy` as well.
- Want a "chest GUI" with slots, a custom HUD, or a custom inventory screen? Not possible through the Script API. Closest options: `ActionFormData` with icons (best), or a real chest/barrel block for items players must move. JSON UI hacks exist but break across game updates; do not offer them unless the user insists and accepts that.
- Forms cannot be shown to non-players (mobs, NPC entities); use the NPC component or a command source that resolves to a `Player`.
