import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { HarnessRun } from '../types'

// Viewer only: run_plan.py keeps owning the run (Bash background), this band only reads
// its files, so a reload of the mod never touches a live plan.

const runs = atom({ plugin: 'harness-band', key: 'runs' } as const, [] as HarnessRun[])

const POLL_MS = 2000
const KEEP_DONE_MS = 60_000
const TAIL = 3
const DETAIL_KEYS = ['path', 'command', 'file_path', 'filePath', 'pattern', 'url']
const EXECUTORS = ['pi', 'claude', 'opencode', 'cline', 'cline-acp', 'llama']

// Same shape as watch.render_line, one display line or null.
function renderLine(line: string): string | null {
  line = line.replace(/\r?\n$/, '')
  if (!line.trim()) return null
  if (line.startsWith('[toolCall ')) {
    const rest = line.slice('[toolCall '.length)
    const end = rest.indexOf(']')
    const name = (end < 0 ? rest : rest.slice(0, end)).trim()
    const args = end < 0 ? '' : rest.slice(end + 1).trim()
    return `${name.padEnd(6)} ${detail(args)}`
  }
  if (line.startsWith('[tool error] ')) return `✖ tool error: ${line.slice('[tool error] '.length)}`
  if (line.startsWith('DONE:')) return `✔ ${line}`
  if (line.startsWith('BLOCKED:')) return `✖ ${line}`
  return `│ ${line}`
}

function detail(args: string): string {
  try {
    const obj = JSON.parse(args.split('\n', 1)[0])
    if (obj && typeof obj === 'object') {
      for (const key of DETAIL_KEYS) {
        if (key in obj) return String(obj[key]).split('\n', 1)[0]
      }
    }
  } catch {}
  return args
}

// Same as watch.log_title: `T4.repair2.claude.log` -> `T4 repair 2`.
function logTitle(name: string): string {
  const parts = name.replace(/\.log$/, '').split('.')
  if (parts.length > 1 && EXECUTORS.includes(parts[parts.length - 1])) parts.pop()
  return parts.map(p => p.replace(/^(retry|repair)(\d+)$/, '$1 $2')).join(' ')
}

async function list($: EngineInterface, dir: string) {
  return $.fs.list(dir).catch(() => [])
}

async function snapshot($: EngineInterface, slug: string, planDir: string, prev?: HarnessRun) {
  let ids: string[] = []
  try {
    const data = JSON.parse(await $.fs.read(`${planDir}/tasks.json`))
    ids = (data.tasks ?? []).map((t: { id?: string }) => t.id).filter(Boolean)
  } catch {}

  let pass = 0
  for (const id of ids) {
    const text: string = await $.fs.read(`${planDir}/items/${id}.report.md`).catch(() => '')
    if (/^RESULT: pass\s*$/m.test(text)) pass += 1
  }

  const logs = (await list($, `${planDir}/logs`))
    .filter((f: { kind: string; name: string }) => f.kind === 'file' && f.name.endsWith('.log'))
    .sort((a: { mtimeMs: number }, b: { mtimeMs: number }) => b.mtimeMs - a.mtimeMs)
  let log = prev?.log ?? ''
  let lines = prev?.lines ?? []
  if (logs.length) {
    const text: string = await $.fs.read(`${planDir}/logs/${logs[0].name}`).catch(() => '')
    log = logTitle(logs[0].name)
    lines = text
      .split('\n')
      .map(renderLine)
      .filter((l): l is string => l !== null)
      .slice(-TAIL)
  }

  return { slug, pass, total: ids.length, log, lines, isDone: false, endedAt: 0 }
}

async function poll($: EngineInterface) {
  const root = await $.session.cwd()
  const now = await $.clock.now()
  const prev: HarnessRun[] = await read($, runs)
  const next: HarnessRun[] = []
  const seen = new Set<string>()

  // worktree runs (the default), then in-place runs (--no-worktree)
  const dirs: [string, string][] = []
  for (const d of await list($, `${root}/.worktrees`)) {
    if (d.kind === 'dir') dirs.push([d.name, `${root}/.worktrees/${d.name}/.harness/plans/${d.name}`])
  }
  for (const d of await list($, `${root}/.harness/plans`)) {
    if (d.kind === 'dir') dirs.push([d.name, `${root}/.harness/plans/${d.name}`])
  }

  for (const [slug, planDir] of dirs) {
    if (seen.has(slug)) continue
    if (!(await $.fs.exists(`${planDir}/run.lock`))) continue
    seen.add(slug)
    next.push(await snapshot($, slug, planDir, prev.find(r => r.slug === slug)))
  }

  // a run whose lock just went away stays a minute as a done row
  for (const run of prev) {
    if (seen.has(run.slug)) continue
    if (!run.isDone) {
      const wt = `${root}/.worktrees/${run.slug}/.harness/plans/${run.slug}`
      const planDir = (await $.fs.exists(wt)) ? wt : `${root}/.harness/plans/${run.slug}`
      const last = await snapshot($, run.slug, planDir, run)
      next.push({ ...last, isDone: true, endedAt: now })
    } else if (now - run.endedAt < KEEP_DONE_MS) {
      next.push(run)
    }
  }

  if (JSON.stringify(next) !== JSON.stringify(prev)) await update($, runs, () => next)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const result = await next(e)
    let isBusy = false

    $.clock.every(POLL_MS, () => {
      if (isBusy) return
      isBusy = true
      void poll($).finally(() => {
        isBusy = false
      })
    })

    return result
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const shown = await read($, runs)
    if (e.props.hasSurvey || shown.length === 0) return next(e)

    const { Box, Text } = $.ui.resolve(e)
    const budget = Math.max(1, e.props.maxRows - 2)
    const perRun = Math.max(0, Math.floor(budget / shown.length) - 1)

    return (
      <Box flexDirection="column">
        {shown.map(run => {
          const isOk = run.isDone && run.total > 0 && run.pass === run.total
          const head = run.isDone
            ? `${isOk ? '✔' : '✖'} harness ${run.slug} · done · ${run.pass}/${run.total} pass`
            : `▶ harness ${run.slug} · ${run.pass}/${run.total} pass · ${run.log || 'starting'}`
          return (
            <Box key={run.slug} flexDirection="column">
              <Text bold color={run.isDone ? (isOk ? 'green' : 'red') : 'cyan'} wrap="truncate-end">
                {head}
              </Text>
              {run.isDone
                ? null
                : run.lines.slice(-perRun).map((line, i) => (
                    <Text key={`${run.slug}-${i}`} dimColor wrap="truncate-end">
                      {'  '}
                      {line}
                    </Text>
                  ))}
            </Box>
          )
        })}
      </Box>
    )
  })
}
