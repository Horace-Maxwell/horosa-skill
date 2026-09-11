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


def _index_blobs(paths: list[Path]) -> dict[Path, bytes]:
    """The bytes git HOLDS for each tracked file (index blob via `git ls-files -s` + `git cat-file --batch`),
    not what the checkout wrote.

    🔴 On a Windows runner the working tree may legitimately carry CRLF (Git for Windows' autocrlf rewrites text on
    checkout even with `eol=lf` in some setups) — reading files from disk made this guard red on every Windows run
    since it was added (v0.38.0 B0 → A5), while the repository content was LF all along. What the guard protects
    is the committed content, so that is what it must read. (`cat-file --batch` does not resolve `:<path>` object
    names — feed it the blob SHAs from `ls-files -s`.)
    """
    wanted = {p.relative_to(REPO_ROOT).as_posix(): p for p in paths}
    listing = subprocess.run(["git", "ls-files", "-s", "-z"], cwd=REPO_ROOT, capture_output=True, check=True).stdout
    sha_for: dict[str, str] = {}
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        meta, _, name = entry.partition(b"\t")
        parts = meta.split()
        if len(parts) >= 3:
            sha_for[name.decode("utf-8")] = parts[1].decode("ascii")
    names = [name for name in wanted if name in sha_for]
    if not names:
        return {}
    stdin = "".join(f"{sha_for[name]}\n" for name in names).encode("ascii")
    out = subprocess.run(["git", "cat-file", "--batch"], cwd=REPO_ROOT, input=stdin, capture_output=True, check=True).stdout
    blobs: dict[Path, bytes] = {}
    pos = 0
    for name in names:
        end = out.index(b"\n", pos)
        header = out[pos:end].decode("utf-8", "replace")
        pos = end + 1
        if header.endswith(" missing"):
            continue
        size = int(header.rsplit(" ", 1)[1])
        blobs[wanted[name]] = out[pos:pos + size]
        pos += size + 1  # trailing newline after the blob
    return blobs


def has_cr(data: bytes) -> bool:
    if b"\0" in data[:8000]:
        return False  # binary by content
    return b"\r" in data


def files_with_cr(paths: list[Path]) -> list[Path]:
    """On-disk variant (negative control + ad-hoc use)."""
    return [p for p in paths if p.suffix.lower() not in BINARY_SUFFIXES and p.is_file() and has_cr(p.read_bytes())]


def tracked_offenders() -> list[Path]:
    """Tracked files whose COMMITTED bytes carry a CR (index blobs, so a CRLF checkout on Windows is not an offender)."""
    candidates = [p for p in tracked_files() if p.suffix.lower() not in BINARY_SUFFIXES]
    return [path for path, data in _index_blobs(candidates).items() if has_cr(data)]


def test_no_tracked_text_file_contains_a_carriage_return() -> None:
    offenders = [p.relative_to(REPO_ROOT).as_posix() for p in tracked_offenders()]
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


def test_index_blob_reader_returns_committed_bytes_and_skips_untracked() -> None:
    """The guard reads what git holds: `.gitattributes` must come back with its LF content even when a Windows
    checkout rewrote the working copy; an untracked path is reported missing, not crashed on."""
    blobs = _index_blobs([REPO_ROOT / ".gitattributes", REPO_ROOT / "definitely-not-tracked.txt"])
    assert set(blobs) == {REPO_ROOT / ".gitattributes"}
    data = blobs[REPO_ROOT / ".gitattributes"]
    assert b"eol=lf" in data and b"\r" not in data
