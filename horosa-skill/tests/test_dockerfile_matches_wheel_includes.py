"""The gateway Dockerfile must COPY every source path the wheel force-includes (v0.38.0 B0).

`pyproject.toml` force-includes `scripts/runtime_templates/windows` into the wheel (the Windows launcher
templates, v0.36.0 C4). The tracked Dockerfile copied only `pyproject.toml README.md src`, so `uv pip
install --system .` aborted inside the image — the same failure shape as the `.mcpbignore` lesson: a
build-time include list and a packaging COPY list drifting apart with nothing comparing them.
"""

from __future__ import annotations

import shlex
import tomllib
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]


def force_include_sources(pyproject_text: str) -> list[str]:
    data = tomllib.loads(pyproject_text)
    wheel = data["tool"]["hatch"]["build"]["targets"]["wheel"]
    sources = list(wheel.get("force-include", {}).keys())
    sources.extend(wheel.get("packages", []))
    return sources


def copy_sources(dockerfile_text: str) -> list[str]:
    sources: list[str] = []
    for line in dockerfile_text.splitlines():
        if not line.strip().upper().startswith("COPY "):
            continue
        parts = [part for part in shlex.split(line.strip())[1:] if not part.startswith("--")]
        sources.extend(parts[:-1])
    return sources


def uncovered(sources: list[str], copies: list[str]) -> list[str]:
    def covered(source: str) -> bool:
        return any(source == copy or source.startswith(copy.rstrip("/") + "/") for copy in copies)

    return sorted(source for source in sources if not covered(source))


def test_dockerfile_copies_every_force_included_source() -> None:
    sources = force_include_sources((PKG_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    copies = copy_sources((PKG_ROOT / "Dockerfile").read_text(encoding="utf-8"))
    assert "scripts/runtime_templates/windows" in sources, "the guard's reason to exist vanished from pyproject"
    assert uncovered(sources, copies) == [], (
        "Dockerfile does not COPY these wheel inputs, so `uv pip install .` fails inside the image"
    )


def test_guard_fires_when_the_template_copy_is_missing() -> None:
    """Negative control: the Dockerfile as tracked before v0.38.0 must be red."""
    legacy = "FROM python:3.12-slim\nCOPY pyproject.toml README.md ./\nCOPY src ./src\nRUN uv pip install --system .\n"
    sources = force_include_sources((PKG_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    # v0.40.0 P1 起 force-include 还带两份运行期契约：旧 Dockerfile 对它们同样是漏 COPY。
    assert uncovered(sources, copy_sources(legacy)) == [
        "contracts/jev_thresholds.json", "contracts/technique_provenance.json", "scripts/runtime_templates/windows",
    ]
    fixed = legacy.replace(
        "COPY src ./src\n",
        "COPY src ./src\nCOPY scripts/runtime_templates ./scripts/runtime_templates\n"
        "COPY contracts/jev_thresholds.json contracts/technique_provenance.json ./contracts/\n",
    )
    assert uncovered(sources, copy_sources(fixed)) == []
    # 只修模板、漏契约 → 守卫仍红（负向对照的负向对照）。
    half = legacy.replace("COPY src ./src\n", "COPY src ./src\nCOPY scripts/runtime_templates ./scripts/runtime_templates\n")
    assert uncovered(sources, copy_sources(half)) == ["contracts/jev_thresholds.json", "contracts/technique_provenance.json"]


# ---- v0.50.0-dev E-02: the image carries the JS engine and a Node that can run it --------------------------------------
# Before, the gateway image had neither: every local JS technique (BaZi / Ziwei / Qimen / Liuren / Heluo / Canping …) failed
# with js_engine.cli_missing inside the container.

import json  # noqa: E402
import re  # noqa: E402


def docker_engine_problems(dockerfile: str, dockerignore: str, *, node_pin: str, floor: tuple[int, int, int],
                           required_entries: list[str]) -> list[str]:
    problems: list[str] = []
    froms = re.findall(r"^FROM\s+(\S+)(?:\s+AS\s+(\S+))?", dockerfile, re.M | re.I)
    node_stage = next(((image, alias) for image, alias in froms if image.startswith("node:")), None)
    if node_stage is None:
        return ["no pinned node:<version>-<debian>-slim stage"]
    match = re.fullmatch(r"node:(\d+)\.(\d+)\.(\d+)-([a-z]+)-slim", node_stage[0])
    if not match:
        return [f"node stage image {node_stage[0]!r} is not pinned to an exact version and Debian release"]
    version = tuple(int(part) for part in match.groups()[:3])
    if ".".join(map(str, version)) != node_pin:
        problems.append(f"node stage is {node_stage[0]}, the runtime's Node pin is {node_pin}")
    if version < floor:
        problems.append(f"node {version} is below the engine floor {floor}")
    final_image = froms[-1][0]
    if not final_image.endswith(f"-{match.group(4)}"):
        problems.append(f"final stage {final_image} is not on the node stage's Debian release ({match.group(4)}): the copied binary needs its glibc")
    alias = node_stage[1]
    if not re.search(rf"^COPY --from={alias} /usr/local/bin/node /usr/local/bin/node$", dockerfile, re.M):
        problems.append("the node binary is not copied into the final image")
    engine = re.search(rf"^COPY --from={alias} (\S+) (\S+)$", dockerfile.replace("/usr/local/bin/node /usr/local/bin/node", ""), re.M)
    env = re.search(r"^ENV HOROSA_CORE_JS_ROOT=(\S+)$", dockerfile, re.M)
    if engine is None or env is None or env.group(1) != engine.group(2):
        problems.append("HOROSA_CORE_JS_ROOT must point at the engine directory copied from the node stage")
    if "npm ci --omit=dev" not in dockerfile:
        problems.append("production dependencies must come from the lock (npm ci --omit=dev)")
    copied = copy_sources(dockerfile)
    for entry in ["package.json", "package-lock.json", *required_entries]:
        if not any(f"horosa-core-js/{entry}" == source or f"horosa-core-js/{entry}".startswith(source.rstrip("/") + "/")
                   for source in copied):
            problems.append(f"horosa-core-js/{entry} is not copied from the build context")
    if "**/node_modules" not in dockerignore.split():
        problems.append(".dockerignore must keep a host node_modules out of the build context")
    return problems


def _engine_inputs() -> dict:
    toolchain = json.loads((PKG_ROOT / "contracts" / "runtime_toolchain.json").read_text(encoding="utf-8"))
    contract = json.loads((PKG_ROOT / "contracts" / "release_platforms.json").read_text(encoding="utf-8"))
    floor = tuple(int(x) for x in re.findall(r"\d+", contract["core_js"]["node_floor"])[:3])
    return {"node_pin": toolchain["node"]["version"], "floor": floor, "required_entries": contract["core_js"]["required_entries"]}


def test_image_bakes_in_the_js_engine_and_a_pinned_node() -> None:
    dockerfile = (PKG_ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (PKG_ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert docker_engine_problems(dockerfile, dockerignore, **_engine_inputs()) == []


def test_engine_guard_fires_on_the_pre_e02_image_and_on_drift() -> None:
    """Negative controls: the Dockerfile as tracked before E-02, an unpinned node tag, and a missing ENV must each be red."""
    dockerfile = (PKG_ROOT / "Dockerfile").read_text(encoding="utf-8")
    inputs = _engine_inputs()
    legacy = "FROM python:3.12-slim\nCOPY src ./src\nRUN uv pip install --system .\n"
    assert docker_engine_problems(legacy, "", **inputs)
    assert docker_engine_problems(re.sub(r"node:\S+", "node:22-slim", dockerfile, count=1), "**/node_modules", **inputs)
    assert docker_engine_problems(dockerfile.replace("ENV HOROSA_CORE_JS_ROOT=", "ENV X="), "**/node_modules", **inputs)
    assert docker_engine_problems(dockerfile.replace("COPY horosa-core-js/dist ./dist\n", ""), "**/node_modules", **inputs)
    assert docker_engine_problems(dockerfile, "", **inputs)
