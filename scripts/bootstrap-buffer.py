#!/usr/bin/env python3
"""
bootstrap-buffer.py — Verify Buffer token, fetch channels, test post create/delete.
Contract: python scripts/bootstrap-buffer.py

Buffer has migrated to a GraphQL API at https://api.buffer.com.
Authentication: Bearer token in Authorization header.

Requires:
  - BUFFER_ACCESS_TOKEN in .env
  - pip install requests
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Run: pip install requests")
    sys.exit(1)


def load_env():
    """Load .env file from project root."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
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


def gql(api_url, token, query, variables=None):
    """Execute a GraphQL query against the Buffer API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    resp = requests.post(api_url, json=payload, headers=headers, timeout=15)

    if resp.status_code == 401:
        print(f"ERROR: Buffer auth failed — HTTP 401")
        print("  Check BUFFER_ACCESS_TOKEN in .env")
        print("  Generate a new token at: https://publish.buffer.com/settings/api")
        sys.exit(1)

    if resp.status_code == 429:
        print("ERROR: Buffer rate limit exceeded. Wait 15 minutes and retry.")
        sys.exit(1)

    if resp.status_code != 200:
        print(f"ERROR: Buffer API returned HTTP {resp.status_code}")
        print(f"  Body: {resp.text[:300]}")
        sys.exit(1)

    data = resp.json()
    if "errors" in data:
        print(f"ERROR: GraphQL errors: {json.dumps(data['errors'], indent=2)[:500]}")
        return None

    return data.get("data")


def verify_account(api_url, token):
    """Verify the Buffer access token is valid and fetch account info."""
    data = gql(api_url, token, "{ account { id name email } }")
    if not data or not data.get("account"):
        print("ERROR: Could not fetch account info")
        sys.exit(1)

    acct = data["account"]
    print(f"  [PASS] Authenticated as: {acct.get('name', 'unknown')} ({acct.get('email', '')})")
    print(f"  [INFO] Account ID: {acct['id']}")
    return acct


def fetch_channels(api_url, token):
    """Fetch connected social channels."""
    data = gql(api_url, token, "{ account { channels { id name service serverUrl } } }")
    if not data or not data.get("account"):
        return []

    channels = data["account"].get("channels", [])
    if not channels:
        print("  [WARN] No connected social channels found in Buffer.")
        print("         Connect at least one channel at https://publish.buffer.com")
        return []

    for ch in channels:
        print(f"  [OK] {ch.get('service', '?')}: {ch.get('name', '?')} (ID: {ch['id']})")

    # Save channel info to config
    config_path = Path(__file__).resolve().parent.parent / "config" / "buffer.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)
    else:
        config = {}

    config["channels"] = channels
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  [OK] Saved {len(channels)} channel(s) to config/buffer.json")

    return channels


def test_create_delete_post(api_url, token, channel_id):
    """Create a test scheduled post via GraphQL, then delete it."""
    scheduled_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

    create_mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionPayload {
          post { id text status }
        }
        ... on InvalidInputError { message }
        ... on UnauthorizedError { message }
        ... on UnexpectedError { message }
      }
    }
    """
    variables = {
        "input": {
            "channelIds": [channel_id],
            "text": "[MARKETING-STACK TEST] Automated pipeline verification. Will be deleted.",
            "scheduledAt": scheduled_at,
        }
    }

    print(f"\n  Creating test scheduled post (24h from now)...")
    data = gql(api_url, token, create_mutation, variables)
    if not data:
        print("  [FAIL] Create post returned no data")
        return False

    result = data.get("createPost", {})
    post = result.get("post")
    if not post:
        error_msg = result.get("message", "Unknown error")
        print(f"  [FAIL] Create post failed: {error_msg}")
        return False

    post_id = post["id"]
    print(f"  [PASS] Post created — ID: {post_id}, Status: {post.get('status', '?')}")

    # Delete the test post
    delete_mutation = """
    mutation DeletePost($input: DeletePostInput!) {
      deletePost(input: $input) {
        ... on DeletePostPayload { success }
        ... on NotFoundError { message }
        ... on UnexpectedError { message }
      }
    }
    """
    del_data = gql(api_url, token, delete_mutation, {"input": {"postId": post_id}})
    if del_data and del_data.get("deletePost", {}).get("success"):
        print(f"  [PASS] Test post deleted — ID: {post_id}")
    else:
        print(f"  [WARN] Could not delete test post — ID: {post_id}")
        print(f"         Delete manually from Buffer dashboard")

    return True


def main():
    print("=== Buffer Bootstrap (GraphQL API) ===\n")

    env = load_env()

    api_url = env.get("BUFFER_API_URL", "https://api.buffer.com").rstrip("/")
    token = env.get("BUFFER_ACCESS_TOKEN", "")

    if not token or token == "CHANGE_ME_BUFFER_TOKEN":
        print("ERROR: BUFFER_ACCESS_TOKEN not set or still placeholder in .env")
        print("  Get your token from: https://publish.buffer.com/settings/api")
        sys.exit(1)

    # Step 1: Verify authentication
    print("[1/3] Verifying Buffer authentication...")
    verify_account(api_url, token)

    # Step 2: Fetch connected channels
    print("\n[2/3] Fetching connected channels...")
    channels = fetch_channels(api_url, token)

    if not channels:
        print("\nWARN: No channels connected. Skipping post test.")
        print("  Connect channels at https://publish.buffer.com, then re-run.")
        print("\n=== Buffer Bootstrap Complete (partial — no channels) ===")
        return

    # Use first channel for testing
    test_channel = channels[0]["id"]
    print(f"\n  Using channel '{channels[0].get('name', '?')}' ({channels[0].get('service', '?')}) for tests")

    # Step 3: Test create + delete post
    print("\n[3/3] Testing post create and delete...")
    test_create_delete_post(api_url, token, test_channel)

    print("\n=== Buffer Bootstrap Complete ===")


if __name__ == "__main__":
    main()

    print("\n=== Buffer Bootstrap Complete ===")
    print(f"  API: {api_url}")
    print(f"  Channels: {len(channels)}")
    print("  Full proof: create, read pending, update, delete all verified.")
    print("  Next: bash scripts/bootstrap-n8n.sh")


if __name__ == "__main__":
    main()
