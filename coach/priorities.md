# Priorities

Last reviewed: 2026-10-22. Order matters: work top-down.

## 0. Health (every day, before work)

Not exercising at all right now. Goal: move every day. Start with a 20–30 minute walk; once
that is a streak of 10 days, add something harder.

## 1. Daisolar: Kapso WhatsApp agent (late, highest priority)

Second income with his father-in-law and brother-in-law. The bot is overdue.

- Code: `~/c/daisolar/bot` (Kapso workflow `workflows/daisolar-bot`, functions `crm`,
  `gate-logic`). Workflow last edited 2026-10-08.
- Pending changes: `Proyectos/daisolar/to-do.md` in the vault (presupuesto → cotización, ask
  for preferred contact channel when asking for the CFE bill, "contáctame en 3 meses", 13 años
  de garantía, install SIM in Kapso, GTM dashboard prototype).
- Versioned in git since 2026-10-22 (no secrets tracked).
- Done: presupuesto → cotización, contact channel (2026-10-22), 13 años de garantía (deployed
  2026-10-23). Won't do: updating the presentation (he won't use it again).
- Next step: install the SIM in Kapso (needs the paid Kapso account, 25 USD/month; Armando
  paid it on 2026-10-29; setup in progress), then the GTM dashboard prototype.
- Pending (added 2026-10-25): **Bot envía cotizaciones reales basadas en costo de CFE.** Today
  the `generar_estimacion` tool only gives an "estimación ilustrativa" from the bill's kWh or
  amount.

## 2. LinkedIn: post daily (the job hunt strategy)

Applying to job posts hasn't worked. Strategy: post daily about what he has built, to stand out
as a product engineer and get recruiters' attention.

- Vault: `Areas/LinkedIn/` (AI essay draft lives there). `Projects to share.md` tracks one
  post per project featured on grillermo.com (15 queued; vvterm posted 2026-10-22).
- Published posts are backed up in `Areas/LinkedIn/Posts/`, one note per post named
  `YYYY-MM-DD <project>.md` with the exact published text and `date`, `project`, `url`
  frontmatter. Save it there once he publishes, and link it from `Projects to share.md`.
- Source material: his projects in `~/c/`. Candidates to check: the Daisolar WhatsApp agent
  (once shipped), comunidad-antesis (multi-country pricing, Argentina payments), readitsoon
  (+ MCP server, Obsidian plugin, companion), patatatube, git-sync, file_server, ipad-send,
  claude-sessions, my-machines-monitor, whatsapp-controller, spreadsheet-ocr.
- Published: PatataTube (2026-10-26), Narrate the web (2026-10-27), git-sync (2026-10-28).
- Next step: the next unticked project in `Projects to share.md`.

## 3. Comunidad Antesis: dLocal Go payments for Argentina

With his wife. Many possible buyers in Argentina, no local payment method.

- On the **macmini**: `~/c/comunidad-antesis-staging`, branch `feat/dlocal-argentina`.
- Done: design spec `docs/superpowers/specs/2026-10-20-dlocal-argentina-design.md`, plus
  recording the buyer's country on purchases. No dLocal payment code yet.
- Claude session for it on the macmini: `8ddbe2ff-4059-4252-b784-d1bac384555a`
  (last used 2026-10-22).
- Next step: implementation plan from the spec, then build it.
- Smaller items: `Proyectos/antesis/to-do.md`.
- Also: an **iOS app** for Comunidad Antesis, a possible quick win as another distribution
  channel. He started a Claude conversation about it (session not located yet; ask him which
  machine). Comes after dLocal unless he decides otherwise.

## 4. ListLab / YourList (59 Pines): stepped away 2026-10-26

On 2026-10-26 he told Ciaran (second in command) that he can't give the project enough time.
Ciaran offered a few weeks away and re-engaging later ("you've onboarded well & made a positive
impact"); he agreed. Jay replied on 2026-10-27: "extremely strong the first couple weeks,"
wants him as a permanent team member. His read (2026-10-29): Jay wants the free labor and
would rather he not join another company, so no asking Jay for a recommendation or outreach.

Why it isn't a backup plan (his words, 2026-10-27): pre-seed and pre-launch, so no money and no
customers. The "hire" was a 30-day unpaid trial: if they raise money and he does well, they hire
him. They aren't getting interest from customers or investors. His private reasons (no closed round, Facebook scraping against Meta's terms, placed
under someone he'd compete with for the role) stay private. Don't plan any ListLab work.

## 5. Ayuyo: publish the app (added 2026-10-25)

Android panic app: a long press sends a pre-set emergency SMS (optionally with location) to one
contact. Code in `~/c/ayuyo` (last commit: the "Ajustes" settings control); there's also a
`webpage/` folder.

- Next step: decide where and how to publish it (Play Store or a direct download), then
  list what's missing.
- Once it's out, it's a good LinkedIn post.

## Dated things from Reminders

- Día de muertos (Nov 1–2): alfeñique, veladoras, hojaldra, incienso, fotos de abuelos,
  papel picado.
- Write to Liz to renew the SAT certificate ("certificado de hacienda").
