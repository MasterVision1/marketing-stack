#!/usr/bin/env python3
"""
bootstrap-sendgrid.py — Verify SendGrid API key and list existing resources.
Contract:
  python scripts/bootstrap-sendgrid.py
"""

import json
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Run: pip install requests")
    sys.exit(1)

PROJECT_DIR = Path(__file__).resolve().parent.parent
BASE_URL = "https://api.sendgrid.com"


def load_env():
    env_path = PROJECT_DIR / ".env"
    if not env_path.exists():
        print("ERROR: .env not found")
        sys.exit(1)
    env = {}
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def sg_get(path, api_key):
    resp = requests.get(
        f"{BASE_URL}{path}",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=15,
    )
    return resp


def main():
    env = load_env()
    api_key = env.get("SENDGRID_API_KEY", "")

    if not api_key or api_key == "PASTE_FROM_AZURE_KEY_VAULT":
        print("ERROR: SENDGRID_API_KEY not set in .env")
        print("  Get it from Azure Key Vault: az keyvault secret show --vault-name <vault> --name SendGridApiKey --query value -o tsv")
        sys.exit(1)

    print("=== SendGrid Bootstrap ===\n")

    # 1. Verify API key scopes
    print("[1/5] Verifying API key...")
    resp = sg_get("/v3/scopes", api_key)
    if resp.status_code == 200:
        scopes = resp.json().get("scopes", [])
        print(f"  [PASS] API key valid — {len(scopes)} scopes")
        needed = ["mail.send", "marketing.singlesends.create", "marketing.contacts.update"]
        for scope in needed:
            found = any(scope in s for s in scopes)
            status = "PASS" if found else "WARN"
            print(f"  [{status}] Scope: {scope}")
    else:
        print(f"  [FAIL] API key invalid — HTTP {resp.status_code}")
        sys.exit(1)

    # 2. List templates
    print("\n[2/5] Listing dynamic templates...")
    resp = sg_get("/v3/templates?generations=dynamic&page_size=50", api_key)
    if resp.status_code == 200:
        templates = resp.json().get("result", resp.json().get("templates", []))
        print(f"  [OK] {len(templates)} dynamic templates found")
        for t in templates:
            print(f"       - {t.get('name', 'unnamed')} ({t.get('id', 'no-id')})")
    else:
        print(f"  [WARN] Could not list templates — HTTP {resp.status_code}")

    # 3. List contact lists
    print("\n[3/5] Listing marketing contact lists...")
    resp = sg_get("/v3/marketing/lists", api_key)
    if resp.status_code == 200:
        lists = resp.json().get("result", [])
        print(f"  [OK] {len(lists)} contact lists")
        for lst in lists:
            print(f"       - {lst.get('name', 'unnamed')} ({lst.get('contact_count', 0)} contacts)")
    else:
        print(f"  [WARN] Could not list contacts — HTTP {resp.status_code}")

    # 4. Check sender identity
    print("\n[4/5] Checking verified senders...")
    resp = sg_get("/v3/verified_senders", api_key)
    if resp.status_code == 200:
        senders = resp.json().get("results", [])
        print(f"  [OK] {len(senders)} verified senders")
        for s in senders:
            print(f"       - {s.get('from_email', 'unknown')} ({s.get('nickname', '')})")
    else:
        print(f"  [WARN] Could not check senders — HTTP {resp.status_code}")

    # 5. Check suppression groups
    print("\n[5/5] Checking suppression groups...")
    resp = sg_get("/v3/asm/groups", api_key)
    if resp.status_code == 200:
        groups = resp.json()
        if isinstance(groups, list):
            print(f"  [OK] {len(groups)} suppression groups")
            for g in groups:
                print(f"       - {g.get('name', 'unnamed')} (id: {g.get('id')})")
        else:
            print("  [OK] Suppression groups endpoint accessible")
    else:
        print(f"  [WARN] Could not check suppression groups — HTTP {resp.status_code}")

    print("\n=== SendGrid Bootstrap Complete ===")


if __name__ == "__main__":
    main()
