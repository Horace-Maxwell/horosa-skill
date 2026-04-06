from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
READMES = [ROOT / "README.md", ROOT / "README_EN.md", ROOT / "horosa-skill" / "README.md"]
PATTERN = re.compile(r"\[[^\]]+\]\((\./[^)]+)\)")


def main() -> None:
    missing: list[str] = []
    for readme in READMES:
        text = readme.read_text(encoding="utf-8")
        for rel in PATTERN.findall(text):
            target = (readme.parent / rel).resolve()
            if not target.exists():
                missing.append(f"{readme}: {rel}")
    if missing:
        raise SystemExit("Broken relative links:\n" + "\n".join(missing))
    print("readme-links: ok")


if __name__ == "__main__":
    main()
