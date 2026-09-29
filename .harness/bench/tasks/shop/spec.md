# Spec: Nimbus Goods (Next.js dropshipping shop)

## Goal
A small dropshipping storefront, "Nimbus Goods": a landing page, a fixed product catalog, a mock
payment gateway, a contact form, a server-side cart, and a no-auth admin sales board. Built in 6
sequential stages (see `stages/s1.md` .. `s6.md`). Each stage spec states what earlier stages
already built (by contract, not by file) and must keep working.

## Starting point (already exists — do not re-create)
A bare Next.js 16.3.6 App Router project in TypeScript: `package.json` (next 16.3.6, react 19.3.0,
react-dom 19.3.0, typescript, @types/*), `tsconfig.json` (`@/*` path alias to the root), `next.config.ts`,
`app/layout.tsx`, `app/page.tsx` (placeholder), `.gitignore`. `node_modules` is installed. Node 24.
See `SEED.md` — reuse `.harness/bench/tasks/crm/seed`, do not copy it.

## Decisions (fixed — do not re-decide; every stage inherits these)
- **No new dependencies.** No ORM, no UI kit, no Tailwind, no test/payment SDK packages. Styling is
  plain CSS (`app/globals.css` and/or CSS modules). Database is Node's built-in `node:sqlite`
  (`DatabaseSync`).
- **Database:** file path from env `SHOP_DB_PATH`, default `data/shop.db`. Create the parent folder
  and all tables on first use (lazy init in a shared `lib/db.ts`). Every route and page that touches
  the DB exports `export const dynamic = "force-dynamic"`.
- **Money** is integer cents everywhere in JSON (`priceCents`, `totalCents`, etc). Never floats,
  never dollar strings, in any API response. Pages may format cents as dollars for display only
  (e.g. `$29.99`), using `(cents / 100).toFixed(2)`, unless a stage specifies another format.
- **Product catalog** (fixed, seeded into the DB on first use if the products table is empty —
  defined once here, used by every later stage):

  | id | slug | name | priceCents | stock | description |
  |---|---|---|---|---|---|
  | 1 | wireless-earbuds | Wireless Earbuds | 2999 | 50 | Bluetooth 5.3 earbuds with charging case. |
  | 2 | phone-stand | Adjustable Phone Stand | 1499 | 100 | Foldable aluminum stand for desk or nightstand. |
  | 3 | led-strip-lights | LED Strip Lights | 1999 | 75 | 16ft RGB strip with remote control. |
  | 4 | insulated-tumbler | Insulated Tumbler | 2499 | 60 | 20oz stainless steel, keeps drinks cold 24 hours. |
  | 5 | yoga-mat | Yoga Mat | 3499 | 40 | Non-slip 6mm mat with carry strap. |
  | 6 | desk-organizer | Bamboo Desk Organizer | 1799 | 30 | Multi-compartment organizer for pens and cables. |

  Seed in this exact id order. `stock` is a live, mutable column (decremented by approved payments);
  the other columns never change after seeding.
- **Error shape** for every API validation failure: HTTP 400 (unless a stage says otherwise) with
  body `{"error": "<human message>", "field": "<name>"}` naming the FIRST invalid field, checked in
  the order each stage's API section lists. A request body that is not a JSON object → 400 with any
  `field`. Missing field is invalid for that field.
- **Design:** before any UI work, read `.claude/skills/emil-design-eng/SKILL.md` and
  `.claude/skills/apple-design/SKILL.md` and apply them: considered typography and spacing,
  restrained motion that respects `prefers-reduced-motion`, visible focus states, responsive down to
  375px wide, real `<label>`s. It should look like a product, not a scaffold. Same look and feel
  (brand name "Nimbus Goods", one consistent color/typography choice) across all 6 stages.
- `npm run build` must succeed with zero type errors. Nothing may require network access at runtime
  (the payment gateway in stage 3 is fully mocked, no outbound calls).
- No authentication anywhere, including `/admin`. No user accounts, no email sending, no real
  payment processor.

## Stages
1. `stages/s1.md` — landing page
2. `stages/s2.md` — product catalog
3. `stages/s3.md` — mock payment gateway (direct checkout, no cart yet)
4. `stages/s4.md` — contact form
5. `stages/s5.md` — server-side cart (checkout reuses stage 3's payment logic)
6. `stages/s6.md` — admin sales board
