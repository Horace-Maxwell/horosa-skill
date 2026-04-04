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
    cmd = ["rsync", "-a"]
    for pattern in excludes:
        cmd.append(f"--exclude={pattern}")
    cmd.extend([str(src), str(dst)])
    subprocess.run(cmd, check=True)


def unpack_wheels(wheels_root: Path, site_packages: Path) -> None:
    site_packages.mkdir(parents=True, exist_ok=True)
    for wheel in sorted(wheels_root.glob("*.whl")):
        with zipfile.ZipFile(wheel) as zf:
            zf.extractall(site_packages)


def patch_embedded_python(runtime_root: Path) -> None:
    pth_path = next(runtime_root.glob("python*._pth"), None)
    if pth_path is None:
        raise SystemExit(f"missing python ._pth file under {runtime_root}")
    pth_path.write_text("python311.zip\n.\nLib\nLib\\site-packages\nimport site\n", encoding="utf-8")


def write_manifest(version: str) -> None:
    manifest = {
        "schema_version": 1,
        "version": version,
        "platform": "win32-x64",
        "runtime_layout_version": 1,
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
