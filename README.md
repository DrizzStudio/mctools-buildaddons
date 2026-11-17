# mctools-buildaddons

One command that installs the **mctools-buildaddons** AI skill into your terminal AI agents. The skill teaches the agent to build original Minecraft Bedrock add-ons that load without errors: valid manifests, self-generated UUIDs, working custom commands, `@minecraft/server-ui` menus, and original license-free textures.

```bash
npx mctools-buildaddons
```

Restart your AI CLI, then ask, for example: *"Buatkan addon Minecraft dengan command /shop dan menu UI"*.

## Options

| Command | What it does |
|---|---|
| `npx mctools-buildaddons` | Install/update for every detected agent (Claude Code if none is found) |
| `npx mctools-buildaddons -a claude,codex` | Only the listed agents |
| `npx mctools-buildaddons --project` | Install into the current project (`./.claude/skills`, ...) |
| `npx mctools-buildaddons --dir <path>` | Install into any skills folder |
| `npx mctools-buildaddons list` | Show agents and where the skill is installed |
| `npx mctools-buildaddons uninstall` | Remove the skill |
| `--dry-run`, `--force`, `--all` | Preview, reinstall, or target every supported agent |

Agent ids: `claude`, `codex`, `gemini`, `cursor`, `cline`, `continue`, `droid`, `amp`, `copilot` (project only).

## Requirements

Node.js 18+ to run the installer. The skill's helper scripts need Python 3.8+.

## Publishing (maintainers)

```bash
npm login
npm publish --access public      # first release
# later: edit skill/mctools-buildaddons/, bump "version" in package.json, then npm publish
```

Test locally before publishing: `node bin/cli.js --dry-run`, or `npm pack` and install the tarball.

## Link
https://buildaddons.drizztools.my.id



## License

MIT

