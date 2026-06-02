from __future__ import annotations

import json
import shutil
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = ROOT / "horosa-skill"
SOURCE_ROOT = ROOT / "vendor" / "runtime-source"
CORE_JS_ROOT = SKILL_ROOT / "horosa-core-js"
BUILD_ROOT = SKILL_ROOT / "build" / "runtime" / "windows"
DOWNLOAD_ROOT = BUILD_ROOT / "downloads"
PAYLOAD_ROOT = BUILD_ROOT / "runtime-payload"
DIST_ROOT = SKILL_ROOT / "dist" / "runtime"
TEMPLATE_ROOT = SKILL_ROOT / "scripts" / "runtime_templates" / "windows"


def read_version() -> str:
    import tomllib

    data = tomllib.loads((SKILL_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def require_path(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"missing required path: {path}")


def download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest
    subprocess.run(["curl", "-fL", url, "-o", str(dest)], check=True)
    return dest


def latest_node_win_url() -> str:
    completed = subprocess.run(
        ["curl", "-fsSL", "https://nodejs.org/dist/latest-v22.x/SHASUMS256.txt"],
        check=True,
        capture_output=True,
        text=True,
    )
    lines = completed.stdout.splitlines()
    for line in lines:
        if "win-x64.zip" in line:
            filename = line.split()[-1]
            return f"https://nodejs.org/dist/latest-v22.x/{filename}"
    raise SystemExit("could not resolve latest Node.js win-x64 zip")


def latest_temurin_asset_url(needle: str, suffix: str) -> str:
    completed = subprocess.run(
        ["curl", "-fsSL", "https://api.github.com/repos/adoptium/temurin17-binaries/releases/latest"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    for asset in payload.get("assets", []):
        name = asset.get("name", "")
        if needle in name and name.endswith(suffix):
            return asset["browser_download_url"]
    raise SystemExit(f"could not resolve Temurin asset for {needle}{suffix}")


def extract_zip_strip_first(archive: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        prefix = None
        for name in zf.namelist():
            clean = name.strip("/")
            if not clean:
                continue
            prefix = clean.split("/", 1)[0]
            break
        for member in zf.infolist():
            clean = member.filename.strip("/")
            if not clean:
                continue
            relative = clean.split("/", 1)[1] if prefix and clean.startswith(f"{prefix}/") and "/" in clean else clean
            if not relative:
                continue
            destination = target / relative
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, destination.open("wb") as dst:
                shutil.copyfileobj(src, dst)


def rsync_copy(src: Path, dst: Path, *, extra_excludes: list[str] | None = None) -> None:
    excludes = [
        ".DS_Store",
        "._*",
        "__pycache__",
        "*.pyc",
        "*.pyo",
        ".pytest_cache",
        ".cache",
        "*.map",
    ]
    if extra_excludes:
        excludes.extend(extra_excludes)
    # Portable equivalent of `rsync -a SRC DST/` (DST is a directory, SRC has no trailing
    # slash): copy SRC *into* DST, i.e. to DST/<src.name>, merging into any existing tree and
    # skipping the excluded names. Uses shutil rather than the rsync binary so the same builder
    # runs on Windows (which has no rsync) as well as macOS/Linux.
    target = dst / src.name
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, target, ignore=shutil.ignore_patterns(*excludes), dirs_exist_ok=True)


def _make_kentang_mount_graceful(registry_path: Path) -> None:
    """The bundled chart service ships only the qimen/taiyi/jinkou ken engines, but the
    upstream kentang registry lists many more. Patch the staged mount to skip any service
    whose engine is not bundled so the chart service still boots offline."""
    if not registry_path.is_file():
        return
    text = registry_path.read_text(encoding="utf-8")
    needle = (
        "def mount_kentang_services(cherrypy):\n"
        "    for spec in KENTANG_SERVICE_SPECS:\n"
        "        cherrypy.tree.mount(_load_service(spec), spec[\"mount\"])\n"
    )
    replacement = (
        "def mount_kentang_services(cherrypy):\n"
        "    import sys as _sys\n"
        "    for spec in KENTANG_SERVICE_SPECS:\n"
        "        try:\n"
        "            cherrypy.tree.mount(_load_service(spec), spec[\"mount\"])\n"
        "        except Exception as _exc:  # offline payload may omit some ken engines\n"
        "            print(f\"[kentang] skipping {spec.get('mount')}: {_exc}\", file=_sys.stderr)\n"
    )
    if needle in text:
        registry_path.write_text(text.replace(needle, replacement), encoding="utf-8")


def unpack_wheels(wheels_root: Path, site_packages: Path) -> None:
    site_packages.mkdir(parents=True, exist_ok=True)
    for wheel in sorted(wheels_root.glob("*.whl")):
        with zipfile.ZipFile(wheel) as zf:
            zf.extractall(site_packages)


def patch_embedded_python(runtime_root: Path) -> None:
    pth_path = next(runtime_root.glob("python*._pth"), None)
    if pth_path is None:
        raise SystemExit(f"missing python ._pth file under {runtime_root}")
    # Derive the stdlib zip name from the discovered ._pth (e.g. python311._pth -> python311.zip)
    # instead of hardcoding a version, so a future embed bump (3.11 -> 3.12) does not silently
    # point the interpreter at a non-existent zip and lose its stdlib.
    stdlib_zip = f"{pth_path.stem}.zip"
    pth_path.write_text(f"{stdlib_zip}\n.\nLib\nLib\\site-packages\nimport site\n", encoding="utf-8")


def write_manifest(version: str) -> None:
    manifest = {
        "schema_version": 1,
        "version": version,
        "platform": "win32-x64",
        "runtime_layout_version": 1,
        "runtime_payload_version": version,
        "export_registry_version": 6,
        "services": {
            "backend_url": "http://127.0.0.1:9999",
            "chart_url": "http://127.0.0.1:8899",
            "start_script": "Horosa-Web/start_horosa_local.ps1",
            "stop_script": "Horosa-Web/stop_horosa_local.ps1",
        },
        "runtimes": {
            "python": "runtime/windows/python/python.exe",
            "java": "runtime/windows/java/bin/java.exe",
            "node": "runtime/windows/node/node.exe",
        },
        "artifacts": {
            "horosa_web_root": "Horosa-Web",
            "astropy_root": "Horosa-Web/astropy",
            "flatlib_root": "Horosa-Web/flatlib-ctrad2/flatlib",
            "swefiles_root": "Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles",
            "boot_jar": "runtime/windows/bundle/astrostudyboot.jar",
            "horosa_core_js_root": "horosa-core-js",
        },
    }
    (PAYLOAD_ROOT / "runtime-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build() -> Path:
    version = read_version()
    archive_name = f"horosa-runtime-win32-x64-v{version}.zip"

    require_path(SOURCE_ROOT / "Horosa-Web" / "start_horosa_local.sh")
    require_path(SOURCE_ROOT / "Horosa-Web" / "astropy")
    require_path(SOURCE_ROOT / "Horosa-Web" / "flatlib-ctrad2")
    require_path(SOURCE_ROOT / "Horosa-Web" / "vendor" / "kinqimen")
    require_path(SOURCE_ROOT / "Horosa-Web" / "vendor" / "kintaiyi")
    require_path(SOURCE_ROOT / "Horosa-Web" / "vendor" / "kinjinkou")
    require_path(SOURCE_ROOT / "Horosa-Web" / "vendor" / "kinwangji")
    require_path(SOURCE_ROOT / "Horosa-Web" / "vendor" / "kinwuzhao")
    require_path(SOURCE_ROOT / "Horosa-Web" / "vendor" / "taixuanshifa")
    require_path(SOURCE_ROOT / "Horosa-Web" / "vendor" / "jingjue")
    require_path(SOURCE_ROOT / "Horosa-Web" / "vendor" / "shenyishu")
    require_path(SOURCE_ROOT / "Horosa-Web" / "astrostudyui" / "dist-file")
    require_path(SOURCE_ROOT / "Horosa-Web" / "astrostudyui" / "scripts" / "warmHorosaRuntime.js")
    require_path(SOURCE_ROOT / "Horosa-Web" / "scripts" / "repairEmbeddedPythonRuntime.py")
    require_path(SOURCE_ROOT / "runtime" / "mac" / "bundle" / "astrostudyboot.jar")
    require_path(SOURCE_ROOT / "runtime" / "windows" / "bundle" / "wheels")
    require_path(CORE_JS_ROOT / "bin" / "cli.mjs")

    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT)
    PAYLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    DIST_ROOT.mkdir(parents=True, exist_ok=True)

    horosa_web_root = PAYLOAD_ROOT / "Horosa-Web"
    (horosa_web_root / "astrostudyui" / "scripts").mkdir(parents=True, exist_ok=True)
    (horosa_web_root / "scripts").mkdir(parents=True, exist_ok=True)

    rsync_copy(SOURCE_ROOT / "Horosa-Web" / "astropy", horosa_web_root / "")
    # ken engines for the chart-service qimen/taiyi/jinkou mounts + the 5 standalone 神数 engines.
    (horosa_web_root / "vendor").mkdir(parents=True, exist_ok=True)
    for ken_engine in ("kinqimen", "kintaiyi", "kinjinkou", "kinwangji", "kinwuzhao", "taixuanshifa", "jingjue", "shenyishu"):
        rsync_copy(SOURCE_ROOT / "Horosa-Web" / "vendor" / ken_engine, horosa_web_root / "vendor" / "")
    # kinastro engine for the 9 kinastro-* 神数 (engine only; drop tools/cities + streamlit ui/docs).
    if (SOURCE_ROOT / "Horosa-Web" / "vendor" / "kinastro").is_dir():
        rsync_copy(
            SOURCE_ROOT / "Horosa-Web" / "vendor" / "kinastro",
            horosa_web_root / "vendor" / "",
            extra_excludes=["tools", "ui", "frontend", "docs", "wiki", "examples", "tests", "styles", "scripts", ".streamlit", ".github", ".devcontainer", ".git"],
        )
    _make_kentang_mount_graceful(horosa_web_root / "astropy" / "websrv" / "kentang" / "registry.py")
    rsync_copy(SOURCE_ROOT / "Horosa-Web" / "flatlib-ctrad2" / "flatlib", horosa_web_root / "flatlib-ctrad2" / "")
    if (SOURCE_ROOT / "Horosa-Web" / "flatlib-ctrad2" / "LICENSE").is_file():
        (horosa_web_root / "flatlib-ctrad2").mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE_ROOT / "Horosa-Web" / "flatlib-ctrad2" / "LICENSE", horosa_web_root / "flatlib-ctrad2" / "LICENSE")
    rsync_copy(
        SOURCE_ROOT / "Horosa-Web" / "astrostudyui" / "dist-file",
        horosa_web_root / "astrostudyui" / "",
        extra_excludes=["fengshui"],
    )
    shutil.copy2(SOURCE_ROOT / "Horosa-Web" / "astrostudyui" / "scripts" / "warmHorosaRuntime.js", horosa_web_root / "astrostudyui" / "scripts" / "warmHorosaRuntime.js")
    shutil.copy2(SOURCE_ROOT / "Horosa-Web" / "scripts" / "repairEmbeddedPythonRuntime.py", horosa_web_root / "scripts" / "repairEmbeddedPythonRuntime.py")
    shutil.copy2(TEMPLATE_ROOT / "start_horosa_local.ps1", horosa_web_root / "start_horosa_local.ps1")
    shutil.copy2(TEMPLATE_ROOT / "stop_horosa_local.ps1", horosa_web_root / "stop_horosa_local.ps1")

    runtime_windows_root = PAYLOAD_ROOT / "runtime" / "windows"
    (runtime_windows_root / "bundle").mkdir(parents=True, exist_ok=True)

    java_archive = download(
        latest_temurin_asset_url("OpenJDK17U-jdk_x64_windows_hotspot_", ".zip"),
        DOWNLOAD_ROOT / "OpenJDK17U-jdk_x64_windows_hotspot.zip",
    )
    python_archive = download(
        "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip",
        DOWNLOAD_ROOT / "python-3.11.9-embed-amd64.zip",
    )
    node_archive = download(
        latest_node_win_url(),
        DOWNLOAD_ROOT / "node-win-x64.zip",
    )

    extract_zip_strip_first(java_archive, runtime_windows_root / "java")
    extract_zip_strip_first(node_archive, runtime_windows_root / "node")
    (runtime_windows_root / "python").mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(python_archive) as zf:
        zf.extractall(runtime_windows_root / "python")
    patch_embedded_python(runtime_windows_root / "python")
    unpack_wheels(SOURCE_ROOT / "runtime" / "windows" / "bundle" / "wheels", runtime_windows_root / "python" / "Lib" / "site-packages")

    shutil.copy2(SOURCE_ROOT / "runtime" / "mac" / "bundle" / "astrostudyboot.jar", runtime_windows_root / "bundle" / "astrostudyboot.jar")

    # canping/heluo compute their four pillars in-process via the vendored bazi chain, which imports
    # the `lunar-javascript` npm package. Install the production dep so the core-js copy below bundles
    # node_modules into the payload. Without it, a clean Windows build ships a runtime where
    # canping/heluo throw "Cannot find package 'lunar-javascript'" at runtime.
    print("installing horosa-core-js production deps (lunar-javascript)…")
    npm_cmd = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm_cmd:
        raise SystemExit("npm not found on PATH; install Node.js so horosa-core-js deps (lunar-javascript) can be bundled")
    subprocess.run(
        [npm_cmd, "install", "--omit=dev", "--no-audit", "--no-fund", "--loglevel=error"],
        cwd=str(CORE_JS_ROOT),
        check=True,
    )
    require_path(CORE_JS_ROOT / "node_modules" / "lunar-javascript" / "package.json")
    rsync_copy(CORE_JS_ROOT, PAYLOAD_ROOT / "")

    write_manifest(version)

    archive_path = DIST_ROOT / archive_name
    if archive_path.exists():
        archive_path.unlink()
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(PAYLOAD_ROOT.rglob("*")):
            if path.is_dir():
                continue
            zf.write(path, path.relative_to(BUILD_ROOT))
    return archive_path


if __name__ == "__main__":
    archive = build()
    print(f"runtime payload ready: {archive}")
