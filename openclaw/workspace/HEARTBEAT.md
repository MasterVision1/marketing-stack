# Heartbeat — Marketing Agent

Every 30 minutes, check:

1. **Ollama status** — Is the local LLM responding? `curl http://127.0.0.1:11434/api/tags`
2. **n8n status** — Is the workflow engine healthy? `curl http://localhost:5678/healthz`
3. **Pending tasks** — Any cron jobs that failed? Check memory for error logs.
4. **New leads** — Quick D365 check for vo_client records created since last heartbeat.

If all systems healthy and no pending work, reply with a brief "All clear" status.
If any system is down, log the issue and attempt recovery.
If new leads found, trigger the onboarding sequence.
