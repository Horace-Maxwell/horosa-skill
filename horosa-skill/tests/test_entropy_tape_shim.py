"""The vendored `utils/entropyTape.js` reads 「真随机记录」 exactly like upstream (v0.53.0, upstream v3.15.0 真随机).

Why: upstream extends an exhausted record with node-forge SHA-256 over `tape ‖ UTF-8("|"+domain) ‖ counter(BE32)`
(`md.update(bin, 'raw')` = one byte per char). The skill swaps node-forge for a `node:crypto` shim (manifest stub). The
two earlier forge shims (tarot shuffle / lingqi) only implement `toHex` over UTF-8; this file also needs `'raw'`,
`getBytes()` and `util.encodeUtf8`. If the shim got any of them wrong, a replayed 塔罗 / 灵棋 record would silently
draw different cards once it runs past the recorded bytes — exactly the case the extension exists for.
Oracle: the same algorithm written independently with hashlib (no node-forge needed).
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from node_esm import run_node_esm

CORE_JS = Path(__file__).resolve().parents[1] / "horosa-core-js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not installed")


def _reference_bits(tape: bytes, domain: str, offset: int, length: int, n: int) -> list[int]:
    chunk, extended, out = tape[offset:offset + length], 0, []
    while len(out) < n:
        for byte in chunk:
            out.extend((byte >> (7 - i)) & 1 for i in range(8))
        tail = ("|" + domain).encode("utf-8") if domain else b""
        chunk = hashlib.sha256(tape + tail + extended.to_bytes(4, "big")).digest()
        extended += 1
    return out[:n]


def _js_bits(seed: str, lane: dict | None, n: int) -> list[int]:
    script = ("const { entropyReader } = await import(process.argv[1]);"
              "const [seed, lane, n] = JSON.parse(process.argv[2]);"
              "const r = entropyReader(seed, lane || undefined);"
              "process.stdout.write(JSON.stringify(Array.from({length: n}, () => r.bits(1))));")
    return json.loads(run_node_esm(script, CORE_JS / "src" / "vendor" / "utils" / "entropyTape.js", json.dumps([seed, lane, n])))


@pytest.mark.parametrize(("tape_hex", "lane"), [
    ("a5", None),                                                        # 1 byte, no lane: extension starts after 8 bits
    ("00ff7f80c3", {"offset": 1, "length": 2, "domain": "塔罗|主洗牌"}),   # multi-byte UTF-8 domain + sub-lane
    ("deadbeef", {"offset": 0, "length": 4, "domain": "cut"}),
])
def test_reader_matches_the_spec_past_the_end_of_the_record(tape_hex: str, lane: dict | None) -> None:
    tape = bytes.fromhex(tape_hex)
    offset, length = (lane["offset"], lane["length"]) if lane else (0, len(tape))
    domain = lane["domain"] if lane else ""
    n = 8 * length + 3 * 256   # 三块续接，确保走到 sha256Block
    assert _js_bits("tr1-" + tape_hex, lane, n) == _reference_bits(tape, domain, offset, length, n)


def test_the_reference_would_catch_a_utf8_only_shim() -> None:
    """Negative control: the earlier shims' rule (hash the UTF-8 of the joined string) differs once a tape byte ≥ 0x80."""
    tape, domain = bytes.fromhex("00ff7f80c3"), "塔罗"
    as_raw = hashlib.sha256(tape + ("|" + domain).encode() + (0).to_bytes(4, "big")).digest()
    utf8_of_chars = hashlib.sha256((tape.decode("latin1") + "|" + domain).encode("utf-8") + (0).to_bytes(4, "big")).digest()
    assert as_raw != utf8_of_chars
