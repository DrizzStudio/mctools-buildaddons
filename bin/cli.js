#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const pkg = require('../package.json');

const SKILL_NAME = 'mctools-buildaddons';
const SOURCE = path.join(__dirname, '..', 'skill', SKILL_NAME);
const HOME = os.homedir();
const CWD = process.cwd();
const home = (...parts) => path.join(HOME, ...parts);

// Where each coding agent looks for skills.
//   global  = available in every project
//   project = relative to the current project folder (use --project)
//   marker  = folder whose existence tells us the agent is installed
const AGENTS = [
  { id: 'claude', label: 'Claude Code', global: home('.claude', 'skills'), project: path.join('.claude', 'skills'), marker: home('.claude') },
  { id: 'codex', label: 'Codex CLI', global: home('.codex', 'skills'), project: path.join('.codex', 'skills'), marker: home('.codex') },
  { id: 'gemini', label: 'Gemini CLI', global: home('.gemini', 'skills'), project: path.join('.gemini', 'skills'), marker: home('.gemini') },
  { id: 'cursor', label: 'Cursor', global: home('.cursor', 'skills'), project: path.join('.cursor', 'skills'), marker: home('.cursor') },
  { id: 'cline', label: 'Cline', global: home('.cline', 'skills'), project: path.join('.cline', 'skills'), marker: home('.cline') },
  { id: 'continue', label: 'Continue', global: home('.continue', 'skills'), project: path.join('.continue', 'skills'), marker: home('.continue') },
  { id: 'droid', label: 'Factory Droid', global: home('.factory', 'skills'), project: path.join('.factory', 'skills'), marker: home('.factory') },
  { id: 'amp', label: 'Amp / Kimi CLI', global: home('.config', 'agents', 'skills'), project: path.join('.agents', 'skills'), marker: home('.config', 'agents') },
  { id: 'copilot', label: 'GitHub Copilot', global: null, project: path.join('.github', 'skills'), marker: null },
];

const HELP = `${SKILL_NAME} ${pkg.version}
Installs the "${SKILL_NAME}" skill (Minecraft Bedrock add-on builder) into your AI coding agents.

Usage:
  npx ${SKILL_NAME} [command] [options]

Commands:
  install      Install or update the skill (default)
  uninstall    Remove the skill
  list         Show supported agents and where the skill is installed

Options:
  -a, --agent <ids>   Target agents, comma separated: ${AGENTS.map((a) => a.id).join(', ')}
      --all           Target every supported agent (not only detected ones)
  -p, --project       Use the current project folder instead of your home folder
  -d, --dir <path>    Install into a custom skills folder
  -f, --force         Reinstall even if already up to date
      --dry-run       Show what would happen without changing anything
  -v, --version       Print version
  -h, --help          Show this help

Examples:
  npx ${SKILL_NAME}                  # every detected agent (Claude Code if none found)
  npx ${SKILL_NAME} -a claude,codex  # only these two
  npx ${SKILL_NAME} --project        # into ./.claude/skills etc. for this project only
  npx ${SKILL_NAME} uninstall
`;

function fail(message) {
  console.error(`Error: ${message}`);
  process.exit(1);
}

function parseArgs(argv) {
  const opts = { command: 'install', agents: [], all: false, project: false, dir: null, force: false, dryRun: false };
  const positional = [];
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    const value = () => {
      if (i + 1 >= argv.length) fail(`Missing value for ${arg}`);
      return argv[++i];
    };
    const addAgents = (text) => opts.agents.push(...text.split(',').map((s) => s.trim().toLowerCase()).filter(Boolean));
    if (arg === '-h' || arg === '--help') {
      console.log(HELP);
      process.exit(0);
    } else if (arg === '-v' || arg === '--version') {
      console.log(pkg.version);
      process.exit(0);
    } else if (arg === '-a' || arg === '--agent') addAgents(value());
    else if (arg.startsWith('--agent=')) addAgents(arg.slice('--agent='.length));
    else if (arg === '--all') opts.all = true;
    else if (arg === '-p' || arg === '--project') opts.project = true;
    else if (arg === '-d' || arg === '--dir') opts.dir = path.resolve(value());
    else if (arg.startsWith('--dir=')) opts.dir = path.resolve(arg.slice('--dir='.length));
    else if (arg === '-f' || arg === '--force') opts.force = true;
    else if (arg === '--dry-run') opts.dryRun = true;
    else if (arg.startsWith('-')) fail(`Unknown option: ${arg}\n\n${HELP}`);
    else positional.push(arg);
  }
  if (positional.length > 1) fail(`Unexpected argument: ${positional[1]}`);
  if (positional.length === 1) {
    const aliases = { install: 'install', add: 'install', uninstall: 'uninstall', remove: 'uninstall', list: 'list', help: 'help' };
    const command = aliases[positional[0]];
    if (!command) fail(`Unknown command: ${positional[0]}\n\n${HELP}`);
    if (command === 'help') {
      console.log(HELP);
      process.exit(0);
    }
    opts.command = command;
  }
  return opts;
}

// ---------------------------------------------------------------- file helpers

function keep(file) {
  const base = path.basename(file);
  return base !== '__pycache__' && base !== '.DS_Store' && !base.endsWith('.pyc');
}

function listFiles(root) {
  const out = [];
  (function walk(dir) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (!keep(full)) continue;
      if (entry.isDirectory()) walk(full);
      else out.push(path.relative(root, full));
    }
  })(root);
  return out.sort();
}

function sameContent(a, b) {
  const filesA = listFiles(a);
  const filesB = listFiles(b);
  if (filesA.length !== filesB.length || filesA.some((f, i) => f !== filesB[i])) return false;
  return filesA.every((f) => fs.readFileSync(path.join(a, f)).equals(fs.readFileSync(path.join(b, f))));
}

function makeScriptsExecutable(dest) {
  const scripts = path.join(dest, 'scripts');
  if (!fs.existsSync(scripts)) return;
  for (const name of fs.readdirSync(scripts)) {
    if (name.endsWith('.py')) {
      try {
        fs.chmodSync(path.join(scripts, name), 0o755);
      } catch (_) {
        /* Windows: nothing to do */
      }
    }
  }
}

// ---------------------------------------------------------------- targets

function projectMarkerExists(agent) {
  return fs.existsSync(path.join(CWD, agent.project.split(path.sep)[0]));
}

function resolveTargets(opts) {
  if (opts.dir) return [{ id: 'custom', label: 'Custom folder', dir: opts.dir }];

  let selected;
  if (opts.agents.length) {
    selected = opts.agents.map((id) => {
      const agent = AGENTS.find((a) => a.id === id);
      if (!agent) fail(`Unknown agent "${id}". Valid agents: ${AGENTS.map((a) => a.id).join(', ')}`);
      return agent;
    });
  } else if (opts.all) {
    selected = AGENTS.slice();
  } else {
    selected = AGENTS.filter((a) => (opts.project ? projectMarkerExists(a) : a.marker && fs.existsSync(a.marker)));
    if (selected.length === 0) selected = [AGENTS[0]]; // default: Claude Code
  }

  const targets = [];
  for (const agent of selected) {
    const dir = opts.project ? path.join(CWD, agent.project) : agent.global;
    if (!dir) {
      console.log(`  skip  ${agent.label}: no global skills folder (use --project)`);
      continue;
    }
    targets.push({ id: agent.id, label: agent.label, dir });
  }
  return targets;
}

// ---------------------------------------------------------------- python check

function checkPython() {
  for (const cmd of ['python3', 'python', 'py']) {
    const result = spawnSync(cmd, ['--version'], { encoding: 'utf8' });
    if (result.status === 0) {
      const match = /Python (\d+)\.(\d+)/.exec(`${result.stdout || ''}${result.stderr || ''}`);
      if (match) return { cmd, major: Number(match[1]), minor: Number(match[2]) };
    }
  }
  return null;
}

// ---------------------------------------------------------------- commands

function doInstall(opts) {
  if (!fs.existsSync(path.join(SOURCE, 'SKILL.md'))) fail('Package is broken: skill files are missing. Reinstall the package.');
  const targets = resolveTargets(opts);
  if (targets.length === 0) fail('Nothing to install to.');

  let lastDest = null;
  for (const target of targets) {
    const dest = path.join(target.dir, SKILL_NAME);
    const exists = fs.existsSync(dest);
    if (exists && !opts.force && sameContent(SOURCE, dest)) {
      console.log(`  [up to date]  ${target.label}  ${dest}`);
      lastDest = dest;
      continue;
    }
    if (opts.dryRun) {
      console.log(`  [dry run]     ${target.label}: would ${exists ? 'update' : 'install'} ${dest}`);
      continue;
    }
    try {
      if (exists) fs.rmSync(dest, { recursive: true, force: true });
      fs.mkdirSync(target.dir, { recursive: true });
      fs.cpSync(SOURCE, dest, { recursive: true, filter: keep });
      makeScriptsExecutable(dest);
    } catch (error) {
      console.error(`  [failed]      ${target.label}: ${error.message}`);
      process.exitCode = 1;
      continue;
    }
    console.log(`  [${exists ? 'updated' : 'installed'}]  ${target.label}  ${dest}`);
    lastDest = dest;
  }

  if (opts.dryRun) return;

  const python = checkPython();
  if (!python) {
    console.log('\nWarning: Python 3 was not found. The skill scripts (scaffold, validator, texture generator) need Python 3.8+.');
  } else if (python.major < 3 || (python.major === 3 && python.minor < 8)) {
    console.log(`\nWarning: found Python ${python.major}.${python.minor}; the skill scripts need Python 3.8 or newer.`);
  }

  if (lastDest) {
    console.log('\nDone. Restart your AI CLI, then ask for example:');
    console.log('  "Buatkan addon Minecraft dengan command /shop dan menu UI, siap texture"');
    console.log(`\nThe scripts live in: ${path.join(lastDest, 'scripts')}`);
  }
}

function doUninstall(opts) {
  const targets = resolveTargets(opts);
  let removed = 0;
  for (const target of targets) {
    const dest = path.join(target.dir, SKILL_NAME);
    if (!fs.existsSync(dest)) {
      console.log(`  [not found]   ${target.label}  ${dest}`);
      continue;
    }
    if (opts.dryRun) {
      console.log(`  [dry run]     ${target.label}: would remove ${dest}`);
      continue;
    }
    fs.rmSync(dest, { recursive: true, force: true });
    console.log(`  [removed]     ${target.label}  ${dest}`);
    removed++;
  }
  if (!opts.dryRun) console.log(removed ? '\nDone.' : '\nNothing was installed in those locations.');
}

function doList() {
  console.log(`Supported agents (skill: ${SKILL_NAME} ${pkg.version})\n`);
  for (const agent of AGENTS) {
    const detected = agent.marker ? fs.existsSync(agent.marker) : false;
    const globalDest = agent.global ? path.join(agent.global, SKILL_NAME) : null;
    const projectDest = path.join(CWD, agent.project, SKILL_NAME);
    const where = [];
    if (globalDest && fs.existsSync(globalDest)) where.push('global');
    if (fs.existsSync(projectDest)) where.push('this project');
    console.log(`  ${agent.id.padEnd(9)} ${agent.label.padEnd(16)} ${detected ? 'detected    ' : 'not detected'}  ${where.length ? `installed: ${where.join(', ')}` : 'not installed'}`);
  }
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (opts.command === 'list') return doList();
  console.log(`${SKILL_NAME} ${pkg.version}${opts.dryRun ? ' (dry run)' : ''}\n`);
  if (opts.command === 'uninstall') return doUninstall(opts);
  return doInstall(opts);
}

main();
