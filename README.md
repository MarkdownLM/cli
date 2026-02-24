# <img src="https://markdownlm.com/favicon-512x512.png" width="48" height="48" align="center" /> mdlm

**mdlm** is a governance-focused CLI tool for your [markdownlm](https://markdownlm.com) knowledge base. It bridges the gap between your codebase and your team's architectural standards by providing a powerful toolkit for syncing documentation, querying patterns, and validating code against established rules.

Built for consistency, `mdlm` allows you to enforce design patterns, surface documentation gaps, and ensure that your architectural decisions are consistently applied across your projects, all from the comfort of your terminal.

## Install

```bash
cd cli
pip install -e .
```

Requires Python 3.8+ and `requests`.

## Quick start

```bash
# 1. Save your API key (from markdownlm dashboard → Settings)
mdlm configure

# 2. Clone your knowledge base into ./knowledge/
mdlm clone

# 3. Edit any .md file in ./knowledge/

# 4. See what changed
mdlm status

# 5. Push changes back
mdlm push -m "update auth docs"

# 6. Query your patterns
mdlm query "How to handle errors?" -c error_handling

# 7. Validate code vs rules
mdlm validate app/api.py -t "Add user endpoint" -c security
```

## Commands

| Command | Description |
|---|---|
| `mdlm configure` | Save API key to `~/.config/mdlm/config` (mode 0600) |
| `mdlm clone [-c CAT]` | Download all docs → `./knowledge/` |
| `mdlm pull` | Refresh docs from server (overwrites local) |
| `mdlm status` | Show new / modified / deleted files |
| `mdlm push [-m MSG] [-c CAT] [--delete]` | Upload local changes |
| `mdlm query Q [-c CAT]` | Query rules/patterns (def: `general`) |
| `mdlm validate CODE -t TASK [-c CAT]` | Check code vs rules |
| `mdlm resolve-gap Q [-c CAT]` | Resolve documentation gaps |

## Security

- Your API key is stored in `~/.config/mdlm/config` with permissions `0600` (owner read/write only).
- Set `MDLM_API_KEY` env var to override without touching the config file.
- Keys are never echoed to the terminal (`getpass` is used during `configure`).
- HTTPS is enforced; `http://` URLs are rejected at startup.
- Conflict detection: `push` checks the remote version before overwriting — run `mdlm pull` if there's a conflict.
- `--delete` flag is required to delete remote docs; omitting it is the safe default.
