# Marketing Stack — RunmAi

CLI-first, 24/7 autonomous marketing automation.
**OpenClaw** = AI brain · **Ollama** = local LLM ($0) · **n8n** = workflow engine · **D365** = CRM · **SendGrid** = email · **Buffer** = social

---

## Non-Negotiable Agent Rules

1. **Never deploy directly from a natural language prompt.**
2. **Always generate a structured campaign spec first.**
3. **Always validate before compile.**
4. **Always compile before deploy.**
5. **Always dry-run before live activation.**
6. **Never write secrets into repo files.**
7. **Never create production workflows without naming, tagging, and rollback metadata.**

---

## Agent Contract — Allowed Commands Only

```bash
# Phase 1: Infrastructure
./scripts/setup.sh                          # Stand up Docker stack (Postgres + n8n)
./scripts/check-health.sh                   # Verify n8n, SendGrid, Ollama, Buffer, D365

# Phase 2: Bootstrap credentials
python scripts/bootstrap-sendgrid.py        # Verify API key, list templates, create suppression groups
python scripts/bootstrap-buffer.py          # Verify token, fetch channels, test scheduled post
python scripts/bootstrap-dynamics365.py     # Verify D365 connection, check ConsultingOpsCore tables
bash scripts/bootstrap-n8n.sh               # Admin account, encryption key, credential entries

# Phase 3: Deploy campaigns
python scripts/deploy-campaign.py --spec campaigns/active/example.yaml --dry-run
python scripts/deploy-campaign.py --spec campaigns/active/example.yaml --live
```

No freestyle. No improvisation. The agent follows this path or stops.

---

## Architecture

```
                    ┌─────────────┐
                    │  OpenClaw   │  24/7 AI agent (heartbeat every 30m)
                    │  + Ollama   │  local LLM (gemma4, $0 cost)
                    └──────┬──────┘
                           │ triggers via webhook / cron
                    ┌──────▼──────┐
                    │    n8n      │  workflow orchestration
                    └──┬───┬───┬──┘
                       │   │   │
              ┌────────┘   │   └────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ SendGrid │ │   D365   │ │  Buffer  │
        │  email   │ │   CRM    │ │  social  │
        └──────────┘ └──────────┘ └──────────┘
```

---

## Setup Order

1. **Repo** — structure, env files, .gitignore
2. **Stack** — Docker Compose (n8n + Postgres)
3. **Ollama** — Install, pull gemma4 model
4. **OpenClaw** — Install, configure workspace + skills
5. **Auth** — SendGrid API key, n8n credentials, Buffer token, D365 via Azure CLI
6. **Schemas** — campaign.schema.json, contact-event.schema.json
7. **Workflows** — reusable n8n blocks
8. **First campaign** — 14-day onboarding (dry-run then live)

---

## Directory Layout

```
marketing-stack/
  .env.example          # Template — never commit real .env
  docker-compose.yml    # n8n + Postgres
  openclaw/
    workspace/          # OpenClaw workspace files
      AGENTS.md         # Agent identity + mission
      HEARTBEAT.md      # Heartbeat behavior (every 30m)
      SOUL.md           # Agent persona
      skills/           # Marketing skills (SKILL.md files)
  scripts/
    setup.sh            # Docker up + health wait
    check-health.sh     # Endpoint liveness checks
    bootstrap-sendgrid.py # SendGrid API verification
    bootstrap-buffer.py # Buffer API verification
    bootstrap-dynamics365.py # D365 connection verification
    bootstrap-n8n.sh    # n8n admin + creds
    deploy-campaign.py  # Validate → compile → deploy
  schemas/
    campaign.schema.json
    contact-event.schema.json
  campaigns/
    templates/          # Reusable campaign templates
    active/             # Live campaign specs
  workflows/
    templates/          # Reusable n8n workflow blocks
    compiled/           # Compiled workflow JSON (generated)
  config/
    sendgrid.json       # SendGrid connection config (no secrets)
    buffer.json         # Buffer connection config (no secrets)
    n8n.json            # n8n connection config (no secrets)
    dynamics365.json    # D365 CRM config (no secrets)
    openclaw.json       # OpenClaw gateway config
```

---

## OpenClaw Cron Jobs

| Schedule | Job | Description |
|----------|-----|-------------|
| 7:00 AM daily | `daily-content-plan` | Plan social posts + newsletter content |
| Every 2h (8am-6pm weekdays) | `lead-check` | Score new D365 leads, trigger email sequences |
| Monday 9:00 AM | `weekly-newsletter` | Compile and send weekly newsletter via SendGrid |
| 6:00 PM weekdays | `daily-review` | Summarize day's activity, plan tomorrow |

---

## Prerequisites

- Docker + Docker Compose (WSL2 on Windows)
- Python 3.10+
- Node.js 18+
- Ollama (local LLM runtime)
- Azure CLI (for D365 auth)
- Buffer API token
- SendGrid API key (from Azure Key Vault)
