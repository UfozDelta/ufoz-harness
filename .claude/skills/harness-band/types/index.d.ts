export type HarnessRun = {
  slug: string
  pass: number
  total: number
  log: string
  lines: string[]
  isDone: boolean
  endedAt: number
}

declare module 'claude-code' {
  interface PluginState {
    'harness-band': { runs: HarnessRun[] }
  }
}
