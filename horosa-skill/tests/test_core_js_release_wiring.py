"""The JS engine asset travels through the whole release pipeline (v0.50.0-dev, E-02).

Every link that could drop it is checked here: the manifest generator writes the `core_js` entry from the archive's own bytes,
the release verifier refuses a manifest of a release ≥ `core_js.since` without it (and bytes that disagree with it), the
`[GAP]/[OK]` verdict of `sync_windows_release.py --check` names a missing asset / entry / digest, release-completeness
(`verify_published_release.py`) does the same for the public latest, and the two shell/YAML halves (publish_release.sh,
release-runtime.yml) carry the asset from the maintainer's draft into the final manifest and SHA256SUMS.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from corejs_fixture import core_js_manifest_entry, make_core_js_archive

PKG_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PKG_ROOT.parent
SCRIPTS = PKG_ROOT / "scripts"
CONTRACT = json.loads((PKG_ROOT / "contracts" / "release_platforms.json").read_text(encoding="utf-8"))
SINCE = CONTRACT["core_js"]["since"]
VERSION = "9.9.9"
TAG = f"v{VERSION}"
BASE = f"https://github.com/o/r/releases/download/{TAG}"
ASSET = CONTRACT["core_js"]["asset"].format(version=VERSION)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


vrr = _load("verify_runtime_release")
swr = _load("sync_windows_release")
vpr = _load("verify_published_release")


def _archive(tmp_path: Path, **kwargs) -> dict:
    return make_core_js_archive(tmp_path / ASSET, VERSION, **kwargs)


# ---------------------------------------------------------------- the contract and the installer agree


def test_contract_core_js_section_is_complete_and_matches_the_engine() -> None:
    spec = CONTRACT["core_js"]
    package = json.loads((PKG_ROOT / "horosa-core-js" / "package.json").read_text(encoding="utf-8"))
    assert re.fullmatch(r"\d+\.\d+\.\d+", spec["since"]) and "{version}" in spec["asset"]
    assert spec["manifest_key"] == "core_js" and spec["manifest_key"] not in CONTRACT["platforms"]
    assert spec["node_floor"] == package["engines"]["node"], "the asset's node floor is the engine's"
    assert spec["root"] == "horosa-core-js" and "bin/cli.mjs" in spec["required_entries"]


# ---------------------------------------------------------------- generate_release_manifest.py


def test_generator_writes_core_js_from_the_archive_bytes(tmp_path: Path) -> None:
    info = _archive(tmp_path)
    darwin = tmp_path / f"horosa-runtime-darwin-arm64-{TAG}.tar.gz"
    darwin.write_bytes(b"d" * 10)
    out = tmp_path / "runtime-manifest.json"
    subprocess.run([sys.executable, str(SCRIPTS / "generate_release_manifest.py"), "--version", VERSION, "--url-base", BASE,
                    "--darwin-archive", str(darwin), "--core-js-archive", str(info["path"]), "--output", str(out)], check=True)
    manifest = json.loads(out.read_text(encoding="utf-8"))
    assert set(manifest["platforms"]) == {"darwin-arm64"}, "core_js never goes under platforms"
    assert manifest["core_js"] == core_js_manifest_entry(info, f"{BASE}/{ASSET}", VERSION)


def test_generator_refuses_an_engine_of_another_version(tmp_path: Path) -> None:
    info = make_core_js_archive(tmp_path / ASSET, "9.9.8")
    darwin = tmp_path / "d.tar.gz"
    darwin.write_bytes(b"d")
    failed = subprocess.run([sys.executable, str(SCRIPTS / "generate_release_manifest.py"), "--version", VERSION, "--url-base", BASE,
                             "--darwin-archive", str(darwin), "--core-js-archive", str(info["path"]),
                             "--output", str(tmp_path / "m.json")], capture_output=True, text=True)
    assert failed.returncode != 0 and "9.9.8" in failed.stderr


# ---------------------------------------------------------------- verify_runtime_release.py


def _manifest_with(entry: dict | None, version: str = VERSION) -> dict:
    manifest = {"version": version, "platforms": {"darwin-arm64": {"url": "u", "sha256": "s", "archive_type": "tar.gz"}}}
    if entry is not None:
        manifest["core_js"] = entry
    return manifest


def test_verifier_accepts_a_matching_asset(tmp_path: Path) -> None:
    info = _archive(tmp_path)
    entry = core_js_manifest_entry(info, f"{BASE}/{ASSET}", VERSION)
    assert vrr.core_js_problems(_manifest_with(entry), info["path"], CONTRACT) == []
    assert vrr.core_js_problems(_manifest_with(entry), None, CONTRACT) == []


def test_verifier_requires_the_entry_from_since_on_only(tmp_path: Path) -> None:
    assert any("required since" in p for p in vrr.core_js_problems(_manifest_with(None), None, CONTRACT))
    older = ".".join(str(max(0, int(x) - (1 if i == 1 else 0))) for i, x in enumerate(SINCE.split(".")))
    assert vrr.core_js_problems(_manifest_with(None, older), None, CONTRACT) == [], "releases before `since` never had it"


@pytest.mark.parametrize("breakage, needle", [
    ({"sha256": "0" * 64}, "sha256 does not match"),
    ({"size": 1}, ".size=1"),
    ({"node_floor": ">=18"}, "node_floor"),
    ({"url": f"https://github.com/o/r/releases/download/v9.9.8/{ASSET}"}, "pin-forward"),
    ({"version": "9.9.8"}, "core_js.version"),
])
def test_verifier_names_an_entry_that_disagrees_with_the_bytes(tmp_path: Path, breakage: dict, needle: str) -> None:
    info = _archive(tmp_path)
    entry = {**core_js_manifest_entry(info, f"{BASE}/{ASSET}", VERSION), **breakage}
    assert any(needle in p for p in vrr.core_js_problems(_manifest_with(entry), info["path"], CONTRACT))


@pytest.mark.parametrize("kwargs, needle", [
    ({"omit": ("bin/cli.mjs",)}, "bin/cli.mjs"),
    ({"omit": ("node_modules/lunar-javascript/package.json",)}, "node_modules/lunar-javascript"),
    ({"extra": {"horosa-core-js/../escape.js": b"x"}}, "outside"),
    ({"extra": {"elsewhere/x.js": b"x"}}, "outside"),
])
def test_verifier_rejects_an_archive_the_installer_could_not_use(tmp_path: Path, kwargs: dict, needle: str) -> None:
    info = _archive(tmp_path, **kwargs)
    entry = core_js_manifest_entry(info, f"{BASE}/{ASSET}", VERSION)
    assert any(needle in p for p in vrr.core_js_problems(_manifest_with(entry), info["path"], CONTRACT))


# ---------------------------------------------------------------- sync_windows_release.py --check ([GAP] / [OK])


def _release(sha: str, size: int = 100) -> tuple[list[str], dict, dict[str, dict], str]:
    assets = [f"horosa-runtime-darwin-arm64-{TAG}.tar.gz", f"horosa-runtime-win32-x64-{TAG}.zip", "runtime-manifest.json",
              "SHA256SUMS.txt", "horosa-skill-sbom.json", f"horosa-skill-{VERSION}.mcpb", f"horosa_skill-{VERSION}-py3-none-any.whl",
              ASSET]
    manifest = {"version": VERSION, "platforms": {
        key: {"url": f"{BASE}/{CONTRACT['platforms'][key]['asset'].format(version=VERSION)}", "sha256": "a", "archive_type": "zip"}
        for key in CONTRACT["platforms"]}}
    manifest["core_js"] = {"url": f"{BASE}/{ASSET}", "sha256": sha, "size": size, "archive_type": "tar.gz",
                           "node_floor": CONTRACT["core_js"]["node_floor"], "version": VERSION, "root": "horosa-core-js"}
    details = {name: {"digest": None, "size": None} for name in assets}
    details[ASSET] = {"digest": sha, "size": size}
    return assets, manifest, details, f"{sha}  {ASSET}\n"


def test_sync_check_is_ok_when_the_asset_entry_and_digest_agree() -> None:
    assets, manifest, details, sums = _release("ab" * 32)
    a = swr.assess_from(TAG, assets, manifest, CONTRACT, asset_details=details, sums=sums)
    assert swr.gaps(a) == [] and a["core_js"]["required"]


def test_sync_check_falls_back_to_sha256sums_when_github_gives_no_digest() -> None:
    assets, manifest, details, sums = _release("ab" * 32)
    details[ASSET]["digest"] = None
    assert swr.gaps(swr.assess_from(TAG, assets, manifest, CONTRACT, asset_details=details, sums=sums)) == []
    assert any("published digest" in g for g in swr.gaps(swr.assess_from(TAG, assets, manifest, CONTRACT, asset_details=details, sums="")))


@pytest.mark.parametrize("mutate, needle", [
    (lambda assets, manifest, details: assets.remove(ASSET), "JS engine asset"),
    (lambda assets, manifest, details: manifest.pop("core_js"), "core_js in manifest"),
    (lambda assets, manifest, details: details[ASSET].update(digest="cd" * 32), "!= published"),
    (lambda assets, manifest, details: manifest["core_js"].update(sha256=""), "core_js manifest sha256"),
    (lambda assets, manifest, details: details[ASSET].update(size=101), "size"),
    (lambda assets, manifest, details: manifest["core_js"].update(url=f"https://github.com/o/r/releases/download/v9.9.8/{ASSET}"),
     "not pinned to this tag"),
])
def test_sync_check_reports_each_core_js_gap(mutate, needle: str) -> None:
    assets, manifest, details, sums = _release("ab" * 32)
    mutate(assets, manifest, details)
    missing = swr.gaps(swr.assess_from(TAG, assets, manifest, CONTRACT, asset_details=details, sums=sums))
    assert any(needle in g for g in missing), missing


def test_sync_check_does_not_ask_old_releases_for_the_asset() -> None:
    old = "0.38.0"
    a = swr.assess_from(f"v{old}", [], {"version": old, "platforms": {}}, CONTRACT)
    assert a["core_js"] == {"required": False}
    assert not any("core_js" in g or "JS engine" in g for g in swr.gaps(a))


def test_windows_box_fallback_keeps_the_asset_in_the_regenerated_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """build_and_verify regenerates runtime-manifest.json: without passing the asset along, the fallback would drop it."""
    calls: list[list[str]] = []
    monkeypatch.setattr(swr, "preflight_vendor_sources", lambda: None)
    monkeypatch.setattr(swr, "DIST", tmp_path)
    a = {"version": VERSION, "tag": TAG, "win_zip": f"horosa-runtime-win32-x64-{TAG}.zip",
         "darwin_tar": f"horosa-runtime-darwin-arm64-{TAG}.tar.gz", "core_js": {"required": True, "asset": ASSET}}
    for name in (a["win_zip"], a["darwin_tar"], ASSET):
        (tmp_path / name).write_bytes(b"x")

    def fake_run(cmd, *, cwd=None, capture=False):
        calls.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(swr, "run", fake_run)
    monkeypatch.setattr(swr.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(subprocess.CalledProcessError(1, "gh")))
    swr.build_and_verify(a)
    flat = [" ".join(cmd) for cmd in calls]
    assert any("release download" in c and ASSET in c for c in flat)
    assert any("generate_release_manifest.py" in c and "--core-js-archive" in c for c in flat)
    assert any("verify_runtime_release.py" in c and "--core-js-archive" in c for c in flat)
    assert ASSET in (tmp_path / "SHA256SUMS.txt").read_text(encoding="utf-8")


# ---------------------------------------------------------------- verify_published_release.py (release-completeness.yml)


def _published() -> tuple[dict, str, dict[str, str]]:
    platforms, sums, digests = {}, [], {}
    for i, (key, entry) in enumerate(CONTRACT["platforms"].items()):
        asset = entry["asset"].format(version=VERSION)
        sha = f"{i:02d}" * 32
        platforms[key] = {"url": f"{BASE}/{asset}", "sha256": sha, "archive_type": "zip", "size": 100 + i, "min_os": entry.get("min_os")}
        sums.append(f"{sha}  {asset}")
        digests[asset] = sha
    sha = "ee" * 32
    manifest = {"version": VERSION, "platforms": platforms,
                "core_js": {"url": f"{BASE}/{ASSET}", "sha256": sha, "archive_type": "tar.gz", "size": 77,
                            "node_floor": CONTRACT["core_js"]["node_floor"], "version": VERSION, "root": "horosa-core-js"}}
    sums.append(f"{sha}  {ASSET}")
    digests[ASSET] = sha
    return manifest, "\n".join(sums) + "\n", digests


def _probe(manifest: dict):
    sizes = {e["url"]: e["size"] for e in [*manifest["platforms"].values(), manifest["core_js"]]}
    return lambda url: (200, str(sizes[url]))


def test_completeness_passes_a_release_with_the_engine_asset() -> None:
    manifest, sums, digests = _published()
    assert vpr.manifest_problems(TAG, manifest, CONTRACT, sums, digests, _probe(manifest)) == []


@pytest.mark.parametrize("mutate, needle", [
    (lambda m, d: m.pop("core_js"), "no `core_js` entry"),
    (lambda m, d: d.update({ASSET: "ff" * 32}), "uploaded asset's digest"),
    (lambda m, d: m["core_js"].update(url=f"https://github.com/o/r/releases/download/v9.9.8/{ASSET}"), "pin-forward"),
    (lambda m, d: m["core_js"].update(node_floor=">=18"), "node_floor"),
    (lambda m, d: m["core_js"].update(sha256="aa" * 32), "!= SHA256SUMS.txt"),
])
def test_completeness_names_each_engine_asset_problem(mutate, needle: str) -> None:
    manifest, sums, digests = _published()
    probe = _probe(manifest)
    mutate(manifest, digests)
    problems = vpr.manifest_problems(TAG, manifest, CONTRACT, sums, digests, probe if "core_js" in manifest else lambda url: (200, None))
    assert any(needle in p for p in problems), problems


def test_completeness_needs_the_sums_line_and_a_reachable_url() -> None:
    manifest, sums, digests = _published()
    no_line = "\n".join(line for line in sums.splitlines() if ASSET not in line)
    assert any(f"does not list {ASSET}" in p for p in vpr.manifest_problems(TAG, manifest, CONTRACT, no_line, digests, _probe(manifest)))
    sizes = _probe(manifest)
    gone = lambda url: (404, None) if url.endswith(ASSET) else sizes(url)  # noqa: E731
    assert any("core_js url returned HTTP 404" in p for p in vpr.manifest_problems(TAG, manifest, CONTRACT, sums, digests, gone))


# ---------------------------------------------------------------- publish_release.sh + release-runtime.yml carry it

PUBLISH = (SCRIPTS / "publish_release.sh").read_text(encoding="utf-8")
RELEASE = (REPO_ROOT / ".github" / "workflows" / "release-runtime.yml").read_text(encoding="utf-8")


def _job(text: str, name: str) -> str:
    match = re.search(rf"^  {name}:\n(.*?)(?=^  [a-z_-]+:\n|\Z)", text, re.S | re.M)
    assert match, f"job {name} missing"
    return match.group(1)


def test_publish_script_builds_uploads_and_sums_the_asset() -> None:
    code = "\n".join(line for line in PUBLISH.splitlines() if not line.lstrip().startswith("#"))
    assert 'CORE_JS="horosa-core-js-${TAG}.tar.gz"' in code
    assert "build_core_js_asset.py" in code
    assert re.search(r'generate_release_manifest\.py.*?--core-js-archive "\$\{DIST\}/\$\{CORE_JS\}"', code, re.S)
    assert re.search(r'verify_runtime_release\.py.*?--core-js-archive "\$\{DIST\}/\$\{CORE_JS\}"', code, re.S)
    sums_line = next(line for line in code.splitlines() if "SHA256SUMS.txt" in line and "shasum" in line)
    assert '"${CORE_JS}"' in sums_line
    draft_assets = next(line for line in code.splitlines() if line.startswith("DRAFT_ASSETS="))
    assert '"${DIST}/${CORE_JS}"' in draft_assets and "runtime-manifest.json" not in draft_assets
    assert code.index("build_core_js_asset.py") < code.index("generate_release_manifest.py")


def test_pipeline_puts_the_drafts_asset_into_the_final_manifest_and_sums() -> None:
    resolve = _job(RELEASE, "resolve")
    assert "core_js: ${{ steps.info.outputs.core_js }}" in resolve and "core_js.since" in resolve
    assert 'has no ${CORE_JS}' in resolve, "a draft without the asset stops in resolve"
    assemble = _job(RELEASE, "assemble")
    assert '-p "${{ needs.resolve.outputs.core_js }}"' in assemble
    manifest_step = assemble.split("Dual-platform manifest", 1)[1].split("- name:", 1)[0]
    generate_call = manifest_step.split("generate_release_manifest.py", 1)[1].split("--output", 1)[0]
    assert '"${CORE_JS_ARGS[@]}"' in generate_call, "the generator call itself must get the asset"
    assert 'CORE_JS_ARGS=(--core-js-archive "dist/runtime/${CORE_JS}")' in manifest_step
    assert "horosa-core-js-*.tar.gz" in manifest_step.split("sha256sum", 1)[1], "SHA256SUMS covers the engine asset"
    verify_step = assemble.split("Verify the release set", 1)[1].split("- name:", 1)[0]
    verify_call = verify_step.split("verify_runtime_release.py", 1)[1].split("--expect-platforms", 1)[0]
    assert '"${CORE_JS_ARGS[@]}"' in verify_call and 'CORE_JS_ARGS=(--core-js-archive "${CORE_JS}")' in verify_step
    publish = _job(RELEASE, "publish")
    assert "sync_windows_release.py --check --tag" in publish, "the [GAP]/[OK] verdict (which now covers core_js) gates the flip"
