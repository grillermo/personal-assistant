---
name: start-day
description: Use when Guillermo invokes /start-day, says good morning, "start my day", "plan my day", or asks for today's page, tasks or a motivational quote to begin the day.
---

# /start-day: the morning page

Builds one HTML page for today: quotes, his one next action, habits, at most three goals,
dated things coming up, his scoreboard and recent wins. He opens it on any device and ticks
things off (ticks are saved in that browser). The coaching rules in `CLAUDE.md` still apply;
this skill is the morning routine's output.

All paths are relative to the repo root (`~/c/personal-assistant`).

## 1. Gather (run in parallel)

- `coach/vision.md`, `coach/priorities.md`, `coach/wins.md`, `coach/to-sell.md`,
  last row of `coach/scoreboard.md`
- The last 3 files in `coach/log/` (yesterday's unfinished goals, mood, used quotes)
- `bin/reminders.sh` (open reminders; anything with a date in the next 10 days, or a seasonal
  list like "dia de muertos" close to its date, goes in "Coming up")
- `bin/social-time.sh` (last 24 hours)

## 2. Decide the day

- **Habits**, always these four, in this order:
  1. SelfControl block on (x.com, youtube.com, linkedin.com); post to LinkedIn before it starts
  2. Move: 20–30 minute walk (or more, if the log shows a streak)
  3. List one item for sale (name the next one from `coach/to-sell.md`, or "pick one thing")
  4. Publish today's LinkedIn post (name the project it's about)
- **Goals**: at most 3, taken from the next steps in `priorities.md`, top-down. Carry over
  yesterday's unfinished goal first. Each goal is one concrete, finishable thing, with a
  `detail` saying where to start (file, machine, command), not "work on X".
- **Next action**: the first physical step of the day, usually "Start SelfControl, then walk".
- **Quotes**: 2–3 real quotes with their real author, about persistence, shipping, or building
  an audience; pick ones that fit his week (low energy, job hunt, distribution). Only quotes you
  are confident are real and correctly attributed; if unsure, choose a different one. Don't
  repeat any quote listed in the last 14 days of logs.
- **Stats** (3–4): social media yesterday, job-hunt minutes yesterday, current exercise streak,
  posts this week. Use "?" for unknowns; never invent numbers.
- **Recent wins**: last 3–5 from `wins.md`.
- **Vision**: one sentence from `vision.md`.
- **Greeting**: short and specific to today (a weekday, a deadline, yesterday's win). No guilt.

## 3. Render

Write the JSON to `coach/days/YYYY-MM-DD.json`, then render:

```bash
python3 -I .claude/skills/start-day/render.py coach/days/2026-10-22.json coach/days/2026-10-22.html
```

Shape (the renderer rejects missing fields and more than 3 goals):

```json
{
  "date": "2026-10-22", "dateLabel": "Thursday, October 22",
  "greeting": "…", "nextAction": "…",
  "quotes": [{"text": "…", "author": "…"}],
  "habits": [{"title": "…", "detail": "…"}],
  "goals": [{"title": "…", "detail": "…"}],
  "comingUp": ["…"], "stats": [{"label": "…", "value": "…"}],
  "recentWins": ["…"], "vision": "…"
}
```

## 4. Deliver

1. `open coach/days/YYYY-MM-DD.html` (local browser).
2. Upload with the `file_server` MCP `upload_file` tool, absolute path, **no `name`**; confirm
   with `curl -sI <url>` (200, text/html). Not logged in: `file_server_login`, ask him for the
   Slack #otp code, `file_server_verify`, retry.
3. Send the link:
   `~/c/agents-configs/bin/ntfy_machines.sh "Start your day" "<next action> <url>" default "<url>"`
4. Create or update `coach/log/YYYY-MM-DD.md` with the habits as checkboxes, the goals, the
   social media number, and a `Quotes:` line listing the authors used.
5. Commit `coach/` (the page, its JSON and the log).

## 5. Reply

Two or three lines: the greeting, the next action, the link. The page is the plan; don't
repeat it in chat.

## Common mistakes

- More than 3 goals, or vague ones ("work on Daisolar"). Shrink and make them concrete.
- Made-up or misattributed quotes. Pick a well-known one instead.
- Inventing stats when a log is missing. Write "?".
- Skipping the habits because he's in a hurry. They're the point.
