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
- Next step: work through the to-do in order, starting with: when asking for the CFE bill, ask the prospect how they want to be contacted
  (WhatsApp or a call; no email). Bot deployed 2026-10-22; update the presentation, then "13 años de garantía".

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
- Next step: post #2, the next unticked project in `Projects to share.md`.

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

## 4. ListLab / YourList (59 Pines): decide by end of October

Deal: unpaid for a month (started ~2026-10-01), hired if they raise a round and he did well.
He's disappointed: unclear direction, engineers building a task management tool instead of the
product, and his assigned work is scraping Facebook (against its terms, fragile, painful).

What Slack showed on 2026-10-22:
- GTM weekly (Oct 20): the Facebook VA automation got **1 lead from 200+ attempts** because of
  account restrictions; US VAs refuse to install the extension or use personal Facebook
  accounts. They are pivoting to Facebook Ads.
- Engineering weekly (Oct 19): 2 items shipped.
- Investor update (Oct 16): one investor wire came in; still filling the funnel. No sign of a
  closed round.
- Jay publicly frustrated with the team on Oct 15.

Coach's take: the month is almost up and the funding that the hire depends on isn't there.
Don't sink more unpaid time into the scraping work. Before Nov 1, ask Jay directly: when do they
expect to close the round, and what would his role be. Until then, cap ListLab at a few hours a
week, below priorities 1–3. His call.

## Dated things from Reminders

- Día de muertos (Nov 1–2): alfeñique, veladoras, hojaldra, incienso, fotos de abuelos,
  papel picado.
- Write to Liz to renew the SAT certificate ("certificado de hacienda").
