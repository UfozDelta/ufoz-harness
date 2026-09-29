# Camp CRM (Next.js 16 App Router) — whole spec, one phase

## Goal
Public intake form + staff dashboard over a `node:sqlite` clients table, with JSON API,
shared pricing, server-truth validation, and designed UI. No new dependencies.
`npm run build` must pass with zero type errors.

## Decisions (fixed — executor never re-decides)

- **No package installs.** No test framework: tests are `node:test` + `node:assert/strict`
  files under `tests/`, run with `node --test <file>` (Node 24 strips TS types natively).
- **Module resolution.** Every internal import uses a RELATIVE path with an explicit `.ts`
  extension (`../../lib/pricing.ts`), in `lib/`, in `app/`, and in `tests/`. The `@/*` alias
  is NOT used anywhere, because Node's test runner cannot resolve it. `tsconfig.json` gets
  `"allowImportingTsExtensions": true` added in T1 (`noEmit` is already true) — nothing else
  in tsconfig changes.
- **Layering.** All logic lives in `lib/`; `app/api/**/route.ts` files are thin wrappers that
  import a handler from `lib/handlers.ts`, call it, and export `const dynamic = "force-dynamic"`.
  Tests exercise `lib/`, plus source-level assertions for React files (no renderer available).
- **Pricing** (`lib/pricing.ts`, whole-dollar integers):
  `total(kids) = 350 + 150 * (kids - 1) + 50`. 1→400, 2→550, 3→700.
  `quote(kids)` returns `{ kids, firstKid: 350, additionalKids: 150 * (kids - 1), activityFee: 50, total }`.
  `formatUSD(n)` returns `"$1,100"` (US grouping, no cents).
- **Validation** (`lib/validate.ts`, server is source of truth). Field order: name, email, dob, kids.
  First bad field wins. Non-object body → 400 with any field.
  - `name`: string, trimmed, length 1–100.
  - `email`: string, trimmed, matches `/^[^\s@]+@[^\s@]+\.[^\s@]+$/`, stored lowercase.
  - `dob`: `YYYY-MM-DD`, real calendar date (`2023-02-30` invalid), not in the future,
    not before `1900-01-01`.
  - `kids`: JSON integer 1–10 (`"2"`, `0`, `11`, `1.5` all invalid).
- **DB** (`lib/db.ts`): `node:sqlite` `DatabaseSync`, path from `process.env.CRM_DB_PATH`,
  default `data/crm.db`; read the env on every `getDb()` call and cache one handle per resolved
  path; `mkdirSync(dirname, { recursive: true })` and `CREATE TABLE IF NOT EXISTS` on first use.
  Table `clients(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
  dob TEXT NOT NULL, kids INTEGER NOT NULL, total INTEGER NOT NULL, createdAt TEXT NOT NULL)`.
  `createdAt` is `new Date().toISOString()`. Email uniqueness is case-insensitive because email is
  stored lowercase; duplicate insert → the handler returns 409.
  Ordering: `ORDER BY createdAt DESC, id DESC`. `?q=` filters `LOWER(name) LIKE ? OR LOWER(email) LIKE ?`.
- **API shapes** exactly as in the spec: `POST /api/clients` 201 client; `GET /api/clients` 200
  `{clients, count, revenue}` (count/revenue describe the FILTERED list); `GET /api/clients/{id}`
  200 client or 404 `{error}` (non-positive-integer id → 404 too); `GET /api/quote?kids=N` 200 quote
  or 400 `{error, field: "kids"}`. Errors: 400 `{error, field}`, 409 `{error, field: "email"}`.
  Handlers return plain web `Response` via `Response.json(body, { status })` — `next/server` is
  never imported, so the handlers stay loadable in `node --test`.
- **Pages:** `/` dashboard (server component, `force-dynamic`, reads `lib/db.ts` directly, not fetch),
  `/intake` (server page + `"use client"` form component). Styling: `app/globals.css` only,
  imported once from `app/layout.tsx`. Design per `.claude/skills/emil-design-eng/SKILL.md` and
  `.claude/skills/apple-design/SKILL.md`, both read before T6.
- **Tests** put their DB in `os.tmpdir()` via `process.env.CRM_DB_PATH`, set before calling `getDb()`,
  with a unique filename per test file, so no two tests share state and the repo stays clean.

## Verified
- Node `v24.16.0`, npm `11.13.0` — `node -v && npm -v`.
- `node:sqlite` `DatabaseSync` works: `node -e "const{DatabaseSync}=require('node:sqlite');..."` → `sqlite ok`.
- `node --test tests/a.test.ts` runs a TS test importing `../lib.ts` and passes (native type stripping).
- Node CANNOT resolve `./lib` or `./lib.js` to a `.ts` file: both throw `ERR_MODULE_NOT_FOUND`
  → explicit `.ts` extensions are mandatory.
- `tsc --noEmit` accepts `import { add } from "./lib.ts"` when `allowImportingTsExtensions: true`
  (run with the project's `node_modules/.bin/tsc`).
- Project starting point is exactly as the spec says: `package.json` (next 16.3.6 / react 19.3.0),
  `tsconfig.json` with `@/*`, `next.config.ts`, `app/layout.tsx`, `app/page.tsx` placeholder.
  `.gitignore` already ignores `node_modules/`, `.next/`, `data/`, `*.db`, so builds and DB files
  never count as out-of-scope edits (`cat .gitignore`).
- `run_acceptance` uses `shell=True`, cwd = project root, 300 s timeout (`sed -n 200,270 run_plan.py`).

## Unverified
- That Next 16 (Turbopack) resolves relative imports ending in `.ts` inside `app/`. Webpack's
  config lists `'.ts'`, and an explicit existing path normally resolves, but this is only proven
  when T5's `npx tsc --noEmit` and T6's `npm run build` run. If it fails, the fix is a decision for
  the main session (options: keep `.ts` in `lib/` only and drop route-level tests, or add a
  `package.json` `imports` map).
- That `npm run build` + a test run fit inside the 300 s acceptance timeout on this machine.
- Whether `node:sqlite` writes work under the Next build's server runtime here (spec asserts it does).

## T1 Pricing and formatting
FILES: `lib/pricing.ts`, `tests/pricing.test.ts`, `tsconfig.json`
MUST:
- `tsconfig.json` gains `"allowImportingTsExtensions": true` in `compilerOptions`; no other key changes.
- `lib/pricing.ts` exports `total(kids: number): number`, `quote(kids: number)`, `formatUSD(cents: number): string`
  (whole dollars, e.g. `formatUSD(1100) === "$1,100"`), and `parseKids(raw: unknown): number | null`
  returning `null` for anything that is not an integer 1–10 (`"2"`, `0`, `11`, `1.5`, `null`, `undefined`).
- `total` is `350 + 150 * (kids - 1) + 50`; tests cover 1→400, 2→550, 3→700, 10→1750.
- `quote(2)` deep-equals `{ kids: 2, firstKid: 350, additionalKids: 150, activityFee: 50, total: 550 }`.
- No imports from anywhere else in the repo.
TEST: `node --test tests/pricing.test.ts`

## T2 Client input validation
FILES: `lib/validate.ts`, `tests/validate.test.ts`
MUST:
- Exports `validateClient(body: unknown)` returning `{ ok: true, value: { name, email, dob, kids } }`
  or `{ ok: false, error: string, field: "name" | "email" | "dob" | "kids" }`.
- Imports `parseKids` from `./pricing.ts` (relative, `.ts`) instead of re-implementing it.
- Field order is name → email → dob → kids; a body that is `null`, an array, a string or a number
  is invalid with some field; missing field is invalid for that field.
- `name` trimmed 1–100 chars; `email` trimmed, regex `^[^\s@]+@[^\s@]+\.[^\s@]+$`, returned lowercase.
- `dob` is `YYYY-MM-DD` and a real date: tests must cover `2023-02-30` invalid, `2024-02-29` valid,
  a future date invalid, `1899-12-31` invalid, `1900-01-01` valid.
TEST: `node --test tests/validate.test.ts && node --test tests/pricing.test.ts`

## T3 SQLite client store
FILES: `lib/db.ts`, `tests/db.test.ts`
MUST:
- `getDb()` reads `process.env.CRM_DB_PATH` on every call (default `data/crm.db`), creates the parent
  folder and the `clients` table if missing, and caches one `DatabaseSync` per resolved path.
- `insertClient({name, email, dob, kids, total})` returns the full stored client
  `{id, name, email, dob, kids, total, createdAt}` with `id` and `kids` as numbers;
  a duplicate email throws (test asserts it throws).
- `listClients(q?: string)` returns newest first (`createdAt DESC, id DESC`); with `q` it filters by
  case-insensitive substring of name OR email; a test inserts rows with mixed case and asserts both.
- `getClient(id: number)` returns the client or `undefined`.
- Tests set `process.env.CRM_DB_PATH` to a unique file under `os.tmpdir()` before the first `getDb()`
  call and never write inside the repo.
TEST: `node --test tests/db.test.ts && node --test tests/pricing.test.ts`

## T4 API handler functions
FILES: `lib/handlers.ts`, `tests/handlers.test.ts`
MUST:
- Exports `createClient(req: Request)`, `listClients(req: Request)`, `getClientById(idParam: string)`,
  `getQuote(req: Request)`, each returning a `Promise<Response>` / `Response` built with
  `Response.json(...)`; `next/server` is never imported.
- `createClient`: invalid JSON body or non-object → 400 `{error, field}`; validation failure → 400
  `{error, field}` for the first bad field; duplicate email → 409 `{error, field: "email"}`;
  success → 201 with the stored client including `total` from `total(kids)` and ISO `createdAt`.
- `listClients`: 200 `{clients, count, revenue}` where `revenue` is the sum of `total` over the
  filtered list and `count` its length; honours `?q=`.
- `getClientById`: 404 `{error}` for a missing id and for `"0"`, `"-1"`, `"abc"`, `"1.5"`; else 200 client.
- `getQuote`: `?kids=2` → 200 quote object; missing/`"0"`/`"11"`/`"1.5"`/`"abc"` → 400 `{error, field: "kids"}`.
- Tests point `CRM_DB_PATH` at a unique `os.tmpdir()` file and assert status codes and parsed JSON bodies.
TEST: `node --test tests/handlers.test.ts && node --test tests/db.test.ts tests/validate.test.ts tests/pricing.test.ts`

## T5 Route handler wiring
FILES: `app/api/clients/route.ts`, `app/api/clients/[id]/route.ts`, `app/api/quote/route.ts`, `tests/routes.test.ts`
MUST:
- Each route file exports `const dynamic = "force-dynamic"` and delegates to `lib/handlers.ts` via a
  relative `.ts` import; no validation, pricing or SQL logic is duplicated in `app/`.
- `app/api/clients/route.ts` exports `GET` and `POST`; `app/api/clients/[id]/route.ts` exports `GET`
  taking `(req, ctx)` where `ctx.params` is a Promise resolving to `{ id: string }` (Next 16 async params)
  and passes `id` to `getClientById`; `app/api/quote/route.ts` exports `GET`.
- `tests/routes.test.ts` imports each route module directly and drives it end to end against a
  tmpdir DB: POST a valid client → 201, GET the collection → 200 with count 1, GET `/api/clients/[id]`
  through the exported `GET` with `{ params: Promise.resolve({ id }) }` → 200, and with id `"999"` → 404,
  quote route with `?kids=3` → 200 `total: 700`.
- Each route module exports `dynamic === "force-dynamic"` (asserted in the test).
TEST: `node --test tests/routes.test.ts && npx tsc --noEmit`

## T6 Global design styles
FILES: `app/globals.css`, `app/layout.tsx`, `tests/styles.test.ts`
MUST:
- Read `.claude/skills/emil-design-eng/SKILL.md` and `.claude/skills/apple-design/SKILL.md` first and
  apply them: CSS custom properties for a restrained palette, type scale and spacing scale, a system
  font stack, sensible line-height and measure.
- `app/globals.css` contains a `:focus-visible` rule with a visible outline, an
  `@media (prefers-reduced-motion: reduce)` block that removes transitions/animations, and at least one
  `@media (max-width: 420px)` rule; the layout works down to 375px wide (no fixed widths above 375px).
- `app/layout.tsx` imports `./globals.css` (this is the only place it is imported), keeps
  `export const metadata`, and wraps children in a centred page container.
- `tests/styles.test.ts` reads both files as text and asserts: `globals.css` includes `:focus-visible`,
  `prefers-reduced-motion`, `--` custom properties and a `max-width: 420px` media query;
  `layout.tsx` includes `./globals.css` exactly once.
TEST: `node --test tests/styles.test.ts && npm run build`

## T7 Staff dashboard page
FILES: `app/page.tsx`, `tests/dashboard.test.ts`
MUST:
- Server component, `export const dynamic = "force-dynamic"`, reads `listClients(q)` from `lib/db.ts`
  directly (no `fetch`); `q` comes from `searchParams` (awaited — Next 16 async searchParams).
- Renders a summary with the client count and the revenue via `formatUSD` from `lib/pricing.ts`
  inside an element with `data-testid="revenue"`; revenue and count describe the filtered list.
- Renders a `<table data-testid="clients-table">` with one `<tr data-testid="client-row">` per client
  showing name, email, dob, kids and total; an empty state message when the list is empty; a GET
  `<form>` with an `<input name="q">` and a real `<label>`; a link to `/intake`.
- `tests/dashboard.test.ts` reads `app/page.tsx` as text and asserts the presence of
  `force-dynamic`, `data-testid="revenue"`, `data-testid="clients-table"`, `data-testid="client-row"`,
  `name="q"`, `/intake`, `formatUSD` and `listClients`, and that `fetch(` does not appear.
TEST: `node --test tests/dashboard.test.ts && npm run build`

## T8 Parent intake form
FILES: `app/intake/page.tsx`, `app/intake/IntakeForm.tsx`, `tests/intake.test.ts`
MUST:
- `app/intake/page.tsx` is a server component rendering `<IntakeForm />` plus a heading and a link
  back to `/`; `app/intake/IntakeForm.tsx` starts with `"use client"`.
- Inputs with real `<label htmlFor>` pairs: `name="name"`, `name="email"`, `name="dob"` (`type="date"`),
  `name="kids"` (`type="number"`, `min={1}`, `max={10}`, default 1).
- Live breakdown (first kid, additional kids, activity fee, total) computed with `quote()` from
  `lib/pricing.ts` and re-rendered as `kids` changes — no duplicate local pricing arithmetic.
- Submits once per click with `fetch("/api/clients", { method: "POST" })`: the submit button is
  `disabled` while a request is in flight, a non-2xx response shows the server's `error` next to the
  field named by `field`, and success replaces the form with a confirmation showing the total and a
  link to `/`.
- `tests/intake.test.ts` reads both files as text and asserts: `"use client"` in `IntakeForm.tsx` only,
  each `name="…"` attribute, `type="date"`, `type="number"`, `min={1}`/`max={10}`, exactly one
  `fetch(` call, `disabled`, `quote(` usage, and an import of `lib/pricing.ts`.
TEST: `node --test tests/intake.test.ts && npm run build`
