"""Build the Linux (linux-x64) Horosa runtime payload archive.

This script is the Linux counterpart of ``build_runtime_release_windows.py``.
It downloads Linux-specific binaries (Java JRE via jlink, Python standalone,
Node.js) from official sources, assembles the shared Horosa-Web assets from
``vendor/runtime-source/``, and produces a ``tar.gz`` archive ready for
GitHub Releases.

Python runtime
  Uses ``python-build-standalone`` (by astral-sh / uv authors) — a pre-compiled,
  relocatable CPython 3.12 for Linux x64. This avoids the build-from-source
  requirement of python.org tarballs and is compatible with ``manylinux2014+``
  wheels needed by ``swisseph`` and the chart service. Chart-service dependencies
  are installed via ``pip install`` after extraction (or from a local
  ``wheels/`` directory if provided).

Usage::

    # Make sure vendor/runtime-source/ is populated first, then:
    python scripts/build_runtime_release_linux.py

Environment variables (optional):

    ``HOROSA_LINUX_JAVA_HOME``
        Path to a local JDK installation to use for ``jlink`` instead of
        downloading one.  The JDK must be a Linux x64 build.
    ``HOROSA_LINUX_PYTHON_HOME``
        Path to a local portable Python installation to use instead of
        downloading from ``python-build-standalone``.
    ``HOROSA_LINUX_SKIP_DOWNLOAD``
        Set to ``1`` to skip downloading runtimes (useful when iterating on
        the payload layout with pre-staged files).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = ROOT / "horosa-skill"
SOURCE_ROOT = ROOT / "vendor" / "runtime-source"
CORE_JS_ROOT = SKILL_ROOT / "horosa-core-js"
BUILD_ROOT = SKILL_ROOT / "build" / "runtime" / "linux"
DOWNLOAD_ROOT = BUILD_ROOT / "downloads"
PAYLOAD_ROOT = BUILD_ROOT / "runtime-payload"
DIST_ROOT = SKILL_ROOT / "dist" / "runtime"


def read_version() -> str:
    """Read the project version from pyproject.toml."""
    import tomllib

    data = tomllib.loads((SKILL_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def require_path(path: Path) -> None:
    """Exit with an error message if *path* does not exist."""
    if not path.exists():
        raise SystemExit(f"missing required path: {path}")


def download(url: str, dest: Path) -> Path:
    """Download *url* to *dest* via ``curl``, skipping if the file already exists."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest
    subprocess.run(["curl", "-fL", url, "-o", str(dest)], check=True)
    return dest


def latest_node_linux_url() -> str:
    """Resolve the latest Node.js v22.x linux-x64 binary archive URL."""
    completed = subprocess.run(
        ["curl", "-fsSL", "https://nodejs.org/dist/latest-v22.x/SHASUMS256.txt"],
        check=True,
        capture_output=True,
        text=True,
    )
    lines = completed.stdout.splitlines()
    for line in lines:
        if "linux-x64.tar.gz" in line:
            filename = line.split()[-1]
            return f"https://nodejs.org/dist/latest-v22.x/{filename}"
    raise SystemExit("could not resolve latest Node.js linux-x64 archive")


def latest_temurin_jdk_url() -> str:
    """Resolve the latest Adoptium Temurin 17 JDK linux-x64 tar.gz URL."""
    completed = subprocess.run(
        ["curl", "-fsSL", "https://api.github.com/repos/adoptium/temurin17-binaries/releases/latest"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    for asset in payload.get("assets", []):
        name = asset.get("name", "")
        if "OpenJDK17U-jdk_x64_linux_hotspot_" in name and name.endswith(".tar.gz"):
            return asset["browser_download_url"]
    raise SystemExit("could not resolve Temurin 17 JDK linux-x64 asset")


def extract_tar_strip_first(archive: Path, target: Path) -> None:
    """Extract a tar.gz archive, stripping the top-level directory."""
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tf:
        # Determine the top-level prefix
        prefix = None
        for member in tf.getmembers():
            name = member.name.strip("/")
            if not name:
                continue
            prefix = name.split("/", 1)[0]
            break
        for member in tf.getmembers():
            name = member.name.strip("/")
            if not name:
                continue
            relative = name.split("/", 1)[1] if prefix and name.startswith(f"{prefix}/") and "/" in name else name
            if not relative:
                continue
            destination = target / relative
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tf.extractfile(member) as src:
                if src is None:
                    continue
                with destination.open("wb") as dst:
                    shutil.copyfileobj(src, dst)


def make_embedded_java_runtime(
    jdk_source: Path,
    dest: Path,
    *,
    jlink_modules: str = (
        "java.base,java.desktop,java.instrument,java.logging,java.management,"
        "java.naming,java.net.http,java.prefs,java.scripting,java.security.jgss,"
        "java.sql,java.xml,jdk.charsets,jdk.crypto.ec,jdk.management,jdk.unsupported,jdk.zipfs"
    ),
) -> None:
    """Use ``jlink`` to create a minimal JRE from the JDK."""
    jlink_bin = jdk_source / "bin" / "jlink"
    jmods_dir = jdk_source / "jmods"
    if not jlink_bin.is_file() or not jmods_dir.is_dir():
        raise SystemExit(
            f"JDK at {jdk_source} missing jlink or jmods; "
            "make sure HOROSA_LINUX_JAVA_HOME points to a full JDK (not a JRE)"
        )
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            str(jlink_bin),
            "--module-path", str(jmods_dir),
            "--add-modules", jlink_modules,
            "--strip-debug",
            "--no-header-files",
            "--no-man-pages",
            "--output", str(dest),
        ],
        check=True,
    )


_STANDALONE_PYTHON_RELEASE = (
    "https://github.com/astral-sh/python-build-standalone/releases/download/"
    "20250115/cpython-3.12.8+20250115-x86_64-unknown-linux-gnu-install_only.tar.gz"
)


def _install_standalone_python(runtime_linux_root: Path) -> None:
    """Download and extract a portable Python 3.12 from ``python-build-standalone``.

    ``python-build-standalone`` (by astral-sh, the uv authors) provides pre-compiled,
    relocatable CPython builds for Linux x64. The extracted layout is:

        runtime/linux/python/
        ├── bin/
        │   └── python3
        ├── lib/
        └── include/

    These builds include ``pip`` and are compatible with ``manylinux2014+`` wheels,
    which is sufficient for ``swisseph``, ``numpy``, and other chart-service dependencies.
    """
    archive_name = _STANDALONE_PYTHON_RELEASE.rsplit("/", 1)[-1]
    python_archive = DOWNLOAD_ROOT / archive_name
    if not python_archive.is_file():
        subprocess.run(
            ["curl", "-fL", _STANDALONE_PYTHON_RELEASE, "-o", str(python_archive)],
            check=True,
        )

    # Extract directly into runtime/linux/python (the archive has no top-level dir)
    python_dest = runtime_linux_root / "python"
    python_dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(python_archive, "r:gz") as tf:
        tf.extractall(path=python_dest)

    # Make the python3 binary executable
    python_bin = python_dest / "bin" / "python3"
    if not python_bin.is_file():
        # In some builds the binary is just `python` — symlink it
        python_bin_alt = python_dest / "bin" / "python"
        if python_bin_alt.is_file():
            python_bin_alt.chmod(0o755)
            python_bin.symlink_to("python")
        else:
            print(
                f"WARNING: python3 binary not found in {python_dest / 'bin'}; "
                "ensure HOROSA_LINUX_PYTHON_HOME points to a valid standalone Python"
            )
    else:
        python_bin.chmod(0o755)

    print(f"standalone Python 3.12 installed at {python_dest}")

    # Install chart-service dependencies via pip
    # python-build-standalone ships pip, so we can install manylinux wheels directly.
    _install_chart_deps(python_dest)


_CHART_DEPS = [
    "swisseph",
    "numpy",
    "pyephem",
    "cherrypy",
    "pendulum",
    "kerykeion",
    "bidict",
    "httpx",
    "pydantic",
]


def _install_chart_deps(python_root: Path) -> None:
    """Install chart-service Python dependencies into the standalone Python runtime.

    First checks for a pre-bundled ``wheels/`` directory at
    ``vendor/runtime-source/runtime/linux/bundle/wheels/`` (same pattern as the
    Windows build), falling back to ``pip install`` from PyPI.
    """
    pip_bin = python_root / "bin" / "pip"
    if not pip_bin.is_file():
        pip_bin = python_root / "bin" / "pip3"
    if not pip_bin.is_file():
        print("WARNING: pip not found in standalone Python; chart deps must be installed manually")
        return

    wheels_dir = SOURCE_ROOT / "runtime" / "linux" / "bundle" / "wheels"
    if wheels_dir.is_dir() and list(wheels_dir.glob("*.whl")):
        print(f"installing chart deps from local wheels at {wheels_dir} …")
        subprocess.run(
            [str(pip_bin), "install", "--no-index", "--find-links", str(wheels_dir), *_CHART_DEPS],
            check=True,
        )
    else:
        print("installing chart deps from PyPI (manylinux wheels) …")
        subprocess.run(
            [str(pip_bin), "install", *_CHART_DEPS],
            check=True,
        )
    print("chart-service Python dependencies installed")


def _gen_shaozi_tiaowen(horosa_web_root: Path) -> None:
    """Generate the 邵子神数 verse JSON from the CSV shipped in the vendor source.

    Without this JSON the 邵子 engine emits placeholder verses at runtime — the same
    issue that affected the early Windows builds (see CHANGELOG v0.10.0 notes).
    """
    csv_path = horosa_web_root / "vendor" / "kinastro" / "astro" / "shaozi" / "data" / "shaozi_tiaowen.csv"
    if not csv_path.is_file():
        print("WARNING: shaozi_tiaowen.csv not found; 邵子神数 will emit placeholder verses")
        return
    gen_script = SKILL_ROOT / "scripts" / "gen_shaozi_tiaowen.py"
    if not gen_script.is_file():
        print("WARNING: gen_shaozi_tiaowen.py not found; skipping 邵子神数 verse generation")
        return
    json_path = csv_path.with_name("shaozi_tiaowen_6144.json")
    subprocess.run(
        [sys.executable, str(gen_script), str(csv_path)],
        check=True,
    )
    if json_path.is_file():
        print(f"邵子神数 verse JSON generated at {json_path}")
    else:
        print(f"WARNING: 邵子神数 verse JSON not found after generation at {json_path}")


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
    target = dst / src.name
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, target, ignore=shutil.ignore_patterns(*excludes), dirs_exist_ok=True)


def _make_kentang_mount_graceful(registry_path: Path) -> None:
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


def write_manifest(version: str) -> None:
    manifest = {
        "schema_version": 1,
        "version": version,
        "platform": "linux-x64",
        "runtime_layout_version": 1,
        "runtime_payload_version": version,
        "export_registry_version": 6,
        "services": {
            "backend_url": "http://127.0.0.1:9999",
            "chart_url": "http://127.0.0.1:8899",
            "start_script": "Horosa-Web/start_horosa_local.sh",
            "stop_script": "Horosa-Web/stop_horosa_local.sh",
        },
        "runtimes": {
            "python": "runtime/linux/python/bin/python3",
            "java": "runtime/linux/java/bin/java",
            "node": "runtime/linux/node/bin/node",
        },
        "artifacts": {
            "horosa_web_root": "Horosa-Web",
            "astropy_root": "Horosa-Web/astropy",
            "flatlib_root": "Horosa-Web/flatlib-ctrad2/flatlib",
            "swefiles_root": "Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles",
            "boot_jar": "runtime/linux/bundle/astrostudyboot.jar",
            "horosa_core_js_root": "horosa-core-js",
        },
    }
    (PAYLOAD_ROOT / "runtime-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build() -> Path:
    version = read_version()
    skip_download = os.environ.get("HOROSA_LINUX_SKIP_DOWNLOAD", "0") == "1"
    archive_name = f"horosa-runtime-linux-x64-v{version}.tar.gz"

    # -- Validate vendored sources --
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
    require_path(CORE_JS_ROOT / "bin" / "cli.mjs")

    # -- Clean and recreate build directories --
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT)
    PAYLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    DIST_ROOT.mkdir(parents=True, exist_ok=True)

    # -- Assemble Horosa-Web (shared code across all platforms) --
    horosa_web_root = PAYLOAD_ROOT / "Horosa-Web"
    (horosa_web_root / "astrostudyui" / "scripts").mkdir(parents=True, exist_ok=True)
    (horosa_web_root / "scripts").mkdir(parents=True, exist_ok=True)

    rsync_copy(SOURCE_ROOT / "Horosa-Web" / "astropy", horosa_web_root / "")
    (horosa_web_root / "vendor").mkdir(parents=True, exist_ok=True)
    for ken_engine in ("kinqimen", "kintaiyi", "kinjinkou",
                       "kinwangji", "kinwuzhao",
                       "taixuanshifa", "jingjue", "shenyishu"):
        rsync_copy(SOURCE_ROOT / "Horosa-Web" / "vendor" / ken_engine, horosa_web_root / "vendor" / "")
    if (SOURCE_ROOT / "Horosa-Web" / "vendor" / "kinastro").is_dir():
        rsync_copy(
            SOURCE_ROOT / "Horosa-Web" / "vendor" / "kinastro",
            horosa_web_root / "vendor" / "",
            extra_excludes=["tools", "ui", "frontend", "docs", "wiki",
                            "examples", "tests", "styles", "scripts",
                            ".streamlit", ".github", ".devcontainer", ".git"],
        )
    _make_kentang_mount_graceful(
        horosa_web_root / "astropy" / "websrv" / "kentang" / "registry.py"
    )
    rsync_copy(SOURCE_ROOT / "Horosa-Web" / "flatlib-ctrad2" / "flatlib",
               horosa_web_root / "flatlib-ctrad2" / "")
    if (SOURCE_ROOT / "Horosa-Web" / "flatlib-ctrad2" / "LICENSE").is_file():
        (horosa_web_root / "flatlib-ctrad2").mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            SOURCE_ROOT / "Horosa-Web" / "flatlib-ctrad2" / "LICENSE",
            horosa_web_root / "flatlib-ctrad2" / "LICENSE",
        )
    rsync_copy(
        SOURCE_ROOT / "Horosa-Web" / "astrostudyui" / "dist-file",
        horosa_web_root / "astrostudyui" / "",
        extra_excludes=["fengshui"],
    )
    # Start/stop scripts – use the same POSIX scripts as darwin (the runtime manager
    # already selects start_horosa_local.sh for non-Windows platforms).
    if (SOURCE_ROOT / "Horosa-Web" / "start_horosa_local.sh").is_file():
        shutil.copy2(
            SOURCE_ROOT / "Horosa-Web" / "start_horosa_local.sh",
            horosa_web_root / "start_horosa_local.sh",
        )
        # Patch runtime/mac → runtime/linux in the start script so it finds the
        # Linux payload layout at runtime/linux/python/... instead of falling
        # through to PATH lookups on non-macOS platforms.
        start_script = horosa_web_root / "start_horosa_local.sh"
        text = start_script.read_text(encoding="utf-8")
        text = text.replace("runtime/mac/", "runtime/linux/")
        start_script.write_text(text, encoding="utf-8")
        start_script.chmod(0o755)
    if (SOURCE_ROOT / "Horosa-Web" / "stop_horosa_local.sh").is_file():
        shutil.copy2(
            SOURCE_ROOT / "Horosa-Web" / "stop_horosa_local.sh",
            horosa_web_root / "stop_horosa_local.sh",
        )

    # -- 邵子神数: generate verse JSON from CSV --
    _gen_shaozi_tiaowen(horosa_web_root)

    # -- Linux runtime binaries --
    runtime_linux_root = PAYLOAD_ROOT / "runtime" / "linux"

    # Java: use jlink to create a minimal JRE from a full JDK
    java_home = os.environ.get("HOROSA_LINUX_JAVA_HOME")
    if java_home:
        java_source = Path(java_home).expanduser().resolve()
        require_path(java_source)
        print(f"using local JDK at {java_source} for jlink …")
        make_embedded_java_runtime(java_source, runtime_linux_root / "java")
    elif skip_download:
        (runtime_linux_root / "java" / "bin").mkdir(parents=True, exist_ok=True)
        (runtime_linux_root / "java" / "bin" / "java.placeholder").write_text("")
        print("SKIP_DOWNLOAD set; java placeholder created")
    else:
        jdk_url = latest_temurin_jdk_url()
        jdk_archive = download(jdk_url, DOWNLOAD_ROOT / "OpenJDK17U-jdk_linux_x64.tar.gz")
        # Extract to a temp dir so we can run jlink
        with tempfile.TemporaryDirectory(prefix="horosa-jdk-") as tmpdir:
            extract_tar_strip_first(jdk_archive, Path(tmpdir))
            java_source = Path(tmpdir)
            print(f"creating minimal JRE from JDK at {java_source} …")
            make_embedded_java_runtime(java_source, runtime_linux_root / "java")

    # Python: pre-built portable runtime from python-build-standalone
    python_home = os.environ.get("HOROSA_LINUX_PYTHON_HOME")
    if python_home:
        python_source = Path(python_home).expanduser().resolve()
        require_path(python_source)
        python_dest = runtime_linux_root / "python"
        python_dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(python_source, python_dest, symlinks=True, dirs_exist_ok=True)
        print(f"using local Python at {python_source} → {python_dest}")
    elif skip_download:
        (runtime_linux_root / "python" / "bin").mkdir(parents=True, exist_ok=True)
        (runtime_linux_root / "python" / "bin" / "python3.placeholder").write_text("")
        print("SKIP_DOWNLOAD set; python placeholder created")
    else:
        _install_standalone_python(runtime_linux_root)

    # Node: download pre-built linux-x64 binary
    if skip_download:
        (runtime_linux_root / "node" / "bin").mkdir(parents=True, exist_ok=True)
        (runtime_linux_root / "node" / "bin" / "node.placeholder").write_text("")
        print("SKIP_DOWNLOAD set; node placeholder created")
    else:
        node_url = latest_node_linux_url()
        node_archive = download(node_url, DOWNLOAD_ROOT / "node-linux-x64.tar.gz")
        extract_tar_strip_first(node_archive, runtime_linux_root / "node")
        # Make node executable
        node_bin = runtime_linux_root / "node" / "bin" / "node"
        if node_bin.is_file():
            node_bin.chmod(0o755)

    # Boot jar (shared Java backend artifact from vendor/mac)
    require_path(SOURCE_ROOT / "runtime" / "mac" / "bundle" / "astrostudyboot.jar")
    (runtime_linux_root / "bundle").mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        SOURCE_ROOT / "runtime" / "mac" / "bundle" / "astrostudyboot.jar",
        runtime_linux_root / "bundle" / "astrostudyboot.jar",
    )

    # -- horosa-core-js with npm dependencies --
    npm_cmd = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm_cmd:
        raise SystemExit("npm not found on PATH; install Node.js so horosa-core-js deps can be bundled")
    print("installing horosa-core-js production deps …")
    subprocess.run(
        [npm_cmd, "install", "--omit=dev", "--no-audit", "--no-fund", "--loglevel=error"],
        cwd=str(CORE_JS_ROOT),
        check=True,
    )
    require_path(CORE_JS_ROOT / "node_modules" / "lunar-javascript" / "package.json")
    rsync_copy(CORE_JS_ROOT, PAYLOAD_ROOT / "")

    # -- Write runtime manifest --
    write_manifest(version)

    # -- Package tar.gz --
    archive_path = DIST_ROOT / archive_name
    if archive_path.exists():
        archive_path.unlink()
    with tarfile.open(archive_path, "w:gz", compresslevel=6) as tf:
        tf.add(PAYLOAD_ROOT, arcname=PAYLOAD_ROOT.relative_to(BUILD_ROOT))
    return archive_path


if __name__ == "__main__":
    result = build()
    print(f"runtime payload ready: {result}")
