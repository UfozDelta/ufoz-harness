# Spec: Camp CRM (Next.js)

## Goal
A small CRM for a kids' summer camp: a public **intake form** where a parent signs up their kids,
and a staff **dashboard** listing every client with totals and search. Clients live in SQLite.

## Starting point (already exists — do not re-create)
A bare Next.js 16.3.6 App Router project in TypeScript: `package.json` (next 16.3.6, react 19.3.0,
react-dom 19.3.0, typescript, @types/*), `tsconfig.json` (`@/*` path alias to the root), `next.config.ts`,
`app/layout.tsx`, `app/page.tsx` (placeholder), `.gitignore`. `node_modules` is installed. Node 24.

## Decisions (fixed — do not re-decide)
- **No new dependencies.** No ORM, no UI kit, no Tailwind, no test framework packages. Styling is plain CSS
  (`app/globals.css` and/or CSS modules). Database is Node's built-in `node:sqlite` (`DatabaseSync`), which is
  proven to work inside route handlers after `next build`.
- **Database:** file path from env `CRM_DB_PATH`, default `data/crm.db`. Create the parent folder and the
  table on first use. One table of clients. Every route and page that touches the DB exports
  `export const dynamic = "force-dynamic"`.
- **Pricing** (one shared function in `lib/`, used by the API and the form preview):
  first kid $350, each additional kid $150, plus a flat $50 activity fee per signup no matter how many kids.
  `total = 350 + 150 * (kids - 1) + 50`. So 1 kid = 400, 2 = 550, 3 = 700. Whole dollars, integers.
- **Validation** (server is the source of truth; the form mirrors it):
  - `name`: string, trimmed, 1–100 chars.
  - `email`: string, trimmed, matches `^[^\s@]+@[^\s@]+\.[^\s@]+$`, stored lowercase. Unique, case-insensitive.
  - `dob`: string `YYYY-MM-DD`, a real calendar date (2023-02-30 is invalid), not in the future, not before 1900-01-01.
  - `kids`: a JSON integer 1–10 (the string `"2"`, `0`, `11`, `1.5` are all invalid).
  - Invalid → HTTP 400 with `{"error": "<human message>", "field": "<name|email|dob|kids>"}` naming the first bad field
    in the order name, email, dob, kids. A missing field is invalid for that field. Body that is not a JSON object → 400 with any `field`.
  - Duplicate email → HTTP 409 with `{"error": "...", "field": "email"}`.
- **API** (JSON everywhere):
  - `POST /api/clients` → 201 with the client: `{"id": int, "name", "email", "dob", "kids": int, "total": int, "createdAt": ISO-8601 string}`.
  - `GET /api/clients` → 200 `{"clients": [client...], "count": int, "revenue": int}`, newest first (ties broken by higher id first).
    Optional `?q=` filters by case-insensitive substring of name OR email; `count` and `revenue` describe the filtered list.
  - `GET /api/clients/{id}` → 200 client, or 404 `{"error": "..."}` when missing or `id` is not a positive integer.
  - `GET /api/quote?kids=N` → 200 `{"kids": N, "firstKid": 350, "additionalKids": 150*(N-1), "activityFee": 50, "total": ...}`;
    invalid `kids` (same rule as above; the query string must be an integer 1–10) → 400 `{"error": "...", "field": "kids"}`.
- **Pages:**
  - `/` — staff dashboard, server-rendered from the DB. Summary with client count and revenue, the revenue shown as
    US dollars with grouping (`$1,100`) inside an element with `data-testid="revenue"`. A table with
    `data-testid="clients-table"` and one `<tr data-testid="client-row">` per client showing name, email, date of birth,
    kids, and total. A search box (GET form, `name="q"`) that filters server-side via `?q=`. Empty state when no clients.
    A clear link to `/intake`.
  - `/intake` — parent-facing form with labelled inputs `name="name"`, `name="email"`, `name="dob"` (`type="date"`),
    `name="kids"` (`type="number"`, min 1, max 10). A live price breakdown that updates as `kids` changes (first kid,
    additional kids, activity fee, total) using the shared pricing function. Submits with `fetch` to `POST /api/clients`,
    shows the server's field error next to that field, disables the button while submitting, and on success shows a
    confirmation with the total and a link to the dashboard.
- **Design:** before any UI work, read `.claude/skills/emil-design-eng/SKILL.md` and `.claude/skills/apple-design/SKILL.md`
  and apply them: considered typography and spacing, restrained motion that respects `prefers-reduced-motion`, visible
  focus states, responsive down to 375px wide, real `<label>`s. It should look like a product, not a scaffold.
- `npm run build` must succeed with zero type errors. Nothing may require network access at runtime.
- No auth, no edit/delete of clients, no payments, no email sending.
