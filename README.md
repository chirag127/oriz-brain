# oriz-brain — ChiragOS ambient personal-AI orchestrator

Live URL: https://github.com/chirag127/oriz-brain

[![MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Thin ambient-brain that **imports** Chirag's existing fleet pieces — never rewrites or deletes them.
Pipeline: **ingest → store(decision log) → reason(agent-forge) → decide → notify**.

## Architecture — import, don't rewrite

```
oriz-brain
├── sources/         # pluggable adapters that READ existing repos' committed data
│   ├── i2i.py       # → repos/own/i2i-portfolio-data/raw/api/  (P2P portfolio JSON)
│   └── mmi.py       # → repos/own/oriz-mmi committed state OR keyless Tickertape API
├── pipeline.py      # reason() calls LLMClient (same kilo→pollinations chain as agent-forge)
├── decision_log.py  # append-only markdown vault/ (git-friendly, no extra service needed)
├── notify/          # ConsoleNotifier (default) + TelegramNotifier stub (env-backed)
└── cli.py           # brain run | brain log | brain sources
```

### Repos consolidated (imported, not copied or deleted)

| Repo | Role in oriz-brain | How |
|---|---|---|
| `agent-forge` | Reasoning engine (Planner→Executor→Critic Orchestrator) | pip dep `agent-forge @ git+…`; LLMClient mirrors its provider chain |
| `i2i-portfolio-data` | P2P portfolio data source | `I2iAdapter` reads `raw/api/escrow-overview.json` + `emi-status-overview.json` |
| `oriz-mmi` / `mmi-tickertape` | Market sentiment source | `MmiAdapter` reads committed `data/latest.json`, falls back to keyless `api.tickertape.in/mmi/now` |
| `oz-ai` | LLM provider reference | `LLMClient` uses same kilo.ai→pollinations failover pattern (`@chirag127/oz-ai` docs it) |
| `life-cli` | Future email/reminder ingest (stub slot in sources/) | Not yet wired — add `LifeCliAdapter` when life-cli exposes a Python interface |
| `oriz-ipo` | Future IPO GMP ingest (stub slot) | Add `IpoAdapter` reading oriz-ipo's committed JSON when available |

**Nothing was copied. Nothing was deleted. Each source repo keeps its own automations running.**

## LLM

Keyless. `LLMClient` tries:
1. `kilo.ai` (free gateway, no key needed)
2. `text.pollinations.ai/openai` with `Referer: https://oriz.in`

Degrades gracefully — returns `[LLM unavailable]` string if both fail; cycle still logs decisions.

## Decision journal + prediction tracker

Two append-only git-friendly stores under `vault/`:

### Decision log (`vault/YYYY-MM-DD.md`)
Auto-written by `brain run` after each reasoning cycle.

```markdown
### 2026-08-13T10:00:00+00:00  [mmi]
**Observation:** Market Mood Index: 91.0 (Extreme Greed)
**Reasoning:** Extreme greed zone — portfolio rebalance warranted
**Verdict:** matters
**Action:** Review equity allocation, consider partial booking
---
```

### Prediction tracker (`vault/predictions/<id>.md`)
Manual entry; scored over time to track your own calibration.

```bash
# record a prediction
brain predict "Nifty will cross 26000 by Sep 2026" --by 2026-09-30 --confidence 75

# mark resolved
brain resolve 20260813-0001 --outcome true

# calibration stats
brain score
```

Sample `brain score` output:

| Metric | Value |
|---|---|
| Total predictions | 12 |
| Resolved | 8 |
| Correct | 5 |
| Accuracy | 62.5% |
| Brier score | 0.1875 |
| Overconfidence | +15.0% |
| Optimism bias | +12.5% |

Brier score: 0=perfect, 1=worst. Overconfidence = avg confidence on wrong predictions minus on correct ones. Optimism bias = avg confidence minus actual accuracy.

Optional richer backend: [mdv-mcp](https://github.com/chirag127/mdv-mcp) can index both `vault/` stores as a queryable memory layer.

## Notify

- **Console** — always on, Rich-formatted panel for `matters` decisions.
- **Telegram** — set `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` (fleet already has `oriz127_bot`). No hardcoded secrets.
- **ntfy** — add `NtfyNotifier` stub; send to `https://ntfy.sh/<topic>` — no key needed for public topics.

## Install

```bash
# requires Python 3.13 + uv
cd repos/own/oriz-brain
uv sync
```

## Usage

```bash
# one ambient cycle
uv run brain run

# dry run (no Telegram, console-only)
uv run brain run --dry-run

# show recent decision log
uv run brain log

# list adapters
uv run brain sources
```

## Tests

```bash
uv run pytest
```

## Roadmap (gaps from fleet inventory)

- **Unified dashboard** — single web view across i2i + MMI + IPO GMP + life-cli reminders
- **Event triggers** — run cycle on git push to i2i-portfolio-data or oriz-mmi (GitHub Actions webhook)
- **Cross-repo coordination** — agent-forge Orchestrator tasks that span multiple source adapters
- **ntfy notifier** — keyless push to ntfy.sh for mobile alerts
- **life-cli adapter** — read email/reminders from life-cli once it exposes a Python API
- **oriz-ipo adapter** — read committed IPO GMP JSON from oriz-ipo repo
