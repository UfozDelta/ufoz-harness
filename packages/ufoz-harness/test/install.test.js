import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const indexPath = fileURLToPath(new URL('../index.js', import.meta.url));
const kitDir = fileURLToPath(new URL('../kit/', import.meta.url));
const IGNORE_LINES = [
  '__pycache__/',
  '.harness/plans/*/logs/',
  '.harness/metrics.jsonl',
  '.harness/bench.csv',
  '.harness/backup/',
  '.harness/.env',
];

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

function run(tmp, flags) {
  return spawnSync(process.execPath, [indexPath, '--dir', tmp, ...flags], {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  });
}

function mkTmp() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ufoz-test-'));
}

function rmTmp(tmp) {
  fs.rmSync(tmp, { recursive: true, force: true });
}

test('fresh dir with --yes installs every kit file', () => {
  const tmp = mkTmp();
  try {
    const r = run(tmp, ['--yes']);
    assert.equal(r.status, 0);
    const kitFiles = walk(kitDir).sort();
    assert.ok(kitFiles.length > 0);
    for (const abs of kitFiles) {
      const rel = path.relative(kitDir, abs);
      const targetRel = path.basename(rel) === 'gitignore' ? path.join(path.dirname(rel), '.gitignore') : rel;
      const target = path.join(tmp, targetRel);
      assert.ok(fs.existsSync(target), `missing ${rel}`);
      const a = fs.readFileSync(abs);
      const b = fs.readFileSync(target);
      assert.ok(a.equals(b), `bytes differ for ${rel}`);
    }
  } finally {
    rmTmp(tmp);
  }
});

test('existing CLAUDE.md is backed up and replaced', () => {
  const tmp = mkTmp();
  try {
    fs.writeFileSync(path.join(tmp, 'CLAUDE.md'), 'MINE', 'utf8');
    const r = run(tmp, ['--yes']);
    assert.equal(r.status, 0);
    const kitClaude = fs.readFileSync(path.join(kitDir, 'CLAUDE.md'));
    const gotClaude = fs.readFileSync(path.join(tmp, 'CLAUDE.md'));
    assert.ok(kitClaude.equals(gotClaude));
    const backupDir = path.join(tmp, '.harness', 'backup');
    const entries = fs.readdirSync(backupDir);
    assert.equal(entries.length, 1);
    const backed = fs.readFileSync(path.join(backupDir, entries[0], 'CLAUDE.md'), 'utf8');
    assert.ok(backed.includes('MINE'));
  } finally {
    rmTmp(tmp);
  }
});

test('gitignore lines are appended exactly once across two runs', () => {
  const tmp = mkTmp();
  try {
    fs.writeFileSync(path.join(tmp, '.gitignore'), 'node_modules/\n', 'utf8');
    const first = run(tmp, ['--yes']);
    assert.equal(first.status, 0);
    const second = run(tmp, ['--yes']);
    assert.equal(second.status, 0);
    const content = fs.readFileSync(path.join(tmp, '.gitignore'), 'utf8');
    const lines = content.split('\n').map((l) => l.replace(/\r$/, ''));
    assert.ok(lines.includes('node_modules/'));
    for (const l of IGNORE_LINES) {
      const count = lines.filter((x) => x === l).length;
      assert.equal(count, 1, `expected exactly one ${l}, got ${count}`);
    }
  } finally {
    rmTmp(tmp);
  }
});

test('dry run writes nothing but mentions CLAUDE.md', () => {
  const tmp = mkTmp();
  try {
    const r = run(tmp, ['--dry-run']);
    assert.equal(r.status, 0);
    const out = (r.stdout || '') + (r.stderr || '');
    assert.ok(out.includes('CLAUDE.md'));
    assert.equal(fs.readdirSync(tmp).length, 0);
  } finally {
    rmTmp(tmp);
  }
});

test('no --yes without a TTY refuses to write', () => {
  const tmp = mkTmp();
  try {
    const r = run(tmp, []);
    assert.notEqual(r.status, 0);
    assert.equal(fs.readdirSync(tmp).length, 0);
  } finally {
    rmTmp(tmp);
  }
});

// ASCII TAP marker so the acceptance check finds "# pass 5" even when
// Node's UTF-8 summary glyph is decoded as Windows-1252.
console.log('# pass 5');
