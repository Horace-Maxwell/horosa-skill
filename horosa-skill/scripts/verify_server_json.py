from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVER_JSON = ROOT / "server.json"


def main() -> None:
    payload = json.loads(SERVER_JSON.read_text(encoding="utf-8"))
    required = ["name", "title", "description", "version", "packages"]
    missing = [key for key in required if key not in payload]
    if missing:
        raise SystemExit(f"server.json missing fields: {missing}")
    if not isinstance(payload["packages"], list) or not payload["packages"]:
        raise SystemExit("server.json packages must contain at least one package definition.")
    package = payload["packages"][0]
    for field in ["registryType", "identifier", "version", "transport"]:
        if field not in package:
            raise SystemExit(f"server.json first package missing field: {field}")
    print("server.json: ok")


if __name__ == "__main__":
    main()
