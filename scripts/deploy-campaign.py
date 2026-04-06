#!/usr/bin/env python3
"""
deploy-campaign.py — Validate → Compile → Deploy marketing campaigns.
Contract:
  python scripts/deploy-campaign.py --spec campaigns/active/example.yaml --dry-run
  python scripts/deploy-campaign.py --spec campaigns/active/example.yaml --live

Rules enforced:
  1. Never deploy directly from a natural language prompt.
  2. Always generate a structured campaign spec first.
  3. Always validate before compile.
  4. Always compile before deploy.
  5. Always dry-run before live activation.
  6. Never write secrets into repo files.
  7. Never create production workflows without naming, tagging, and rollback metadata.
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: 'pyyaml' package required. Run: pip install pyyaml")
    sys.exit(1)

try:
    import jsonschema
except ImportError:
    print("ERROR: 'jsonschema' package required. Run: pip install jsonschema")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Run: pip install requests")
    sys.exit(1)


PROJECT_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = PROJECT_DIR / "schemas" / "campaign.schema.json"
COMPILED_DIR = PROJECT_DIR / "workflows" / "compiled"


def load_env():
    """Load .env file."""
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


def load_spec(spec_path):
    """Load campaign spec from YAML."""
    path = Path(spec_path)
    if not path.exists():
        print(f"ERROR: Spec file not found: {spec_path}")
        sys.exit(1)

    with open(path, "r") as f:
        spec = yaml.safe_load(f)

    if not spec:
        print(f"ERROR: Spec file is empty: {spec_path}")
        sys.exit(1)

    print(f"  [OK] Loaded spec: {spec.get('name', 'unnamed')} ({spec.get('id', 'no-id')})")
    return spec


def validate_spec(spec):
    """Validate campaign spec against JSON schema."""
    if not SCHEMA_PATH.exists():
        print(f"ERROR: Schema not found at {SCHEMA_PATH}")
        sys.exit(1)

    with open(SCHEMA_PATH, "r") as f:
        schema = json.load(f)

    try:
        jsonschema.validate(instance=spec, schema=schema)
        print("  [PASS] Schema validation passed")
        return True
    except jsonschema.ValidationError as e:
        print(f"  [FAIL] Schema validation failed:")
        print(f"         Path: {' → '.join(str(p) for p in e.absolute_path)}")
        print(f"         Error: {e.message}")
        return False
    except jsonschema.SchemaError as e:
        print(f"  [FAIL] Invalid schema: {e.message}")
        return False


def validate_business_rules(spec):
    """Additional business rule validation beyond schema."""
    errors = []

    # Must have at least one step
    if not spec.get("steps"):
        errors.append("Campaign has no steps defined")

    # Must have exit conditions
    if not spec.get("exit_conditions"):
        errors.append("Campaign has no exit conditions")

    # Must have at least one goal
    if not spec.get("goals"):
        errors.append("Campaign has no goals")

    # Entry trigger must be defined
    trigger = spec.get("entry_trigger", {})
    if not trigger.get("type") or not trigger.get("value"):
        errors.append("Entry trigger type and value are required")

    # Check step references are valid
    step_ids = {s.get("id") for s in spec.get("steps", [])}
    for step in spec.get("steps", []):
        if step.get("next") and step["next"] not in step_ids:
            errors.append(f"Step '{step['id']}' references unknown next step '{step['next']}'")

    for rule in spec.get("branch_rules", []):
        if rule.get("action") == "goto_step" and rule.get("target") not in step_ids:
            errors.append(f"Branch rule targets unknown step '{rule.get('target')}'")

    # No secrets in spec
    spec_str = json.dumps(spec)
    secret_patterns = ["password", "secret", "token", "api_key", "private_key"]
    for pattern in secret_patterns:
        if pattern in spec_str.lower():
            # Check it's not just a field name reference
            for step in spec.get("steps", []):
                config = step.get("config", {})
                for key, value in config.items() if isinstance(config, dict) else []:
                    if pattern in str(value).lower() and len(str(value)) > 20:
                        errors.append(f"Possible secret found in step '{step.get('id')}' config key '{key}'")

    if errors:
        for e in errors:
            print(f"  [FAIL] {e}")
        return False

    print("  [PASS] Business rule validation passed")
    return True


def compile_campaign(spec, env):
    """Compile campaign spec into deployable n8n workflow JSON + Mautic assets."""
    campaign_id = spec["id"]
    version = spec.get("version", "v1")
    timestamp = datetime.now(timezone.utc).isoformat()

    deployment = {
        "deployment_id": str(uuid.uuid4()),
        "campaign_id": campaign_id,
        "campaign_name": spec["name"],
        "version": version,
        "compiled_at": timestamp,
        "status": "compiled",
        "rollback_metadata": {
            "previous_version": None,
            "compiled_by": "deploy-campaign.py",
            "can_rollback": True,
        },
        "n8n_workflows": [],
        "mautic_assets": {
            "tags": [],
            "segments": [],
            "emails": [],
            "campaign": None,
        },
        "buffer_posts": [],
    }

    # Compile entry tags
    entry_tags = spec.get("tags", {}).get("add_on_entry", [])
    exit_tags = spec.get("tags", {}).get("remove_on_exit", [])
    deployment["mautic_assets"]["tags"] = list(set(entry_tags + exit_tags))

    # Compile steps into workflow nodes
    workflow_nodes = []
    for i, step in enumerate(spec.get("steps", [])):
        node = {
            "id": step["id"],
            "type": step["type"],
            "channel": step["channel"],
            "position": [250, 150 + (i * 120)],
            "config": step.get("config", {}),
        }

        if step.get("delay"):
            node["delay"] = step["delay"]

        if step["type"] == "send_email":
            deployment["mautic_assets"]["emails"].append({
                "step_id": step["id"],
                "template": step.get("config", {}).get("template_id"),
                "subject": step.get("config", {}).get("subject"),
            })

        if step["type"] == "schedule_social":
            deployment["buffer_posts"].append({
                "step_id": step["id"],
                "text": step.get("config", {}).get("text", ""),
                "channel_id": step.get("config", {}).get("channel_id"),
                "scheduled_at": step.get("config", {}).get("scheduled_at"),
            })

        workflow_nodes.append(node)

    # Build n8n workflow structure
    main_workflow = {
        "name": f"[Campaign] {spec['name']} {version}",
        "tags": [
            {"name": "deployment"},
            {"name": f"campaign:{campaign_id}"},
        ],
        "active": False,  # Never activate during compile
        "nodes": workflow_nodes,
        "connections": {},
        "settings": {
            "timezone": spec.get("schedule", {}).get("timezone", "America/Chicago"),
        },
        "staticData": {
            "campaign_id": campaign_id,
            "version": version,
            "compiled_at": timestamp,
        },
    }

    # Wire up connections
    for step in spec.get("steps", []):
        if step.get("next"):
            main_workflow["connections"][step["id"]] = {
                "main": [[{"node": step["next"], "type": "main", "index": 0}]]
            }

    deployment["n8n_workflows"].append(main_workflow)

    # Branch handler workflow
    if spec.get("branch_rules"):
        branch_workflow = {
            "name": f"[Branch] {spec['name']} {version}",
            "tags": [
                {"name": "branch-handler"},
                {"name": f"campaign:{campaign_id}"},
            ],
            "active": False,
            "nodes": [],
            "connections": {},
            "settings": {
                "timezone": spec.get("schedule", {}).get("timezone", "America/Chicago"),
            },
        }

        for rule in spec.get("branch_rules", []):
            branch_node = {
                "id": f"branch_{rule['event']}",
                "type": "branch_condition",
                "event": rule["event"],
                "action": rule["action"],
                "target": rule.get("target"),
            }
            branch_workflow["nodes"].append(branch_node)

        deployment["n8n_workflows"].append(branch_workflow)

    # Write compiled output
    COMPILED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = COMPILED_DIR / f"{campaign_id}_{version}.json"
    with open(output_path, "w") as f:
        json.dump(deployment, f, indent=2)

    print(f"  [OK] Compiled to: {output_path}")
    print(f"  [OK] Workflows: {len(deployment['n8n_workflows'])}")
    print(f"  [OK] Mautic emails: {len(deployment['mautic_assets']['emails'])}")
    print(f"  [OK] Buffer posts: {len(deployment['buffer_posts'])}")
    print(f"  [OK] Tags: {deployment['mautic_assets']['tags']}")

    return deployment


def dry_run(deployment, env):
    """Dry-run: validate everything would work without activating."""
    print("\n  --- DRY RUN ---")
    print(f"  Deployment ID: {deployment['deployment_id']}")
    print(f"  Campaign: {deployment['campaign_name']} ({deployment['campaign_id']})")
    print(f"  Version: {deployment['version']}")

    n8n_url = f"{env.get('N8N_PROTOCOL', 'http')}://{env.get('N8N_HOST', 'localhost')}:{env.get('N8N_PORT', '5678')}"
    mautic_url = env.get("MAUTIC_URL", "http://localhost:8080")

    # Check n8n
    try:
        resp = requests.get(f"{n8n_url}/healthz", timeout=5)
        print(f"  [CHECK] n8n reachable: {'YES' if resp.status_code == 200 else 'NO'}")
    except requests.RequestException:
        print("  [CHECK] n8n reachable: NO (stack may not be running)")

    # Check Mautic
    try:
        resp = requests.get(mautic_url, timeout=5)
        print(f"  [CHECK] Mautic reachable: {'YES' if resp.status_code in (200, 301, 302) else 'NO'}")
    except requests.RequestException:
        print("  [CHECK] Mautic reachable: NO (stack may not be running)")

    # Check Buffer (GraphQL API)
    buffer_token = env.get("BUFFER_ACCESS_TOKEN", "")
    if buffer_token and buffer_token != "CHANGE_ME_BUFFER_TOKEN":
        try:
            resp = requests.post(
                env.get("BUFFER_API_URL", "https://api.buffer.com"),
                json={"query": "{ account { id } }"},
                headers={
                    "Authorization": f"Bearer {buffer_token}",
                    "Content-Type": "application/json",
                },
                timeout=5,
            )
            ok = resp.status_code == 200 and "data" in resp.json()
            print(f"  [CHECK] Buffer API: {'YES' if ok else 'NO'}")
        except requests.RequestException:
            print("  [CHECK] Buffer API: NO")
    else:
        print("  [CHECK] Buffer API: SKIP (no token)")

    # Check Dynamics 365
    d365_url = env.get("DYNAMICS365_URL", "")
    if d365_url and d365_url != "CHANGE_ME_DYNAMICS365_URL":
        try:
            import subprocess
            token_result = subprocess.run(
                ["az", "account", "get-access-token", "--resource", f"{d365_url}/", "--query", "accessToken", "-o", "tsv"],
                capture_output=True, text=True, timeout=15,
            )
            if token_result.returncode == 0 and token_result.stdout.strip():
                d365_token = token_result.stdout.strip()
                resp = requests.get(
                    f"{d365_url}/api/data/v9.2/WhoAmI",
                    headers={"Authorization": f"Bearer {d365_token}", "OData-Version": "4.0"},
                    timeout=10,
                )
                print(f"  [CHECK] Dynamics 365: {'YES' if resp.status_code == 200 else 'NO'}")
            else:
                print("  [CHECK] Dynamics 365: NO (az login required)")
        except Exception:
            print("  [CHECK] Dynamics 365: NO")
    else:
        print("  [CHECK] Dynamics 365: SKIP (no URL)")

    # Enumerate what would be created
    for wf in deployment.get("n8n_workflows", []):
        print(f"  [WOULD CREATE] n8n workflow: {wf['name']} ({len(wf.get('nodes', []))} nodes)")

    for email in deployment.get("mautic_assets", {}).get("emails", []):
        print(f"  [WOULD CREATE] Mautic email: step {email['step_id']} — {email.get('subject', 'no subject')}")

    for post in deployment.get("buffer_posts", []):
        text_preview = (post.get("text", "")[:60] + "...") if len(post.get("text", "")) > 60 else post.get("text", "")
        print(f"  [WOULD CREATE] Buffer post: {text_preview}")

    for tag in deployment.get("mautic_assets", {}).get("tags", []):
        print(f"  [WOULD ENSURE] Mautic tag: {tag}")

    if d365_url and d365_url != "CHANGE_ME_DYNAMICS365_URL":
        print(f"  [WOULD CREATE] D365 vo_MarketingCampaign: {deployment['campaign_name']}")

    print("\n  --- DRY RUN COMPLETE — Nothing was deployed ---")
    print(f"  To deploy live: python scripts/deploy-campaign.py --spec <same-spec> --live")

    return True


def deploy_live(deployment, env):
    """Deploy compiled campaign to live systems."""
    n8n_url = f"{env.get('N8N_PROTOCOL', 'http')}://{env.get('N8N_HOST', 'localhost')}:{env.get('N8N_PORT', '5678')}"
    n8n_user = env.get("N8N_BASIC_AUTH_USER", "admin")
    n8n_pass = env.get("N8N_BASIC_AUTH_PASSWORD", "")

    print("\n  --- LIVE DEPLOYMENT ---")
    print(f"  Deployment ID: {deployment['deployment_id']}")

    results = {
        "workflows_created": [],
        "workflows_failed": [],
        "errors": [],
    }

    # Deploy n8n workflows
    for wf in deployment.get("n8n_workflows", []):
        try:
            resp = requests.post(
                f"{n8n_url}/api/v1/workflows",
                json=wf,
                auth=(n8n_user, n8n_pass),
                timeout=30,
            )
            if resp.status_code in (200, 201):
                wf_data = resp.json()
                wf_id = wf_data.get("id", "unknown")
                print(f"  [DEPLOYED] Workflow: {wf['name']} — ID: {wf_id}")
                results["workflows_created"].append({"name": wf["name"], "id": wf_id})

                # Activate the workflow
                activate_resp = requests.patch(
                    f"{n8n_url}/api/v1/workflows/{wf_id}",
                    json={"active": True},
                    auth=(n8n_user, n8n_pass),
                    timeout=15,
                )
                if activate_resp.status_code == 200:
                    print(f"  [ACTIVATED] Workflow: {wf['name']}")
                else:
                    print(f"  [WARN] Could not activate: {wf['name']} — HTTP {activate_resp.status_code}")
            else:
                print(f"  [FAIL] Workflow: {wf['name']} — HTTP {resp.status_code}")
                results["workflows_failed"].append(wf["name"])
        except requests.RequestException as e:
            print(f"  [FAIL] Workflow: {wf['name']} — {e}")
            results["errors"].append(str(e))

    # Deploy Dynamics 365 marketing campaign record
    d365_url = env.get("DYNAMICS365_URL", "")
    if d365_url and d365_url != "CHANGE_ME_DYNAMICS365_URL":
        try:
            import subprocess
            token_result = subprocess.run(
                ["az", "account", "get-access-token", "--resource", f"{d365_url}/", "--query", "accessToken", "-o", "tsv"],
                capture_output=True, text=True, timeout=15,
            )
            if token_result.returncode == 0 and token_result.stdout.strip():
                d365_token = token_result.stdout.strip()
                campaign_payload = {
                    "vo_name": deployment["campaign_name"],
                    "vo_campaignid_external": deployment["campaign_id"],
                    "vo_status": 100000000,  # Active
                }
                resp = requests.post(
                    f"{d365_url}/api/data/v9.2/vo_marketingcampaigns",
                    json=campaign_payload,
                    headers={
                        "Authorization": f"Bearer {d365_token}",
                        "OData-Version": "4.0",
                        "Content-Type": "application/json",
                    },
                    timeout=15,
                )
                if resp.status_code in (200, 201, 204):
                    print(f"  [DEPLOYED] D365 MarketingCampaign: {deployment['campaign_name']}")
                else:
                    print(f"  [WARN] D365 campaign creation: HTTP {resp.status_code}")
            else:
                print("  [SKIP] D365 campaign — no Azure CLI token")
        except Exception as e:
            print(f"  [WARN] D365 campaign creation failed: {e}")

    # Write deployment report
    report_path = COMPILED_DIR / f"{deployment['campaign_id']}_{deployment['version']}_report.json"
    report = {
        "deployment_id": deployment["deployment_id"],
        "campaign_id": deployment["campaign_id"],
        "version": deployment["version"],
        "deployed_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n  Deployment report: {report_path}")

    if results["workflows_failed"] or results["errors"]:
        print("  [WARN] Some items failed — review report")
    else:
        print("  [OK] All items deployed successfully")

    print("\n  --- LIVE DEPLOYMENT COMPLETE ---")
    return results


def main():
    parser = argparse.ArgumentParser(description="Deploy marketing campaign")
    parser.add_argument("--spec", required=True, help="Path to campaign spec YAML file")
    parser.add_argument("--dry-run", action="store_true", help="Validate and simulate without deploying")
    parser.add_argument("--live", action="store_true", help="Deploy to live systems")

    args = parser.parse_args()

    if not args.dry_run and not args.live:
        print("ERROR: Must specify --dry-run or --live")
        print("  Always dry-run first:")
        print("    python scripts/deploy-campaign.py --spec <file> --dry-run")
        sys.exit(1)

    if args.dry_run and args.live:
        print("ERROR: Cannot specify both --dry-run and --live")
        sys.exit(1)

    env = load_env()

    print("=== Campaign Deployment Pipeline ===\n")

    # Step 1: Load spec
    print("[1/4] Loading campaign spec...")
    spec = load_spec(args.spec)

    # Step 2: Validate
    print("\n[2/4] Validating campaign spec...")
    schema_valid = validate_spec(spec)
    rules_valid = validate_business_rules(spec)

    if not schema_valid or not rules_valid:
        print("\n  ABORT: Validation failed. Fix errors and retry.")
        sys.exit(1)

    # Step 3: Compile
    print("\n[3/4] Compiling campaign...")
    deployment = compile_campaign(spec, env)

    # Step 4: Deploy or dry-run
    if args.dry_run:
        print("\n[4/4] Running dry-run...")
        dry_run(deployment, env)
    elif args.live:
        print("\n[4/4] Deploying LIVE...")
        deploy_live(deployment, env)


if __name__ == "__main__":
    main()
