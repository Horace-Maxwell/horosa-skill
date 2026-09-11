"""No tracked text file may contain a carriage return (v0.38.0 B0).

`.gitattributes` says `* text=auto eol=lf`, yet docs/LESSONS.md arrived on main as CRLF (2245 lines), and one
line had a literal `\\r` escape turned into a REAL carriage-return byte (`current\\runtime` → `current<CR>untime`),
which `read_text()` then splits into two lines. A stray CR is invisible in most editors and corrupts every
line-based tool afterwards (docs-sync, sha stamps computed on LF text, launcher templates).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz", ".jar", ".dll", ".exe",
    ".woff", ".woff2", ".ttf", ".otf", ".db", ".sqlite",
}


def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, check=True).stdout
    return [REPO_ROOT / name.decode("utf-8") for name in out.split(b"\0") if name]


def files_with_cr(paths: list[Path]) -> list[Path]:
    offenders: list[Path] = []
    for path in paths:
        if path.suffix.lower() in BINARY_SUFFIXES or not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data[:8000]:
            continue  # binary by content
        if b"\r" in data:
            offenders.append(path)
    return offenders


def test_no_tracked_text_file_contains_a_carriage_return() -> None:
    offenders = [str(p.relative_to(REPO_ROOT)) for p in files_with_cr(tracked_files())]
    assert offenders == [], (
        f"these tracked text files contain \\r bytes (CRLF endings or a corrupted escape): {offenders}; "
        "the repo is eol=lf — normalize them before committing"
    )


def test_guard_catches_crlf_and_stray_cr(tmp_path: Path) -> None:
    """Negative control: both shapes seen on main must be red; clean text and binaries must not."""
    crlf = tmp_path / "crlf.md"
    crlf.write_bytes("line one\r\nline two\r\n".encode("utf-8"))
    stray = tmp_path / "stray.md"
    stray.write_bytes("path `current\rruntime`\n".encode("utf-8"))
    clean = tmp_path / "clean.md"
    clean.write_bytes("fine\n".encode("utf-8"))
    binary = tmp_path / "blob.png"
    binary.write_bytes(b"\x89PNG\r\n")
    nul = tmp_path / "blob.bin"
    nul.write_bytes(b"\x00\r\n")
    assert files_with_cr([crlf, stray, clean, binary, nul]) == [crlf, stray]
