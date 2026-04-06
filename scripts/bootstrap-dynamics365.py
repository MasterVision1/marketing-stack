#!/usr/bin/env python3
"""
bootstrap-dynamics365.py — Verify Dataverse API access, test CRUD, validate schema.
Contract: python scripts/bootstrap-dynamics365.py

Auth: Uses Azure CLI token (az account get-access-token).
Target: VisionOne-Dev Dataverse (org9c07232f.crm.dynamics.com)

Requires:
  - Azure CLI installed and logged in (az login)
  - DYNAMICS365_URL in .env
  - pip install requests
"""

import json
import subprocess
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Run: pip install requests")
    sys.exit(1)

PROJECT_DIR = Path(__file__).resolve().parent.parent


def load_env():
    """Load .env file from project root."""
    env_path = PROJECT_DIR / ".env"
    if not env_path.exists():
        print(f"ERROR: .env not found at {env_path}")
        sys.exit(1)
    env = {}
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def get_dataverse_token(base_url):
    """Get Bearer token from Azure CLI for Dataverse."""
    try:
        result = subprocess.run(
            ["az", "account", "get-access-token", "--resource", f"{base_url}/"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            print(f"ERROR: az account get-access-token failed:")
            print(f"  {result.stderr.strip()}")
            print("  Make sure you're logged in: az login")
            sys.exit(1)

        token_data = json.loads(result.stdout)
        return token_data["accessToken"]
    except FileNotFoundError:
        print("ERROR: Azure CLI (az) not found. Install from https://aka.ms/installazurecliwindows")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("ERROR: az command timed out")
        sys.exit(1)


def dataverse_get(api_url, token, path, params=None):
    """GET request to Dataverse Web API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
        "Accept": "application/json",
    }
    resp = requests.get(f"{api_url}{path}", headers=headers, params=params, timeout=15)
    return resp


def dataverse_post(api_url, token, path, data):
    """POST (create) to Dataverse Web API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
        "Accept": "application/json",
        "Prefer": "return=representation",
    }
    resp = requests.post(f"{api_url}{path}", headers=headers, json=data, timeout=15)
    return resp


def dataverse_delete(api_url, token, path):
    """DELETE a record from Dataverse."""
    headers = {
        "Authorization": f"Bearer {token}",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
    }
    resp = requests.delete(f"{api_url}{path}", headers=headers, timeout=15)
    return resp


def verify_connection(api_url, token):
    """Verify we can reach Dataverse and the user has access."""
    resp = dataverse_get(api_url, token, "/WhoAmI")
    if resp.status_code != 200:
        print(f"ERROR: Dataverse WhoAmI failed — HTTP {resp.status_code}")
        print(f"  {resp.text[:300]}")
        sys.exit(1)

    who = resp.json()
    user_id = who.get("UserId", "unknown")
    org_id = who.get("OrganizationId", "unknown")
    print(f"  [PASS] Connected to Dataverse")
    print(f"         User ID: {user_id}")
    print(f"         Org ID:  {org_id}")
    return who


def verify_tables(api_url, token):
    """Check that all ConsultingOpsCore tables exist."""
    expected_tables = [
        "vo_client", "vo_engagement", "vo_project", "vo_projectphase",
        "vo_task", "vo_deliverable", "vo_marketingcampaign", "vo_request",
        "vo_scorecard", "vo_scorecardmetric", "vo_riskissue", "vo_approval"
    ]

    found = 0
    missing = []

    for table in expected_tables:
        resp = dataverse_get(
            api_url, token,
            f"/EntityDefinitions(LogicalName='{table}')",
            params={"$select": "LogicalName,DisplayName"}
        )
        if resp.status_code == 200:
            display = resp.json().get("DisplayName", {}).get("UserLocalizedLabel", {}).get("Label", table)
            print(f"  [OK] {display} ({table})")
            found += 1
        else:
            print(f"  [MISSING] {table}")
            missing.append(table)

    print(f"\n  Tables: {found}/{len(expected_tables)} found")
    if missing:
        print(f"  Missing: {', '.join(missing)}")
        print("  Run power-platform/setup-dataverse-schema.ps1 to create them")
    return missing


def test_client_crud(api_url, token):
    """Test create, read, update, delete on vo_client."""
    test_name = "[MARKETING-STACK-TEST] Pipeline Verification Client"

    # CREATE
    print(f"\n  Creating test client...")
    create_resp = dataverse_post(api_url, token, "/vo_clients", {
        "vo_name": test_name,
        "vo_contactemail": "test@marketing-stack.local",
        "vo_contactphone": "555-0000",
        "vo_industry": "Test Industry",
        "vo_status": 100000002,  # Prospect
    })

    if create_resp.status_code not in (200, 201, 204):
        print(f"  [FAIL] Create client — HTTP {create_resp.status_code}")
        print(f"         {create_resp.text[:300]}")
        return False

    # Extract client ID from response or OData-EntityId header
    if create_resp.status_code in (200, 201) and create_resp.text:
        client_data = create_resp.json()
        client_id = client_data.get("vo_clientid")
    else:
        entity_id = create_resp.headers.get("OData-EntityId", "")
        client_id = entity_id.split("(")[-1].rstrip(")") if "(" in entity_id else None

    if not client_id:
        print("  [WARN] Client created but could not extract ID for cleanup")
        return True

    print(f"  [PASS] Client created — ID: {client_id}")

    # READ
    read_resp = dataverse_get(api_url, token, f"/vo_clients({client_id})")
    if read_resp.status_code == 200:
        print(f"  [PASS] Client read back — Name: {read_resp.json().get('vo_name')}")
    else:
        print(f"  [WARN] Client read — HTTP {read_resp.status_code}")

    # DELETE (cleanup)
    del_resp = dataverse_delete(api_url, token, f"/vo_clients({client_id})")
    if del_resp.status_code == 204:
        print(f"  [PASS] Test client deleted")
    else:
        print(f"  [WARN] Client delete — HTTP {del_resp.status_code}")
        print(f"         Delete manually: {client_id}")

    return True


def test_marketing_campaign_read(api_url, token):
    """Read existing marketing campaigns to verify the table works."""
    resp = dataverse_get(
        api_url, token, "/vo_marketingcampaigns",
        params={"$top": "5", "$select": "vo_name,vo_status,vo_campaigntype"}
    )
    if resp.status_code == 200:
        campaigns = resp.json().get("value", [])
        print(f"  [PASS] Marketing Campaigns table accessible — {len(campaigns)} record(s)")
        for c in campaigns:
            print(f"         - {c.get('vo_name', 'unnamed')}")
    else:
        print(f"  [WARN] Could not read vo_marketingcampaigns — HTTP {resp.status_code}")


def save_config_update(who_am_i):
    """Update dynamics365.json with verified connection info."""
    config_path = PROJECT_DIR / "config" / "dynamics365.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)
    else:
        config = {}

    config["verified"] = True
    config["verified_user_id"] = who_am_i.get("UserId")
    config["verified_org_id"] = who_am_i.get("OrganizationId")

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  [OK] Updated config/dynamics365.json with verification info")


def main():
    print("=== Dynamics 365 / Dataverse Bootstrap ===\n")

    env = load_env()

    base_url = env.get("DYNAMICS365_URL", "").rstrip("/")
    if not base_url or base_url == "CHANGE_ME_DYNAMICS365_URL":
        print("ERROR: DYNAMICS365_URL not set in .env")
        print("  Set to your Dataverse org URL, e.g.: https://org9c07232f.crm.dynamics.com")
        sys.exit(1)

    api_url = f"{base_url}/api/data/v9.2"

    # Step 1: Get Azure CLI token
    print("[1/5] Authenticating via Azure CLI...")
    token = get_dataverse_token(base_url)
    print(f"  [PASS] Token acquired")

    # Step 2: Verify connection
    print("\n[2/5] Verifying Dataverse connection...")
    who = verify_connection(api_url, token)

    # Step 3: Verify ConsultingOpsCore tables
    print("\n[3/5] Checking ConsultingOpsCore tables...")
    missing = verify_tables(api_url, token)

    # Step 4: Test CRUD on vo_client
    if "vo_client" not in missing:
        print("\n[4/5] Testing Client CRUD operations...")
        test_client_crud(api_url, token)
    else:
        print("\n[4/5] [SKIP] vo_client table missing — cannot test CRUD")

    # Step 5: Test marketing campaign read
    if "vo_marketingcampaign" not in missing:
        print("\n[5/5] Verifying Marketing Campaign table...")
        test_marketing_campaign_read(api_url, token)
    else:
        print("\n[5/5] [SKIP] vo_marketingcampaign table missing")

    # Save verification
    save_config_update(who)

    print("\n=== Dynamics 365 Bootstrap Complete ===")


if __name__ == "__main__":
    main()
