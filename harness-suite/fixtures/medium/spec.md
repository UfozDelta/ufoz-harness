# Spec (medium: minimal Next.js App Router todo app)

Seed: App Router shell (`app/layout.tsx`, `app/page.tsx`, `lib/format.ts`), strict `tsconfig.json`,
`next-env.d.ts`, `vitest.config.ts` (jsdom + `@vitejs/plugin-react`) and a dependency-free `package.json`.
There is no `lib/todos-store.ts` in the seed: the store is created from scratch by T2 against a contract
this plan fixes up front.
T1: `app/api/todos/route.ts` with `GET` (200, the store's list) and `POST` (201, created todo; 400 with an
`error` string for broken JSON, missing/non-string/blank/over-long `title`), importing only the store.
T2: create `lib/todos-store.ts` — `Todo {id,title,done}` plus `resetTodos` (ids restart at 1), `listTodos` (copies, in
order), `getTodo`, `addTodo` (title as given, not done), `toggleTodo`, `removeTodo`; no imports.
T3: `lib/validate.ts` — `MAX_TITLE_LENGTH = 120`, `validateTitle` (trimmed title or `null`), `isValidTitle`,
`validateDone`; pure, no imports.
T4: `components/TodoList.tsx` — `"use client"`, default-exported presentational `TodoList` taking
`{todos, onToggle?, emptyLabel?}`, rendering the empty label or a `<ul>` of checkbox rows, importing the
`Todo` type only.
T5 (join, deps on all four): `app/page.tsx` calls `listTodos()`, renders the heading, `formatCount(...)`,
`<TodoList>` with a non-default empty label and an `isValidTitle` hint line.
T1-T4 have empty `deps` and disjoint files; the layout, `lib/format.ts`, the configs and `package.json` are
never edited, and no new dependencies are allowed.
