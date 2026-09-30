# Plan: suite-medium (minimal Next.js App Router todo app — API route, store, validation, component, page)

Work dir: `{work}` - every path in this plan is relative to it; cd there before running anything.

## Goal
Turn the seeded Next.js shell into a small todo app: a route handler, the in-memory store behind it, a
shared validation module, a presentational list component, and a page that wires the four together. The
first four tasks touch disjoint files and have no dependencies on each other; the fifth task is the join.

## Starting point (already exists — do not re-create)
`app/layout.tsx` (root layout + `metadata`), `app/page.tsx` (heading + `formatCount(0)`),
`lib/format.ts` (`formatCount(n: number): string`),
`next.config.mjs`, `package.json` (no dependencies of its own), `tsconfig.json` (strict, `jsx: react-jsx`,
`moduleResolution: bundler`, `include: **/*.ts(x)`), `next-env.d.ts`, `vitest.config.ts`
(environment `jsdom`, `@vitejs/plugin-react`).

## Assumptions / Decisions (fixed — the executor must not re-decide)
- The seed has **no** `lib/todos-store.ts`: the store module is T2's file and is created from scratch. This
  plan fixes the **contract** up front instead — the exported `Todo` interface and the six function
  signatures below are agreed before any task starts, so T1 (route), T4 (type-only import) and T5 (page)
  all call the same names. **T2 must keep every exported name and signature exactly as written here.**
- Consequence of the store not being in the seed: T1 and T4 import `lib/todos-store`, so their `tsc` step
  only passes once T2's file exists. In a parallel run where T2 has not landed yet the "cannot find module"
  type errors are expected; the file/export checks in the acceptance are the real gate for those tasks.
- `lib/todos-store.ts` API (T2): module state `todos: Todo[]` and `nextId: number`; `Todo` is
  `{ id: number; title: string; done: boolean }` (exported).
  - `resetTodos(): void` — clears the list and sets `nextId` back to 1 (ids restart at 1 after a reset;
    this matches the small fixture's `reset_store`/`reset_tag_store`).
  - `listTodos(): Todo[]` — shallow copies, in creation order; callers cannot mutate the store.
  - `getTodo(id: number): Todo | null`, `toggleTodo(id: number): Todo | null` (flips `done`, `null` for a
    miss), `removeTodo(id: number): boolean` (`true` when a todo was actually removed).
  - `addTodo(title: string): Todo` — stores the title as given (trimming is the caller's job, see T1/T3),
    `done: false`, ids from 1.
- `app/api/todos/route.ts` (T1) is a Next App Router route module: `export async function GET(): Promise<Response>`
  answering `200` with the JSON array from `listTodos()`, and
  `export async function POST(request: Request): Promise<Response>` answering `201` with the created todo.
  A body that is not JSON, has no `title`, has a non-string `title`, or a blank title longer than 120
  characters after trimming answers `400` with `{ "error": string }`. The route does its own inline
  validation and must not import `lib/validate.ts` (that is T3's file).
- `lib/validate.ts` (T3) is pure and imports nothing from the app: `MAX_TITLE_LENGTH = 120`,
  `validateTitle(raw: unknown): string | null` (trimmed title, or `null` when the input is not a string, is
  blank, or is longer than `MAX_TITLE_LENGTH`), `isValidTitle(raw: unknown): boolean`,
  `validateDone(raw: unknown): boolean` (booleans pass through, anything else is `false`).
- `components/TodoList.tsx` (T4) is a presentational client component — it never imports the store or the
  validator, it only takes props: `{ todos: Todo[]; onToggle?: (id: number) => void; emptyLabel?: string }`
  with a default `emptyLabel` of `"No todos yet"`. It renders a default-exported `TodoList`, shows the
  empty label in a `data-testid="todo-empty"` paragraph when the list is empty, otherwise a
  `data-testid="todo-list"` `<ul>` with one `<li>` per todo, each holding a checkbox (`aria-label` = the
  title) that calls `onToggle?.(todo.id)`. The `Todo` type is imported with `import type` from
  `lib/todos-store` (type-only: the component never calls the store).
- `app/page.tsx` (T5) is a server component: it calls `listTodos()`, keeps rendering `formatCount(...)` and
  the `<h1>Todos</h1>` heading, renders `<TodoList ... />`, and uses `isValidTitle` for the hint line. It
  imports `TodoList`, `lib/todos-store` and `lib/validate`.
- Toolchain: React 19, Next 16, TypeScript 5.9, vitest 5, jsdom, `@testing-library/react` all come from the
  repo root `node_modules` — the work dir's `package.json` stays dependency-free and is never `npm install`ed.
  No new dependencies, no `next.config` changes, no client-side data fetching library.
- The work dir is `harness-suite/work/<slug>/`; every acceptance command runs `cd {work} && ...` (`{work}`
  is substituted by the runner). `app/layout.tsx`, `lib/format.ts`, `tsconfig.json`, `vitest.config.ts`,
  `next.config.mjs` and `package.json` are never edited.

## Tasks (T1-T4 fully independent, `deps` empty; T5 joins all four)
| id | title | deps | files |
|----|-------|------|-------|
| T1 | `/api/todos` route handler (GET + POST) | - | {work}/app/api/todos/route.ts |
| T2 | create the in-memory `lib/todos-store.ts` | - | {work}/lib/todos-store.ts |
| T3 | shared title validation in `lib/validate.ts` | - | {work}/lib/validate.ts |
| T4 | presentational `components/TodoList.tsx` | - | {work}/components/TodoList.tsx |
| T5 | wire the page to the store, validator and component | T1, T2, T3, T4 | {work}/app/page.tsx |

## T1
GOAL: Add the App Router route module `app/api/todos/route.ts` that serves the todo list and creates todos.

CONTEXT: The seed has no `app/api/` directory and no store module. Import `listTodos()` and `addTodo()`
statically from `lib/todos-store` using the names this plan fixes (T2 writes that file) — do not reach for
a dynamic import and do not edit the store file (T2 owns it).

FILES (create; touch nothing else):
- `{work}/app/api/todos/route.ts` (create)

REQUIREMENTS:
- `export async function GET(): Promise<Response>` — `200` with the JSON array `listTodos()`.
- `export async function POST(request: Request): Promise<Response>` — parses `await request.json()`; on
  success returns `201` with the todo from `addTodo(title)`.
- `title` handling: the payload's `title` must be a `string`; the value is trimmed and must be 1..120
  characters. Anything else (broken JSON, missing `title`, non-string `title`, blank, over-long) answers
  `400` with a JSON body carrying an `error` string. `await request.json()` throwing is a `400`, never a 500.
- Imports only from `lib/todos-store`. No validation import (T3's file), no `NextRequest`, no framework
  magic: plain `Request`/`Response` so the handlers are callable from a test.

CONSTRAINTS: match the seed style (typed exports, no docstring noise); touch only the listed file; no new
dependencies; no `next/server` import; never run git commands that change state.

ACCEPTANCE (run from the project root; must print `T1 OK` and exit 0):
`cd {work} && npx --no-install tsc --noEmit --incremental && node -e "const fs=require('fs');const p='app/api/todos/route.ts';if(!fs.existsSync(p))process.exit(1);const s=fs.readFileSync(p,'utf8');if(!/export async function GET/.test(s))process.exit(1);if(!/export async function POST/.test(s))process.exit(1);console.log('T1 OK')"`

## T2
GOAL: Create `lib/todos-store.ts`, the in-memory todo store behind the route, behind the component's type and
behind the page.

CONTEXT: The seed has no store file. T1's route module, T4's type-only import and T5's page are written
against the contract fixed in Decisions — keep the exported names and signatures exactly as specified there.

FILES (create; touch nothing else):
- `{work}/lib/todos-store.ts` (create)

REQUIREMENTS:
- Declare `export interface Todo { id: number; title: string; done: boolean }` and the six exported function
  signatures exactly as listed below; no `throw` and no `notImplemented` helper.
- Module state: a `todos` array and a `nextId` counter starting at 1.
- `resetTodos()` empties the list and sets `nextId` back to 1.
- `listTodos()` returns shallow copies in creation order; `getTodo(id)` returns a copy or `null`;
  `addTodo(title)` appends `{ id, title, done: false }` with the title as given (no trimming) and returns a
  copy; `toggleTodo(id)` flips `done` and returns a copy or `null`; `removeTodo(id)` drops the todo and
  returns whether anything was removed.
- No persistence, no async, no `Date`/random ids, no imports at all.

CONSTRAINTS: match the seed style; touch only the listed file; the store must not import the route, the
validator or anything from React/Next; no new dependencies.

ACCEPTANCE (run from the project root; must print `T2 OK` and exit 0):
`cd {work} && npx --no-install tsc --noEmit --incremental && node -e "const fs=require('fs');const s=fs.readFileSync('lib/todos-store.ts','utf8');if(/not implemented/.test(s))process.exit(1);for(const n of ['resetTodos','listTodos','getTodo','addTodo','toggleTodo','removeTodo']){if(!s.includes('export function '+n))process.exit(1);}console.log('T2 OK')"`

## T3
GOAL: Add `lib/validate.ts`, the shared input validation used by the UI side of the app.

CONTEXT: The seed has no validation module and the route deliberately validates inline (T1), so this module
is imported by `components/TodoList.tsx` and `app/page.tsx` only. It must stay pure and dependency-free.

FILES (create; touch nothing else):
- `{work}/lib/validate.ts` (create)

REQUIREMENTS:
- `export const MAX_TITLE_LENGTH = 120`.
- `export function validateTitle(raw: unknown): string | null` — returns the trimmed title when `raw` is a
  string, is not blank and is at most `MAX_TITLE_LENGTH` characters; `null` otherwise (non-strings included).
- `export function isValidTitle(raw: unknown): boolean` — `validateTitle(raw) !== null`.
- `export function validateDone(raw: unknown): boolean` — booleans pass through, anything else is `false`.
- No imports, no state, no `throw`.

CONSTRAINTS: touch only the listed file; no new dependencies; the route must not be edited to use it.

ACCEPTANCE (run from the project root; must print `T3 OK` and exit 0):
`cd {work} && npx --no-install tsc --noEmit --incremental && node -e "const fs=require('fs');const p='lib/validate.ts';if(!fs.existsSync(p))process.exit(1);const s=fs.readFileSync(p,'utf8');if(/not implemented/.test(s))process.exit(1);if(!/export function validateTitle/.test(s))process.exit(1);if(!/export function isValidTitle/.test(s))process.exit(1);console.log('T3 OK')"`

## T4
GOAL: Add the presentational `components/TodoList.tsx` that renders todos and reports toggles.

CONTEXT: The seed has no `components/` directory. This task is independent of T2 and T3: the component
receives todos as props and takes the `Todo` type with a type-only import from `lib/todos-store` (T2's
file), so it never calls the store and never needs the validator.

FILES (create; touch nothing else):
- `{work}/components/TodoList.tsx` (create)

REQUIREMENTS:
- `"use client"` at the top, then `export interface TodoListProps` and a default-exported `TodoList`.
- Props: `todos: Todo[]`, `onToggle?: (id: number) => void`, `emptyLabel?: string` (default
  `"No todos yet"`).
- Empty list: render `<p data-testid="todo-empty">{emptyLabel}</p>` and nothing else.
- Non-empty list: render `<ul data-testid="todo-list">` with one `<li key={todo.id}>` per todo, in order,
  each containing a checkbox `<input type="checkbox" checked={todo.done} aria-label={todo.title}>` next to
  the title text; the checkbox's `onChange` calls `onToggle?.(todo.id)`.
- No store calls, no `fetch`, no validator import, no hooks beyond the event handler.

CONSTRAINTS: touch only the listed file; no new dependencies; JSX only through the `react-jsx` runtime
configured in `tsconfig.json` (no manual `React` import).

ACCEPTANCE (run from the project root; must print `T4 OK` and exit 0):
`cd {work} && npx --no-install tsc --noEmit --incremental && node -e "const fs=require('fs');const p='components/TodoList.tsx';if(!fs.existsSync(p))process.exit(1);const s=fs.readFileSync(p,'utf8');if(!/export default function TodoList/.test(s))process.exit(1);console.log('T4 OK')"`

## T5
GOAL: Wire the four leaves together in `app/page.tsx` so the app renders the todo board.

CONTEXT: T1 (route), T2 (store), T3 (validator) and T4 (component) have all landed. The seed's page renders
a heading and `formatCount(0)`; this task turns that into the real board.

FILES (create/overwrite; touch nothing else):
- `{work}/app/page.tsx` (modify)

REQUIREMENTS:
- A default-exported server component `Page` (no `"use client"`, no hooks) that calls `listTodos()` once
  and renders, in this order: `<main>`, `<h1>Todos</h1>`, the count line built with
  `formatCount(todos.length)`, `<TodoList todos={todos} ... />`, and a hint line that uses `isValidTitle`
  (e.g. "Type a title to add it" when a sample title is valid, otherwise "Titles are required").
- Pass a non-default `emptyLabel` to `TodoList` so the page does not depend on the component's default text.
- Import `TodoList` from `../components/TodoList`, `formatCount` from `../lib/format`, `listTodos` from
  `../lib/todos-store` and `isValidTitle` from `../lib/validate`.
- The route handlers are not wired here: no `fetch`, no client state, no form submission.

CONSTRAINTS: touch only `app/page.tsx`; the four leaf modules are read-only now; no new dependencies; keep
`formatCount` in use so `lib/format.ts` does not become dead code.

ACCEPTANCE (run from the project root; must print `T5 OK` and exit 0):
`cd {work} && npx --no-install tsc --noEmit --incremental && node -e "const fs=require('fs');const s=fs.readFileSync('app/page.tsx','utf8');if(!s.includes('TodoList'))process.exit(1);if(!s.includes('listTodos'))process.exit(1);if(!s.includes('isValidTitle'))process.exit(1);console.log('T5 OK')"`

## Later phases
None planned.
