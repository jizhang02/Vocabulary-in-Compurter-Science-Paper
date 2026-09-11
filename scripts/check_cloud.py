"""Read one public entry to check the deployed database without changing data."""
import json
from pathlib import Path
import re
import urllib.request


def main():
    config = (Path(__file__).resolve().parents[1] / "docs/config.js").read_text(encoding="utf-8")
    def setting(name):
        match = re.search(r'\b' + name + r'\s*:\s*"([^"]+)"', config)
        if not match:
            raise ValueError(f"Missing public configuration: {name}")
        return match.group(1)

    url = setting("supabaseUrl").rstrip("/") + "/rest/v1/entries?select=id&limit=1"
    request = urllib.request.Request(url, headers={"apikey": setting("supabasePublishableKey")})
    with urllib.request.urlopen(request, timeout=30) as response:
        entries = json.load(response)
    if not isinstance(entries, list) or not entries or not entries[0].get("id"):
        raise RuntimeError("Cloud vocabulary did not return an entry")
    print("PASS: public vocabulary database is reachable.")


if __name__ == "__main__":
    main()
