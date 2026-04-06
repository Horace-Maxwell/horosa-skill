from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path
from typing import Any


def build_sbom(project_root: Path, runtime_manifest: Path | None = None) -> dict[str, Any]:
    pyproject = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject.get("project", {})
    payload: dict[str, Any] = {
        "schema_version": 1,
        "format": "horosa.skill.sbom.v1",
        "project": {
            "name": project.get("name"),
            "version": project.get("version"),
            "description": project.get("description"),
            "dependencies": list(project.get("dependencies", [])),
            "optional_dependencies": project.get("optional-dependencies", {}),
        },
    }
    if runtime_manifest and runtime_manifest.is_file():
        payload["runtime_manifest"] = json.loads(runtime_manifest.read_text(encoding="utf-8"))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a lightweight JSON SBOM for Horosa Skill.")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--runtime-manifest", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sbom = build_sbom(args.project_root.resolve(), args.runtime_manifest.resolve() if args.runtime_manifest else None)
    args.output.write_text(json.dumps(sbom, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"sbom: wrote {args.output}")


if __name__ == "__main__":
    main()
