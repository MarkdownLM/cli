# mdlm

Bare-bones CLI for your [markdownlm](https://markdownlm.com) knowledge base.

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
mdlm push --message "update auth docs"
```

## Commands

| Command | Description |
|---|---|
| `mdlm configure` | Save API key to `~/.config/mdlm/config` (mode 0600) |
| `mdlm clone [--category CATEGORY]` | Download all docs → `./knowledge/` |
| `mdlm pull` | Refresh docs from server (overwrites local) |
| `mdlm status` | Show new / modified / deleted files |
| `mdlm push [--message MSG] [--category CATEGORY] [--delete]` | Upload local changes |

## Security

- Your API key is stored in `~/.config/mdlm/config` with permissions `0600` (owner read/write only).
- Set `MDLM_API_KEY` env var to override without touching the config file.
- Keys are never echoed to the terminal (`getpass` is used during `configure`).
- HTTPS is enforced; `http://` URLs are rejected at startup.
- Conflict detection: `push` checks the remote version before overwriting — run `mdlm pull` if there's a conflict.
- `--delete` flag is required to delete remote docs; omitting it is the safe default.
