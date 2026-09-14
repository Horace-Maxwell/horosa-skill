from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

# Windows 控制台默认 cp1252/cp936：脚本自己 print 的中文会抛 UnicodeEncodeError 并让脚本 exit 1
# （v0.38.0 的 repack 脚本在「打印成功信息」那一步失败过）。统一在入口把两条流改成 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")
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
    """Fetch *url* to *dest*, reusing a cached copy only when it came from the same URL.

    The cache (DOWNLOAD_ROOT) now survives rebuilds, so two things it used to get for free from the
    wipe have to be earned: (1) a cached file is only reused when the sidecar records the *same*
    resolved URL — a fixed filename would otherwise pin the first JDK/Node we ever downloaded and
    silently keep shipping it after a new release lands; (2) the download is staged through a
    `.part` file so an interrupted curl can never leave a truncated archive posing as a cache hit.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    stamp = dest.with_name(dest.name + ".url")
    if dest.is_file() and stamp.is_file() and stamp.read_text(encoding="utf-8").strip() == url:
        print(f"reusing cached download: {dest.name}")
        return dest
    partial = dest.with_name(dest.name + ".part")
    partial.unlink(missing_ok=True)
    subprocess.run(["curl", "-fL", url, "-o", str(partial)], check=True)
    partial.replace(dest)
    stamp.write_text(url, encoding="utf-8")
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


TEMURIN_JDK_API = "https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jdk/hotspot/normal/eclipse"


def latest_temurin_jdk_url() -> str:
    # Adoptium's own API redirects to the newest GA JDK whose windows/x64 binary actually exists.
    # GitHub `releases/latest` on temurin17-binaries picks by tag commit date, so during the hours
    # after a GA tag lands it can point at a release with zero platform assets (jdk-17.0.20-ga did).
    # Resolve the redirect so the returned URL carries the JDK version: the API URL itself is
    # constant across GA releases, which would make the download cache pin whichever JDK it first
    # saw. Fall back to the API URL (still correct, just not cache-keyable) if the probe fails.
    try:
        head = subprocess.run(
            ["curl", "-fsI", TEMURIN_JDK_API], check=True, capture_output=True, text=True, timeout=60
        )
        for line in head.stdout.splitlines():
            if line.lower().startswith("location:"):
                target = line.split(":", 1)[1].strip()
                if target.endswith(".zip"):
                    return target
    except (subprocess.SubprocessError, OSError):
        pass
    return TEMURIN_JDK_API


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
        # SQLite 运行期日志侧车：非源文件；非空 WAL 打进包 = runtime 打开库时回放上游未 checkpoint 的写入。
        "*.sqlite-wal",
        "*.sqlite-shm",
        "*.sqlite-journal",
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
    # newline="\n": this script runs natively on Windows; without it write_text translates \n -> \r\n,
    # breaking the LF byte-parity the release artifacts are held to (._pth itself tolerates CRLF, the
    # cross-platform reproducibility gate does not).
    pth_path.write_text(f"{stdlib_zip}\n.\nLib\nLib\\site-packages\nimport site\n", encoding="utf-8", newline="\n")


def write_manifest(version: str) -> None:
    manifest = {
        "schema_version": 1,
        "version": version,
        "platform": "win32-x64",
        "runtime_layout_version": 1,
        "runtime_payload_version": version,
        "export_registry_version": 14,
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
    require_path(SOURCE_ROOT / "Horosa-Web" / "vendor" / "kin_year_domain.py")
    require_path(SOURCE_ROOT / "Horosa-Web" / "astrostudyui" / "dist-file")
    require_path(SOURCE_ROOT / "Horosa-Web" / "astrostudyui" / "scripts" / "warmHorosaRuntime.js")
    require_path(SOURCE_ROOT / "Horosa-Web" / "scripts" / "repairEmbeddedPythonRuntime.py")
    require_path(SOURCE_ROOT / "runtime" / "mac" / "bundle" / "astrostudyboot.jar")
    require_path(SOURCE_ROOT / "runtime" / "windows" / "bundle" / "wheels")
    require_path(CORE_JS_ROOT / "bin" / "cli.mjs")

    # Wipe the staging tree only — DOWNLOAD_ROOT is a sibling inside BUILD_ROOT, and nuking the whole
    # BUILD_ROOT re-downloaded the JDK (~180 MB) + Node + CPython on every rebuild, which on a slow
    # link cost an hour per launcher/template tweak. `download()` keys each cached file by its
    # resolved URL and stages through `.part`, so a preserved cache can neither go stale nor be
    # poisoned by an interrupted transfer.
    if PAYLOAD_ROOT.exists():
        shutil.rmtree(PAYLOAD_ROOT)
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
    # v3.5.0 全年份域 shared module (sibling of the engine dirs, missed by the loop) — copy explicitly.
    # shutil.copy2 (no POSIX rsync/cp/tar per §6). Missing it → ken/神数 engines 500 on first BC/远期 request.
    shutil.copy2(SOURCE_ROOT / "Horosa-Web" / "vendor" / "kin_year_domain.py", horosa_web_root / "vendor" / "kin_year_domain.py")
    # kinastro engine for the 9 kinastro-* 神数 (engine only; drop tools/cities + streamlit ui/docs).
    if (SOURCE_ROOT / "Horosa-Web" / "vendor" / "kinastro").is_dir():
        rsync_copy(
            SOURCE_ROOT / "Horosa-Web" / "vendor" / "kinastro",
            horosa_web_root / "vendor" / "",
            extra_excludes=["tools", "ui", "frontend", "docs", "wiki", "examples", "tests", "styles", "scripts", ".streamlit", ".github", ".devcontainer", ".git"],
        )
        # 邵子神数: upstream ships only the verse CSV (no shaozi_tiaowen_6144.json), so without the
        # generated JSON 邵子 readings come back with placeholder verses. Generate the JSON the engine
        # expects into the staged payload (parity with package_runtime_payload.sh). gen_shaozi_tiaowen.py
        # is stdlib-only and a no-op if the CSV is absent; it never touches the 星阙 source tree.
        shaozi_data = horosa_web_root / "vendor" / "kinastro" / "astro" / "shaozi" / "data"
        if (shaozi_data / "shaozi_tiaowen.csv").is_file():
            subprocess.run(
                [sys.executable, str(SKILL_ROOT / "scripts" / "gen_shaozi_tiaowen.py"), str(shaozi_data)],
                check=True,
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
        latest_temurin_jdk_url(),
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
    win_site_packages = runtime_windows_root / "python" / "Lib" / "site-packages"
    unpack_wheels(SOURCE_ROOT / "runtime" / "windows" / "bundle" / "wheels", win_site_packages)

    # Drop plotly (~40 MB): it is required ONLY by streamlit (lazy import for st.plotly_chart, never hit
    # by the headless 神数 compute path), while pyarrow/pandas are astropy deps and MUST stay. Parity with
    # package_runtime_payload.sh (verified there: streamlit import + cetian snapshot + astropy.units all
    # OK without it). The §4 native check (cetian/qizhengkin snapshots) re-confirms it on Windows.
    for plotly_path in list(win_site_packages.glob("plotly")) + list(win_site_packages.glob("plotly-*.dist-info")):
        shutil.rmtree(plotly_path, ignore_errors=True)

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


# --- seed + derive mode (v0.38.0 A2) ---------------------------------------------------------------
# `--seed <darwin-arm64 tar.gz>`: no vendor/runtime-source, no npm, no Windows box. The platform-independent
# tree comes from the live-tested seed; only the JDK / Node / embedded CPython / native wheels are fetched
# for win32-x64 (pinned in contracts/runtime_toolchain.json) or built from sdist on the target runner
# (pyswisseph, sxtwl: no cp312 Windows wheels on PyPI — see contracts/runtime_python_lock.json). The
# vendor mode above stays intact as the Windows-box fallback.


def _seed_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("horosa_runtime_seed", SKILL_ROOT / "scripts" / "runtime_seed.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def download_pinned(url: str, dest: Path, sha256: str | None) -> Path:
    """`download()` plus a sha256 check: a pinned toolchain that is not verified is a pin in name only."""
    path = download(url, dest)
    if sha256:
        import hashlib

        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        if digest.hexdigest() != sha256:
            path.unlink(missing_ok=True)
            path.with_name(path.name + ".url").unlink(missing_ok=True)
            raise SystemExit(f"{path.name}: sha256 {digest.hexdigest()} != pinned {sha256} (contracts/runtime_toolchain.json)")
    return path


def download_toolchain(toolchain: dict, *, resolve_latest: bool = False) -> dict[str, Path]:
    """JDK / embedded Python / Node archives for win32-x64, pinned URL + sha unless --resolve-latest."""
    jdk = toolchain["java"]["windows_x64_jdk"]
    py = toolchain["python"]["embed_windows_x64"]
    node = toolchain["node"]["windows_x64"]
    if resolve_latest:
        return {
            "jdk": download(latest_temurin_jdk_url(), DOWNLOAD_ROOT / "OpenJDK17U-jdk_x64_windows_hotspot-latest.zip"),
            "python": download_pinned(py["url"], DOWNLOAD_ROOT / py["url"].rsplit("/", 1)[-1], py.get("sha256")),
            "node": download(latest_node_win_url(), DOWNLOAD_ROOT / "node-win-x64-latest.zip"),
        }
    return {
        "jdk": download_pinned(jdk["url"], DOWNLOAD_ROOT / jdk["name"], jdk.get("sha256")),
        "python": download_pinned(py["url"], DOWNLOAD_ROOT / py["url"].rsplit("/", 1)[-1], py.get("sha256")),
        "node": download_pinned(node["url"], DOWNLOAD_ROOT / node["name"], node.get("sha256")),
    }


def _lock_without_sdist(lock: dict, platform_key: str) -> dict:
    sources = (lock.get("wheel_sources") or {}).get(platform_key, {})
    import re as _re

    def norm(name: str) -> str:
        return _re.sub(r"[-_.]+", "-", name).lower()

    trimmed = json.loads(json.dumps(lock))
    trimmed["native"] = [r for r in lock["native"] if sources.get(norm(r.split("==")[0])) != "sdist"]
    return trimmed


def stage_from_seed(seed, tree, lock: dict, toolchain: dict, payload_root: Path, *, downloads: dict[str, Path],
                    python: str | None = None, jlink: bool = True, skip_sdist: bool = False,
                    jlink_bin: Path | None = None) -> dict:
    """Assemble a win32-x64 payload tree from the seed tree + downloaded toolchain. Returns a summary."""
    platform_key = "win32-x64"
    os_dir = "windows"
    if payload_root.exists():
        shutil.rmtree(payload_root)
    payload_root.mkdir(parents=True, exist_ok=True)
    seed.copy_platform_tree(tree, payload_root, launchers="ps1", os_dir=os_dir)
    horosa_web = payload_root / "Horosa-Web"
    # the repo's launcher templates (UTF-8 BOM, loopback bind, quoted path args) — copy2 keeps bytes as-is
    shutil.copy2(TEMPLATE_ROOT / "start_horosa_local.ps1", horosa_web / "start_horosa_local.ps1")
    shutil.copy2(TEMPLATE_ROOT / "stop_horosa_local.ps1", horosa_web / "stop_horosa_local.ps1")
    runtime_root = payload_root / "runtime" / os_dir
    runtime_root.mkdir(parents=True, exist_ok=True)

    # Java: pinned Temurin JDK → jlink to the same 17 modules the mac packager uses (or the full JDK)
    jdk_extract = payload_root.parent / "seed-jdk"
    if jdk_extract.exists():
        shutil.rmtree(jdk_extract)
    extract_zip_strip_first(downloads["jdk"], jdk_extract)
    jdk_home = seed.find_jdk_home(jdk_extract)
    if jlink:
        seed.jlink_image(jdk_home, runtime_root / "java", list(toolchain["java"]["jlink_modules"]), jlink_bin=jlink_bin)
    else:
        shutil.copytree(jdk_home, runtime_root / "java", dirs_exist_ok=True)

    # Python: pinned embeddable CPython + the seed's pure dists + native wheels for win_amd64
    py_root = runtime_root / "python"
    py_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(downloads["python"]) as zf:
        zf.extractall(py_root)
    patch_embedded_python(py_root)
    site = py_root / "Lib" / "site-packages"
    pure = seed.copy_pure_site_packages(tree, lock, site)
    wheels_dir = payload_root.parent / "seed-wheels" / platform_key
    if wheels_dir.exists():
        shutil.rmtree(wheels_dir)
    fetch_lock = _lock_without_sdist(lock, platform_key) if skip_sdist else lock
    wheels = seed.fetch_native_wheels(fetch_lock, platform_key, wheels_dir, python=python, build_from_sdist=not skip_sdist)
    unpack_wheels(wheels_dir, site)
    # plotly never enters a derived payload (the seed is already stripped; kept for builder parity)
    for plotly_path in list(site.glob("plotly")) + list(site.glob("plotly-*.dist-info")):
        shutil.rmtree(plotly_path, ignore_errors=True)

    # Node: pinned win-x64 zip
    extract_zip_strip_first(downloads["node"], runtime_root / "node")

    # 🔴 arch guard: a derived payload must never carry the seed's arm64 binaries
    for rel in ("python/python.exe", "java/bin/java.exe", "node/node.exe"):
        seed.assert_binary_arch(runtime_root / rel, "x86_64")
    numpy_ext = next(site.glob("numpy/_core/_multiarray_umath*.pyd"), None)
    if numpy_ext is not None:
        seed.assert_binary_arch(numpy_ext, "x86_64")

    manifest = seed.derive_manifest(
        tree.manifest, platform=platform_key,
        runtimes={"python": f"runtime/{os_dir}/python/python.exe", "java": f"runtime/{os_dir}/java/bin/java.exe", "node": f"runtime/{os_dir}/node/node.exe"},
        boot_jar=f"runtime/{os_dir}/bundle/astrostudyboot.jar",
        start_script="Horosa-Web/start_horosa_local.ps1", stop_script="Horosa-Web/stop_horosa_local.ps1",
        platform_requirements={"arch": "x86_64", "min_os": toolchain["platforms"][platform_key].get("min_os")},
    )
    (payload_root / "runtime-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"version": manifest["version"], "pure_dists": len(pure), "native_wheels": sorted(wheels), "jlink": jlink, "skip_sdist": skip_sdist}


NATIVE_SMOKE_IMPORTS = "numpy, pandas, pyarrow, astropy, swisseph, sxtwl, ephem, pendulum, kerykeion, cherrypy, streamlit, bidict, cnlunar, cn2an"


def native_smoke(payload_root: Path) -> bool:
    """Only meaningful on Windows (the payload's binaries are x64 Windows): import every native-backed dep,
    print java/node versions. Elsewhere it is deferred to the runtime matrix."""
    if os.name != "nt":
        print("cross build — native smoke deferred to runtime-matrix (this host cannot run x64 Windows binaries)")
        return False
    runtime_root = payload_root / "runtime" / "windows"
    subprocess.run([str(runtime_root / "python" / "python.exe"), "-c", f"import {NATIVE_SMOKE_IMPORTS}; print('imports ok')"], check=True)
    subprocess.run([str(runtime_root / "java" / "bin" / "java.exe"), "-version"], check=True)
    subprocess.run([str(runtime_root / "node" / "node.exe"), "-v"], check=True)
    return True


def write_archive(payload_root: Path, archive_path: Path) -> Path:
    """zip DEFLATE 6 with `runtime-payload/…` entry names; copy2'd .ps1 keep their BOM byte for byte."""
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        archive_path.unlink()
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(payload_root.rglob("*")):
            if path.is_dir():
                continue
            zf.write(path, path.relative_to(payload_root.parent))
    return archive_path


def build_from_seed(args) -> Path:
    seed = _seed_module()
    lock = seed.load_lock(args.lock)
    toolchain = seed.load_toolchain(args.toolchain)
    seed_manifest = seed.verify_seed(args.seed)
    seed_version = str(seed_manifest["version"])
    if seed_version != read_version():
        print(f"note: seed is v{seed_version}, pyproject is v{read_version()} — the derived payload carries the seed's version")
    tree = seed.materialize_seed(args.seed, BUILD_ROOT / "seed")
    downloads = download_toolchain(toolchain, resolve_latest=args.resolve_latest)
    jlink_bin = None
    if not args.full_jdk and os.name != "nt":
        jlink_bin = seed.host_jlink(int(toolchain["java"]["major"]))
        if jlink_bin is None:
            raise SystemExit(f"no host jlink of major {toolchain['java']['major']} for cross-linking; pass --full-jdk or build on Windows")
    summary = stage_from_seed(seed, tree, lock, toolchain, PAYLOAD_ROOT, downloads=downloads, python=args.python,
                              jlink=not args.full_jdk, skip_sdist=args.skip_sdist_builds, jlink_bin=jlink_bin)
    if not args.skip_native_smoke:
        native_smoke(PAYLOAD_ROOT)
    suffix = "-DRYRUN" if args.skip_sdist_builds else ""
    out_dir = args.out_dir or DIST_ROOT
    archive = write_archive(PAYLOAD_ROOT, out_dir / f"horosa-runtime-win32-x64-v{seed_version}{suffix}.zip")
    print(json.dumps({"archive": str(archive), **summary}, ensure_ascii=False, indent=2))
    return archive


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Build the win32-x64 runtime payload (vendor mode by default; --seed derives from a darwin-arm64 seed).")
    ap.add_argument("--seed", type=Path, default=None, help="darwin-arm64 runtime archive to derive from (hosted mode)")
    ap.add_argument("--lock", type=Path, default=None, help="contracts/runtime_python_lock.json override")
    ap.add_argument("--toolchain", type=Path, default=None, help="contracts/runtime_toolchain.json override")
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--python", default=None, help="interpreter with pip used for `pip download` / `pip wheel` (default: this one)")
    ap.add_argument("--full-jdk", action="store_true", help="copy the whole JDK instead of jlinking the pinned module set")
    ap.add_argument("--resolve-latest", action="store_true", help="ignore the toolchain pins and resolve latest JDK/Node (dev only)")
    ap.add_argument("--skip-sdist-builds", action="store_true", help="dry run on a non-Windows host: skip dists that must be built from sdist (archive gets a -DRYRUN suffix)")
    ap.add_argument("--skip-native-smoke", action="store_true")
    args = ap.parse_args(argv)
    if args.seed is None:
        archive = build()
        print(f"runtime payload ready: {archive}")
        return 0
    build_from_seed(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
