#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import readline from 'node:readline';

const kitDir = fileURLToPath(new URL('./kit/', import.meta.url));
const IGNORE_LINES = [
  '__pycache__/',
  '.harness/plans/*/logs/',
  '.harness/metrics.jsonl',
  '.harness/bench.csv',
  '.harness/backup/',
  '.harness/.env',
];

function usage() {
  return `Usage: ufoz-harness [--yes] [--dry-run] [--dir <path>] [--help]
  --yes      install without prompting
  --dry-run  show what would be written, write nothing
  --dir      target project dir (default: cwd)
  --help     show this help`;
}

function hasTool(cmd) {
  try {
    let r;
    if (process.platform === 'win32') {
      r = spawnSync(`${cmd} --version`, { shell: true, stdio: 'ignore' });
    } else {
      r = spawnSync(cmd, ['--version'], { stdio: 'ignore' });
    }
    return r.status === 0;
  } catch {
    return false;
  }
}

function walk(dir) {
  const out = [];
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    const st = fs.statSync(full);
    if (st.isDirectory()) out.push(...walk(full));
    else if (st.isFile()) out.push(full);
  }
  return out;
}

function stamp() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

let dir = process.cwd();
let yes = false;
let dryRun = false;
const args = process.argv.slice(2);
for (let i = 0; i < args.length; i++) {
  const a = args[i];
  if (a === '--yes') yes = true;
  else if (a === '--dry-run') dryRun = true;
  else if (a === '--help') {
    console.log(usage());
    process.exit(0);
  } else if (a === '--dir') {
    const v = args[++i];
    if (!v) {
      console.error(usage());
      process.exit(1);
    }
    dir = v;
  } else {
    console.error(usage());
    process.exit(1);
  }
}
dir = path.resolve(dir);

// Preflight, before any write, even for --dry-run.
const missing = [];
let pythonOk = hasTool('python');
if (!pythonOk) pythonOk = hasTool('python3');
if (!pythonOk) missing.push('python');
if (!hasTool('git')) missing.push('git');
const piLauncher = path.join(os.homedir(), '.pi', 'agent', 'bin', 'pi-launcher.js');
if (!fs.existsSync(piLauncher) && !hasTool('pi')) missing.push('pi');
if (missing.length > 0) {
  for (const m of missing) {
    if (m === 'python') console.error('missing python: install Python 3');
    else if (m === 'git') console.error('missing git: install git');
    else if (m === 'pi') console.error('missing pi: install pi from https://pi.dev');
  }
  process.exit(1);
}

// Plan the install.
const kitFiles = walk(kitDir).sort();
const plan = kitFiles.map((abs) => {
  const rel = path.relative(kitDir, abs);
  const targetRel = path.basename(rel) === 'gitignore' ? path.join(path.dirname(rel), '.gitignore') : rel;
  const display = targetRel.split(path.sep).join('/');
  const target = path.join(dir, targetRel);
  let needBackup = false;
  if (fs.existsSync(target) && fs.statSync(target).isFile()) {
    const a = fs.readFileSync(abs);
    const b = fs.readFileSync(target);
    needBackup = !a.equals(b);
  }
  return { abs, target, display, rel: targetRel, needBackup };
});

if (dryRun) {
  for (const e of plan) {
    console.log(`${e.needBackup ? 'backup+write' : 'write'} ${e.display}`);
  }
  process.exit(0);
}

if (!yes) {
  if (!process.stdin.isTTY) {
    console.error('re-run with --yes to install non-interactively');
    process.exit(1);
  }
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  const answer = await new Promise((resolve) => {
    rl.question(`Install ufoz-harness into ${dir}? This overwrites harness files (backups kept). [y/N] `, resolve);
  });
  rl.close();
  const norm = answer.trim().toLowerCase();
  if (norm !== 'y' && norm !== 'yes') process.exit(0);
}

// Install: backups first, then copy.
const needy = plan.filter((e) => e.needBackup);
if (needy.length > 0) {
  const backupRoot = path.join(dir, '.harness', 'backup', stamp());
  for (const e of needy) {
    const dest = path.join(backupRoot, e.rel);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.copyFileSync(e.target, dest);
  }
}
for (const e of plan) {
  fs.mkdirSync(path.dirname(e.target), { recursive: true });
  fs.copyFileSync(e.abs, e.target);
}

// .gitignore: never overwrite, append missing lines only.
const giPath = path.join(dir, '.gitignore');
let giContent = '';
if (fs.existsSync(giPath)) giContent = fs.readFileSync(giPath, 'utf8');
else giContent = '';
const giLines = giContent.split('\n').map((l) => l.replace(/\r$/, ''));
const toAdd = IGNORE_LINES.filter((l) => !giLines.includes(l));
if (toAdd.length > 0) {
  if (giContent.length > 0 && !giContent.endsWith('\n')) giContent += '\n';
  giContent += toAdd.map((l) => l + '\n').join('');
  fs.writeFileSync(giPath, giContent, 'utf8');
}

if (!fs.existsSync(path.join(dir, '.git'))) {
  console.log('not a git repo: run git init (the runner needs git)');
}

console.log(`files written: ${plan.length}, files backed up: ${needy.length}`);
console.log('Next: python .harness/selftest.py');
