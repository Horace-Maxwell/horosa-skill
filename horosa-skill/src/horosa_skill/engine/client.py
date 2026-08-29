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



# Java 聚合层把业务失败塞进 200/500 的 body 里，只看状态码得到的永远是一句
# 「本地 Horosa 后端返回 HTTP 500」——两个最常见的码值有完全不同的处置，值得直接翻译出来。
_JAVA_PARAM_HINT = (
    "ResultCode 200001 = 参数错误。最常见的成因是必填的经纬度传了 null —— "
    "/nongli/time 要求 lon 与 lat 均非空。"
)
_JAVA_NO_REGISTER_HINT = (
    "ResultCode 9999 (no.register.app) = Java 聚合层的 app 注册没读到（注册信息在 MongoDB 里）。"
    "注意 doctor 探的是 /common/time，不碰这族路由，所以 doctor 绿不代表它活着。"
)
# 9999 是**通用**失败码，不是 no.register.app 的同义词：实测同一台机器上，缺 lat 触发的上游字符串
# 越界回的也是 `{"ResultCode": 9999, "Result": "begin 1, end 3, length 1"}`。只按码值贴「app 注册没
# 读到（在 MongoDB 里）」，会把一个参数 bug 指去查 Mongo——正是本仓花了两轮才清掉的那类误诊。
# 所以：9999 必须再看 `Result` 原文，认不出就给中性提示，不替用户断案。
_JAVA_GENERIC_9999_HINT = (
    "ResultCode 9999 是 Java 聚合层的通用失败码，**不等于** app 注册问题——请以 `Result` 原文为准。"
    "本仓实测过的一例：`begin/end/length` 形态的字符串越界，真因是请求缺 lat（先核 lon 与 lat 是否齐全）。"
)


def _java_result_code(body: str, code: str) -> bool:
    return f'"ResultCode" : {code}' in body or f'"ResultCode": {code}' in body


def _java_result_code_hint(body: str) -> str:
    if _java_result_code(body, "200001"):
        return _JAVA_PARAM_HINT
    if _java_result_code(body, "9999"):
        return _JAVA_NO_REGISTER_HINT if "no.register.app" in body else _JAVA_GENERIC_9999_HINT
    return ""


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
            body = self._decode_response_text(exc.response)[:1000]
            raise ToolTransportError(
                f"本地 Horosa 后端返回 HTTP {exc.response.status_code}。{_java_result_code_hint(body)}",
                code="transport.http_error",
                details={
                    "endpoint": endpoint,
                    "status_code": exc.response.status_code,
                    "body": body,
                    **({"diagnosis": hint} if (hint := _java_result_code_hint(body)) else {}),
                },
            ) from exc
        except httpx.HTTPError as exc:
            raise ToolTransportError(
                "无法连接本地 Horosa 后端（可能未启动或正在冷启动）。",
                code="transport.connection_error",
                details={"endpoint": endpoint, "message": str(exc)},
            ) from exc
        except ValueError as exc:
            raise ToolTransportError(
                "本地 Horosa 后端返回了无效 JSON。",
                code="transport.invalid_json",
                details={"endpoint": endpoint, "message": str(exc)},
            ) from exc


class HorosaPlainJsonClient:
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

    def probe(self, endpoint: str = "/", payload: dict[str, Any] | None = None) -> bool:
        url = f"{self.server_root}{endpoint}"
        try:
            with httpx.Client(timeout=min(self.timeout, 5.0), transport=self.transport, follow_redirects=True) as client:
                if payload is None:
                    response = client.get(url)
                else:
                    response = client.post(url, json=payload)
                if response.status_code >= 500:
                    return False
                # /healthz（v0.33.0 批 I-6）：真就绪探针——新 runtime 回 {ok, warm}，ok=false 视为未就绪。
                # 老 runtime 无此路由（404<500）→ 维持「服务在」判定，与旧探 "/" 行为等价（诚实回退）。
                if endpoint == "/healthz" and response.status_code == 200:
                    try:
                        body = response.json()
                        if isinstance(body, dict) and body.get("ok") is False:
                            return False
                    except ValueError:
                        pass
                return True
        except Exception:
            return False

    def call(self, endpoint: str, payload: dict[str, Any]) -> Any:
        url = f"{self.server_root}{endpoint}"
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict) and data.get("err"):
                    raise ToolTransportError(
                        "后端拒绝了本次请求参数（backend_param_error）。",
                        code="tool.backend_param_error",
                        details={"endpoint": endpoint, "status_code": response.status_code, "body": response.text[:1000]},
                    )
                return data
        except ToolTransportError:
            raise
        except httpx.HTTPStatusError as exc:
            raise ToolTransportError(
                f"本地星盘计算服务返回 HTTP {exc.response.status_code}。",
                code="transport.http_error",
                details={"endpoint": endpoint, "status_code": exc.response.status_code, "body": exc.response.text[:1000]},
            ) from exc
        except httpx.HTTPError as exc:
            raise ToolTransportError(
                "无法连接本地星盘计算服务（可能未启动或正在冷启动）。",
                code="transport.connection_error",
                details={"endpoint": endpoint, "message": str(exc)},
            ) from exc
        except ValueError as exc:
            raise ToolTransportError(
                "本地星盘计算服务返回了无效 JSON。",
                code="transport.invalid_json",
                details={"endpoint": endpoint, "message": str(exc)},
            ) from exc
