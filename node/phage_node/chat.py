"""talk to kell directly. requires a $KELL holder API key."""

import json
import sys
import urllib.request
import urllib.error

API_URL = "https://kellphage.com/api/keys/chat"
CHECK_URL = "https://kellphage.com/api/keys/check"


def chat(key, message):
    """send a message to kell and print the response."""
    if not key:
        print("error: no API key provided.")
        print("get one at kellphage.com/talk (requires 100K $KELL)")
        sys.exit(1)

    if not message:
        print("error: no message provided.")
        sys.exit(1)

    payload = json.dumps({"key": key, "message": message}).encode()
    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            print(data.get("reply", ""))
            uses = data.get("uses_remaining", "?")
            print(f"\n[{uses} uses remaining]")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            err = json.loads(body)
            print(f"error: {err.get('error', 'unknown error')}")
        except Exception:
            print(f"error: {e.code}")
        sys.exit(1)
    except Exception as e:
        print(f"error: {e}")
        sys.exit(1)


def check_key(key):
    """check remaining uses for a key."""
    if not key:
        print("error: no key provided.")
        sys.exit(1)

    try:
        url = f"{CHECK_URL}?key={key}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data.get("valid"):
                print(f"key valid. {data.get('uses_remaining', 0)} uses remaining.")
            else:
                print("key invalid or depleted.")
    except Exception as e:
        print(f"error: {e}")
        sys.exit(1)
