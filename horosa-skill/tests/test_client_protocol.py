from __future__ import annotations

import base64
import hashlib
import json

import httpx

from horosa_skill.engine.client import (
    DEFAULT_CLIENT_APP,
    DEFAULT_CLIENT_CHANNEL,
    DEFAULT_CLIENT_RSA_MODULUS,
    DEFAULT_CLIENT_RSA_PUBLIC_EXP,
    DEFAULT_CLIENT_VER,
    DEFAULT_SIGNATURE_KEY,
    HorosaApiClient,
    _aes_decrypt_ecb,
    _aes_encrypt_ecb,
    _pkcs1_pad,
    _rsa_decrypt_pkcs1,
)

APP1_PRIVATE_EXP = (
    "2FDC3A4ECC6FA6E1FA3BF6C6B9187560DE18D8EB45530595A805EC7042CB0E079C4E5672B9F309DF8BFFB1365C0225ECDE3EAE32874078B8FEDFA6C64DA300D7AC51157431B2AC20D1DED14E4C3C0D14231EB042A91F65DA7E8F3283AAFE0C3AE2413AD33B34BBA4A34F2EA99551CCB4AF4AA533281073712FD86FAB461DF3015EA44C4A48939785E8E76D2D740EC4DFAA22BE92C2EA7CB4645B716EE2932ECBAD787A6889BC3566AB411EF0F5BD1E87B683E7A8B8D662A1A4B722B03AA7128030081C433A52C43FF5559F81820EAA3FA6016ECEEE8EE30E2FA2B0456CE967706C81FF3D9A0C57F1CAD2463A6DA07E0A7BA3EA28F5DBD70A5060832C22DEB5"
)


def _rsa_encrypt_with_exponent(plain: bytes, exponent_hex: str) -> bytes:
    modulus = int(DEFAULT_CLIENT_RSA_MODULUS, 16)
    block_size = (modulus.bit_length() + 7) // 8
    padded = _pkcs1_pad(plain, block_size)
    value = int.from_bytes(padded, "big")
    encoded = pow(value, int(exponent_hex, 16), modulus)
    return encoded.to_bytes(block_size, "big")


def _encrypt_response_payload(body_text: str) -> str:
    aes_key = b"abcdefghijklmnop"
    encrypted_body = base64.b64encode(_aes_encrypt_ecb(body_text.encode("utf-8"), aes_key)).decode("ascii")
    encrypted_key = base64.b64encode(_rsa_encrypt_with_exponent(aes_key, APP1_PRIVATE_EXP)).decode("ascii")
    return f"{encrypted_body},{encrypted_key}"


def test_client_sends_signed_encrypted_request_and_decrypts_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["ClientChannel"] == DEFAULT_CLIENT_CHANNEL
        assert request.headers["ClientApp"] == DEFAULT_CLIENT_APP
        assert request.headers["ClientVer"] == DEFAULT_CLIENT_VER
        assert request.headers["Token"] == ""

        body_parts = request.content.decode("utf-8").split(",")
        aes_key = _rsa_decrypt_pkcs1(base64.b64decode(body_parts[1]), DEFAULT_CLIENT_RSA_MODULUS, APP1_PRIVATE_EXP)
        plain_body = _aes_decrypt_ecb(base64.b64decode(body_parts[0]), aes_key).decode("utf-8")
        expected_body = {} if request.url.path == "/common/time" else {"year": 2026}
        assert json.loads(plain_body) == expected_body

        expected_signature = hashlib.sha256(
            f"{''}{DEFAULT_SIGNATURE_KEY}{DEFAULT_CLIENT_CHANNEL}{DEFAULT_CLIENT_APP}{DEFAULT_CLIENT_VER}{plain_body}".encode(
                "utf-8"
            )
        ).hexdigest()
        assert request.headers["Signature"] == expected_signature

        if request.url.path == "/common/time":
            return httpx.Response(200, headers={"Encrypted": "1"}, text=_encrypt_response_payload("1775338316537"))

        response_body = _encrypt_response_payload(json.dumps({"Result": {"jieqi24": [], "ok": True}}))
        return httpx.Response(200, headers={"Encrypted": "1"}, text=response_body)

    client = HorosaApiClient("http://127.0.0.1:9999", transport=httpx.MockTransport(handler))

    assert client.probe("/common/time") is True
    result = client.call("/jieqi/year", {"year": 2026})

    assert result["Result"]["ok"] is True
