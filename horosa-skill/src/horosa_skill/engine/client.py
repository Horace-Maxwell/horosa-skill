from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from typing import Any

import httpx
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from horosa_skill.errors import ToolTransportError

DEFAULT_SIGNATURE_KEY = "FE45AB6E29EF"
DEFAULT_CLIENT_CHANNEL = "1"
DEFAULT_CLIENT_APP = "1"
DEFAULT_CLIENT_VER = "1.0"
DEFAULT_CLIENT_RSA_MODULUS = (
    "902563E4F9348E8366C0939BAB48D4403AA7CCD933EECF899265228512C4B72F2E30084B7CADF97132D0882A51FB814E5ADD82D676CFCFBC22ECDDCFACE8D4444BC60B5B30A53EB933321BA2FB9AA69727C03A5E6A90BDAB5895A8E179FF24CF9B0F66A4061E028EAB86FCE733254B5ED2D0CE47AF7A4CD1BB987702237F2A89FE8D86938ACD9D125CC6A1094AA291418D088D355A139E00C406045D38BD215F23F3D222352FD74AC914798FE3160B10A93C7F15319D5B44840850DF6A504E0299CD994F0A3133C7D58054AB19C43B6FEAA71AC0F61904665F345C2D99A25BD56D1CBFFFD08BE699D6FA53E1AD2ED812B8710DBA86D4CC43FF6389DEDD2888B9"
)
DEFAULT_CLIENT_RSA_PUBLIC_EXP = "10001"
DEFAULT_AES_KEY_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789_"


def _json_body(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _random_key(length: int = 16) -> bytes:
    return "".join(secrets.choice(DEFAULT_AES_KEY_CHARS) for _ in range(length)).encode("utf-8")


def _pkcs1_pad(plain: bytes, block_size: int) -> bytes:
    if len(plain) > block_size - 11:
        raise ValueError("RSA plaintext too long for PKCS#1 v1.5 block.")
    padding_size = block_size - len(plain) - 3
    padding_bytes = bytearray()
    while len(padding_bytes) < padding_size:
        value = secrets.randbelow(255) + 1
        padding_bytes.append(value)
    return b"\x00\x02" + bytes(padding_bytes) + b"\x00" + plain


def _pkcs1_unpad(block: bytes) -> bytes:
    if len(block) < 11 or block[0] != 0 or block[1] not in (1, 2):
        raise ValueError("Invalid PKCS#1 block.")
    separator = block.find(b"\x00", 2)
    if separator < 0:
        raise ValueError("Invalid PKCS#1 block separator.")
    return block[separator + 1 :]


def _rsa_apply_exponent(cipher_bytes: bytes, modulus_hex: str, exponent_hex: str) -> bytes:
    modulus = int(modulus_hex, 16)
    exponent = int(exponent_hex, 16)
    block_size = (modulus.bit_length() + 7) // 8
    value = int.from_bytes(cipher_bytes, "big")
    decoded = pow(value, exponent, modulus)
    return decoded.to_bytes(block_size, "big")


def _rsa_encrypt_pkcs1(plain: bytes, modulus_hex: str, exponent_hex: str) -> bytes:
    modulus = int(modulus_hex, 16)
    block_size = (modulus.bit_length() + 7) // 8
    padded = _pkcs1_pad(plain, block_size)
    value = int.from_bytes(padded, "big")
    encoded = pow(value, int(exponent_hex, 16), modulus)
    return encoded.to_bytes(block_size, "big")


def _rsa_decrypt_pkcs1(cipher_bytes: bytes, modulus_hex: str, exponent_hex: str) -> bytes:
    decoded = _rsa_apply_exponent(cipher_bytes, modulus_hex, exponent_hex)
    return _pkcs1_unpad(decoded)


def _aes_encrypt_ecb(plain: bytes, key: bytes) -> bytes:
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(plain) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    return encryptor.update(padded) + encryptor.finalize()


def _aes_decrypt_ecb(ciphertext: bytes, key: bytes) -> bytes:
    decryptor = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


def _encrypt_request_payload(body_text: str) -> str:
    aes_key = _random_key()
    encrypted_body = base64.b64encode(_aes_encrypt_ecb(body_text.encode("utf-8"), aes_key)).decode("ascii")
    encrypted_key = base64.b64encode(
        _rsa_encrypt_pkcs1(aes_key, DEFAULT_CLIENT_RSA_MODULUS, DEFAULT_CLIENT_RSA_PUBLIC_EXP)
    ).decode("ascii")
    encrypted_time = base64.b64encode(
        _aes_encrypt_ecb(str(int(time.time() * 1000)).encode("utf-8"), aes_key)
    ).decode("ascii")
    return f"{encrypted_body},{encrypted_key},{encrypted_time}"


def _decrypt_response_payload(payload_text: str) -> str:
    parts = payload_text.split(",")
    if len(parts) < 2:
        raise ValueError("Encrypted payload is missing required segments.")
    aes_key = _rsa_decrypt_pkcs1(base64.b64decode(parts[1]), DEFAULT_CLIENT_RSA_MODULUS, DEFAULT_CLIENT_RSA_PUBLIC_EXP)
    plain = _aes_decrypt_ecb(base64.b64decode(parts[0]), aes_key)
    return plain.decode("utf-8")


class HorosaApiClient:
    def __init__(
        self,
        server_root: str,
        timeout: float = 60.0,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.server_root = server_root.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    def _build_headers(self, body_text: str) -> dict[str, str]:
        token = ""
        signature = _sha256_hex(
            f"{token}{DEFAULT_SIGNATURE_KEY}{DEFAULT_CLIENT_CHANNEL}{DEFAULT_CLIENT_APP}{DEFAULT_CLIENT_VER}{body_text}"
        )
        return {
            "Token": token,
            "Content-Type": "application/json; charset=UTF-8",
            "LocalIp": "",
            "ClientChannel": DEFAULT_CLIENT_CHANNEL,
            "ClientApp": DEFAULT_CLIENT_APP,
            "ClientVer": DEFAULT_CLIENT_VER,
            "Signature": signature,
        }

    def _decode_response_text(self, response: httpx.Response) -> str:
        payload_text = response.text
        if response.headers.get("Encrypted") == "1":
            try:
                return _decrypt_response_payload(payload_text)
            except Exception:
                return payload_text
        return payload_text

    def probe(self, endpoint: str = "/common/time", payload: dict[str, Any] | None = None) -> bool:
        url = f"{self.server_root}{endpoint}"
        body_text = _json_body(payload or {})
        headers = self._build_headers(body_text)
        encoded_payload = _encrypt_request_payload(body_text)
        try:
            with httpx.Client(timeout=min(self.timeout, 5.0), transport=self.transport) as client:
                response = client.post(url, content=encoded_payload, headers=headers)
                decoded = self._decode_response_text(response)
                return response.status_code < 500 and bool(decoded.strip())
        except Exception:
            return False

    def call(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.server_root}{endpoint}"
        body_text = _json_body(payload)
        headers = self._build_headers(body_text)
        encoded_payload = _encrypt_request_payload(body_text)
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                response = client.post(url, content=encoded_payload, headers=headers)
                response_text = self._decode_response_text(response)
                response.raise_for_status()
                data = json.loads(response_text)
                if not isinstance(data, dict):
                    raise ToolTransportError(
                        "Horosa server returned a non-object JSON response.",
                        code="transport.invalid_response_shape",
                        details={"endpoint": endpoint},
                    )
                return data
        except httpx.HTTPStatusError as exc:
            raise ToolTransportError(
                f"Horosa server returned HTTP {exc.response.status_code}.",
                code="transport.http_error",
                details={
                    "endpoint": endpoint,
                    "status_code": exc.response.status_code,
                    "body": self._decode_response_text(exc.response)[:1000],
                },
            ) from exc
        except httpx.HTTPError as exc:
            raise ToolTransportError(
                "Could not reach the Horosa server.",
                code="transport.connection_error",
                details={"endpoint": endpoint, "message": str(exc)},
            ) from exc
        except ValueError as exc:
            raise ToolTransportError(
                "Horosa server returned invalid JSON.",
                code="transport.invalid_json",
                details={"endpoint": endpoint, "message": str(exc)},
            ) from exc
