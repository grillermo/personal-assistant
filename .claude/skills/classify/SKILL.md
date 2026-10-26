---
name: classify
description: Empty the FSNotes scratch note into the Obsidian vault (PARA). Proposes where each item goes, waits for approval, then files it. Run only when the user types /classify.
disable-model-invocation: true
---

# /classify: empty scratch into the vault

The user throws ideas, to-dos, snippets and random text into one FSNotes note. This skill sorts
that note into their Obsidian vault and leaves scratch with only what still needs a human.

## Paths

```bash
SCRATCH=~/"Library/Mobile Documents/iCloud~com~grillermo~fsnotes/Documents/scratch.markdown"
VAULT=~/"google drive personal/documentos/notas"
BACKUPS=~/.local/share/classify-scratch
```

- `ls` is aliased to eza here; use `command ls`.
- `cd` into the vault prints a git status (a shell hook). That's noise; ignore it.
- Keep backups in `$BACKUPS`, never in this repo or `/tmp`. git-sync commits the repo, and scratch holds secrets.

## Steps

### 1. Back up and read

```bash
mkdir -p ~/.local/share/classify-scratch
cp ~/"Library/Mobile Documents/iCloud~com~grillermo~fsnotes/Documents/scratch.markdown" ~/.local/share/classify-scratch/scratch-$(date +%Y-%m-%d-%H%M%S).markdown
```

Record `md5 -q` of scratch, then read the backup with `cat -n`. Line numbers matter in step 4.

### 2. Survey the vault

The vault uses PARA with Spanish names:

| Folder | Holds |
|---|---|
| `Proyectos/<name>` | Things with an end (antesis, daisolar, linkedin, readitsoon, Personal server, bank-parser, 2025 job hunt notes…) |
| `Areas/<name>` | Ongoing parts of life (AI, AI/Prompts, finanzas, Datacenters, Poesía, paternidad, notas personales, Customizaciones…) |
| `Recursos/` | Reference material |
| `Archivo/` | Finished things |

Folders change, so list the current ones each run (`command ls "$VAULT/Proyectos" "$VAULT/Areas"`)
and look inside a folder before you put anything in it. Prefer existing folders and existing notes,
especially `to-do.md` notes. Create a new folder only when several items share a project that has none.

### 3. Propose, then wait

Group every line of scratch into exactly one bucket:

- **A vault note.** Name the destination path. Say whether it's a new note or an addition to an existing one.
- **Secrets.** Passwords, tokens, keys, license keys, magic-login links, `KEY=value` env lines.
  They stay in scratch under a `## Secrets` heading for the user to move to their password manager.
  Never write their values in chat, in a vault note, or in an uploaded page. Refer to them as "a password", "a token", and so on.
- **Unclear.** Lines whose meaning or destination you can't work out. They stay in scratch under `## Unclear`.
- **Delete.** Pasted agent output, `/clear`, `yes`, stray plan/spec paths, terminal pastes, keyboard mash,
  drafts that are done with (old restaurant orders, interview-reply drafts).

Ask before guessing what a person or pet is (for example, check whether a name already appears in the vault).
Show the proposal grouped by destination and **wait for approval**. If the user asks for it as a page,
write the HTML (secrets omitted) and upload it with `mcp__file_server__upload_file` (not public).

When every remaining item is already labeled by the user (e.g. a heading like "Palabras de mis hijos"),
the destinations are obvious. In that case a short proposal is enough, but still confirm before you write anything.

### 4. Apply

- **Keep the user's wording.** Group lines and fix obvious typos only. Don't paraphrase or summarize.
- **New note:** start it with `# Title`, then the grouped lines. Link related notes with `[[name]]`.
- **Existing note:** append under `## From scratch (YYYY-MM-DD)`. Never overwrite an existing file.
  Before writing a "new" file, check it doesn't exist.
- **Rewrite scratch last.** First check its md5 still matches step 1; if the user edited it meanwhile, stop and re-read.
  Copy the secret lines out of the backup by line number (`sed -n 'Np'`) so you never retype a secret.
  The backup's last line may lack a trailing newline, so add one yourself between sections.
  Keep the `scratch` title line. Verify the secrets section by line lengths (`awk '{print length}'`), not by printing it.
  - If nothing is left, scratch is just `scratch` and a blank line.

### 5. Report

Show a table: note → what went in it. List the existing notes you added to, then what's left in scratch
(secrets by kind, unclear items), what you deleted, and the backup path. Don't commit the vault.
Tell the user they can review the changes with `git status` there.
