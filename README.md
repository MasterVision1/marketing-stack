# Marketing Stack — RunmAi

CLI-first marketing automation stack.
**n8n** = orchestration · **Mautic** = marketing backend · **Buffer** = social publishing · **Git** = source of truth

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
./scripts/setup.sh                          # Stand up Docker stack
./scripts/check-health.sh                   # Verify n8n, Mautic, Buffer reachable

# Phase 2: Bootstrap credentials
python scripts/bootstrap-mautic.py          # Enable API, create OAuth client, verify endpoints
python scripts/bootstrap-buffer.py          # Verify token, fetch channels, test scheduled post
bash scripts/bootstrap-n8n.sh               # Admin account, encryption key, credential entries

# Phase 3: Deploy campaigns
python scripts/deploy-campaign.py --spec campaigns/active/example.yaml --dry-run
python scripts/deploy-campaign.py --spec campaigns/active/example.yaml --live
```

No freestyle. No improvisation. The agent follows this path or stops.

---

## Setup Order

1. **Repo** — structure, env files, .gitignore
2. **Stack** — Docker Compose (n8n + Mautic + Postgres + Redis)
3. **Auth** — Mautic API enable, n8n credentials, Buffer token
4. **Schemas** — campaign.schema.json, contact-event.schema.json
5. **Workflows** — reusable n8n blocks
6. **First campaign** — 14-day onboarding (dry-run then live)

---

## Directory Layout

```
marketing-stack/
  .env.example          # Template — never commit real .env
  docker-compose.yml    # n8n + Mautic + Postgres + Redis
  scripts/
    setup.sh            # Docker up + health wait
    check-health.sh     # Endpoint liveness checks
    bootstrap-mautic.py # Mautic API setup
    bootstrap-buffer.py # Buffer API verification
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
    mautic.json         # Mautic connection config (no secrets)
    buffer.json         # Buffer connection config (no secrets)
    n8n.json            # n8n connection config (no secrets)
```

---

## 7-Day Setup Sequence

| Day | Task |
|-----|------|
| 1 | Repo, Docker setup, env files, health scripts |
| 2 | Install n8n and Mautic, confirm login and persistence |
| 3 | Enable Mautic API, set up auth, verify contact/segment endpoints |
| 4 | Buffer credentials, verify channel read + scheduled post |
| 5 | Campaign schema, event schema, first workflow templates |
| 6 | Deployment script, dry-run test campaign |
| 7 | Deploy live onboarding test, verify end-to-end event branching |

---

## What NOT To Do Yet

- Build UI
- Create dozens of campaigns
- Attempt analytics dashboards
- Do multitenancy
- Connect FlowGen
- Build custom asset editors
- Support every channel at once

---

## Prerequisites

- Docker + Docker Compose
- Python 3.10+
- Node.js 18+ (for n8n CLI)
- Buffer API token (from https://publish.buffer.com/apps)
- Domain/IP for Mautic (or localhost for dev)
