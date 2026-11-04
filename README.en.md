# gov-hub · Project Map for Agent Workspaces

English | [中文](README.md)

Give your AI agent a **project map**: instead of brute-force scanning folders to find "where is X documented", the agent queries a local index and lands on the authoritative file in one step.

> Measured on real workspaces: navigation cost cut by **96.7%~99.3%**; end-to-end Q&A from **141s / 40 tool calls → 40s / 5 calls** (up to 5.8× faster, 8× fewer calls). Full data: [`bench/RESULTS.md`](bench/RESULTS.md).

## Why

Agents forget where things live in *your* workspace. Every session re-pays the same discovery cost — globbing, grepping, reading dead ends — and tokens burn on navigation instead of answers. gov-hub moves that knowledge into a plain, human-readable registry (`registry.yaml`) that lives **inside your workspace**, plus a tiny stdlib-only CLI that keeps it honest.

## How it works

One closed loop of three commands:

| Command | Role |
|---|---|
| `ensure` | Gate: prints `[OK]` (enabled → look up first) / `[MUTED]` (declined → stay silent) / welcome + `[NEXT]` (ask the user once) |
| `lookup "<keyword or full question>"` | Keyword or natural-language question → authoritative file path |
| `add <file> --keywords ... --answers "..."` | Feed back: any file the agent found the hard way gets registered in one command |

Supporting commands: `init` · `check` (registry ↔ disk consistency gate) · `status` · `suggest` · `attach`/`detach` (managed block in AGENTS.md) · `install`/`uninstall`.

## Quick start

```bash
# 1. Get it
git clone https://github.com/songzhou666/gov-hub.git   # or download & unzip anywhere

# 2. One-command install: skill file into the discovery root + entry block into AGENTS.md + self-check
python govhub.py install                # user scope (recommended)
python govhub.py install --scope project  # or this project only

# 3. Uninstall (fully reversible; workspace data files are untouched)
python govhub.py uninstall
```

From then on it's automatic: ask "where is the login test report?" in any session — the agent runs `ensure → lookup`, lands on the file, and feeds new finds back into the map with `add`.

**Distribution formats** (same skill files, pick any):
- **DSH native bundle**: root `package.json` declares `dsh.bundle`; installable via `install_bundle` with this repo's Git URL, listable by any DSH plugin-market index;
- **SkillHub skill pack**: root `SKILL.md` carries full publish metadata; upload the directory as-is;
- **Plain clone**: everything above works with no platform at all.

## Design principles

- **Decision by command output, not model judgment.** The enable/decline/ask choice is `ensure`'s output, not the model's discretion — timing decisions left to model judgment were measured to fail (see [`references/anti-patterns.md`](references/anti-patterns.md)).
- **Consent first.** Nothing is written without the user's explicit yes; declining is permanent and silent; `detach` restores AGENTS.md byte-for-byte.
- **Plain data.** `registry.yaml` + `gov-hub.yaml` are human-readable files inside your workspace. No cloud, no telemetry, no network calls; Python stdlib only (optional PyYAML).
- **Map answers "where to read", nothing else.** No conversation memory, no statistics that go stale, and it yields entirely to any project that has its own lookup protocol.

## Requirements

- Python ≥ 3.9 (any; no venv needed)
- PyYAML optional (falls back to JSON index automatically)

## License

[MIT](LICENSE)
