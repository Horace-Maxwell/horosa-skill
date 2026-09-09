from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import platform
import re
import secrets
import sys
import shutil
import subprocess
import tarfile
import tempfile
import threading
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import url2pathname

import httpx

from horosa_skill.config import Settings
from horosa_skill.engine.client import HorosaApiClient, loopback_httpx_client
from horosa_skill.errors import RuntimeInstallError, RuntimeValidationError
from horosa_skill.runtime import registry as runtime_registry
from horosa_skill.runtime.identity import EndpointIdentity, classify_endpoint, trust_unknown_ports
from horosa_skill.runtime.pidlock import describe_lock, release as release_lock, try_pid_lock
from horosa_skill.runtime.ports import port_holders
from horosa_skill.tracing import TraceRecorder

logger = logging.getLogger(__name__)


def _platform_key() -> str:
    # 架构精确匹配：只有确知的 64 位架构映射到发布键；其余（i386/i686/armv7l 等）保留原始
    # machine 名 —— 让 install 的 `runtime.install_missing_platform` 错误如实报出真实架构，
    # 而不是把 32 位机器误标成 x64 后下载一个跑不起来的运行时。
    machine = platform.machine().lower()
    arm64 = {"arm64", "aarch64", "armv8l"}
    x64 = {"x86_64", "amd64"}
    if sys_platform := platform.system().lower():
        if sys_platform == "darwin":
            if machine in arm64:
                return "darwin-arm64"
            if machine in x64:
                return "darwin-x64"
            return f"darwin-{machine}"
        if sys_platform == "windows":
            if machine in arm64:
                return "win32-arm64"
            if machine in x64:
                return "win32-x64"
            return f"win32-{machine}"
        if sys_platform == "linux":
            if machine in arm64:
                return "linux-arm64"
            if machine in x64:
                return "linux-x64"
            return f"linux-{machine}"
    return f"{sys_platform}-{machine}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https", "file"}


WINDOWS_LOCAL_CACHE_FACTORY = "horosa.offline.LocalCacheFactory"
WINDOWS_LOCAL_CACHE_CONFIG = "offline"
WINDOWS_BOOT_CACHE_CONFIG_PATH = "BOOT-INF/classes/conf/properties/cache/caches.json"
WINDOWS_BOOT_WEBPARAMS_PATH = "BOOT-INF/classes/conf/properties/param/webparams.properties"
WINDOWS_BOOT_LOG4J_PATH = "BOOT-INF/classes/log4j2.xml"
WINDOWS_BOOT_BOUNDLESS_PREFIX = "BOOT-INF/lib/boundless-"
WINDOWS_LOCAL_CACHE_FACTORY_CLASS_PATH = "BOOT-INF/classes/horosa/offline/LocalCacheFactory.class"
WINDOWS_LOCAL_CACHE_FACTORY_INNER_CLASS_PATH = "BOOT-INF/classes/horosa/offline/LocalCacheFactory$LocalCache.class"
WINDOWS_LOCAL_CACHE_FACTORY_CLASS_B64 = (
    "yv66vgAAAD0AXwoAAgADBwAEDAAFAAYBABBqYXZhL2xhbmcvT2JqZWN0AQAGPGluaXQ+AQADKClWCQAIAAkHAAoMAAsADAEAIGhvcm9zYS9vZmZsaW5lL0xv"
    "Y2FsQ2FjaGVGYWN0b3J5AQAEbmFtZQEAEkxqYXZhL2xhbmcvU3RyaW5nOwoADgAPBwAQDAARABIBABBqYXZhL2xhbmcvU3RyaW5nAQAHaXNCbGFuawEAAygp"
    "WggAFAEAB2RlZmF1bHQJAAgAFgwAFwAYAQAGQ0FDSEVTAQAoTGphdmEvdXRpbC9jb25jdXJyZW50L0NvbmN1cnJlbnRIYXNoTWFwOxIAAAAaDAAbABwBAAVh"
    "cHBseQEAHygpTGphdmEvdXRpbC9mdW5jdGlvbi9GdW5jdGlvbjsKAB4AHwcAIAwAIQAiAQAmamF2YS91dGlsL2NvbmN1cnJlbnQvQ29uY3VycmVudEhhc2hN"
    "YXABAA9jb21wdXRlSWZBYnNlbnQBAEMoTGphdmEvbGFuZy9PYmplY3Q7TGphdmEvdXRpbC9mdW5jdGlvbi9GdW5jdGlvbjspTGphdmEvbGFuZy9PYmplY3Q7"
    "BwAkAQAWYm91bmRsZXNzL3R5cGVzL0lDYWNoZQkAJgAnBwAoDAApACoBABFqYXZhL2xhbmcvQm9vbGVhbgEABUZBTFNFAQATTGphdmEvbGFuZy9Cb29sZWFu"
    "OwoACAADCgAIAC0MAC4ALwEAC2ZhY3RvcnlOYW1lAQAVKExqYXZhL2xhbmcvU3RyaW5nOylWCgAeAAMHADIBACNib3VuZGxlc3MvdHlwZXMvY2FjaGUvSUNh"
    "Y2hlRmFjdG9yeQEACVNpZ25hdHVyZQEAaUxqYXZhL3V0aWwvY29uY3VycmVudC9Db25jdXJyZW50SGFzaE1hcDxMamF2YS9sYW5nL1N0cmluZztMaG9yb3Nh"
    "L29mZmxpbmUvTG9jYWxDYWNoZUZhY3RvcnkkTG9jYWxDYWNoZTs+OwEABENvZGUBAA9MaW5lTnVtYmVyVGFibGUBAAVidWlsZAEACGdldENhY2hlAQAaKClM"
    "Ym91bmRsZXNzL3R5cGVzL0lDYWNoZTsBAA1TdGFja01hcFRhYmxlAQAFY2xvc2UBAAxuZWVkTWVtQ2FjaGUBABUoKUxqYXZhL2xhbmcvQm9vbGVhbjsBAAxu"
    "ZWVkQ29tcHJlc3MBAAtuZWVkSHlzdHJpeAEAFCgpTGphdmEvbGFuZy9TdHJpbmc7AQAMc3Bhd25GYWN0b3J5AQA5KExqYXZhL2xhbmcvU3RyaW5nOylMYm91"
    "bmRsZXNzL3R5cGVzL2NhY2hlL0lDYWNoZUZhY3Rvcnk7AQAIPGNsaW5pdD4BAApTb3VyY2VGaWxlAQAWTG9jYWxDYWNoZUZhY3RvcnkuamF2YQEAC05lc3RN"
    "ZW1iZXJzBwBIAQAraG9yb3NhL29mZmxpbmUvTG9jYWxDYWNoZUZhY3RvcnkkTG9jYWxDYWNoZQEAEEJvb3RzdHJhcE1ldGhvZHMQAEsBACYoTGphdmEvbGFu"
    "Zy9PYmplY3Q7KUxqYXZhL2xhbmcvT2JqZWN0Ow8IAE0KAEcATgwABQAvEABQAQBBKExqYXZhL2xhbmcvU3RyaW5nOylMaG9yb3NhL29mZmxpbmUvTG9jYWxD"
    "YWNoZUZhY3RvcnkkTG9jYWxDYWNoZTsPBgBSCgBTAFQHAFUMAFYAVwEAImphdmEvbGFuZy9pbnZva2UvTGFtYmRhTWV0YWZhY3RvcnkBAAttZXRhZmFjdG9y"
    "eQEAzChMamF2YS9sYW5nL2ludm9rZS9NZXRob2RIYW5kbGVzJExvb2t1cDtMamF2YS9sYW5nL1N0cmluZztMamF2YS9sYW5nL2ludm9rZS9NZXRob2RUeXBl"
    "O0xqYXZhL2xhbmcvaW52b2tlL01ldGhvZFR5cGU7TGphdmEvbGFuZy9pbnZva2UvTWV0aG9kSGFuZGxlO0xqYXZhL2xhbmcvaW52b2tlL01ldGhvZFR5cGU7"
    "KUxqYXZhL2xhbmcvaW52b2tlL0NhbGxTaXRlOwEADElubmVyQ2xhc3NlcwEACkxvY2FsQ2FjaGUHAFsBACVqYXZhL2xhbmcvaW52b2tlL01ldGhvZEhhbmRs"
    "ZXMkTG9va3VwBwBdAQAeamF2YS9sYW5nL2ludm9rZS9NZXRob2RIYW5kbGVzAQAGTG9va3VwADEACAACAAEAMQACABoAFwAYAAEAMwAAAAIANAACAAsADAAA"
    "AAsAAQAFAAYAAQA1AAAAHQABAAEAAAAFKrcAAbEAAAABADYAAAAGAAEAAAAYAAEANwAvAAEANQAAABkAAAACAAAAAbEAAAABADYAAAAGAAEAAAAfAAEAOAA5"
    "AAEANQAAAFUAAwACAAAAKyq0AAfGAA0qtAAHtgANmQAIEhOnAAcqtAAHTLIAFSu6ABkAALYAHcAAI7AAAAACADYAAAAKAAIAAAAjABsAJAA6AAAACAADEQRD"
    "BwAOAAEAOwAGAAEANQAAABkAAAABAAAAAbEAAAABADYAAAAGAAEAAAAqAAEAPAA9AAEANQAAABwAAQABAAAABLIAJbAAAAABADYAAAAGAAEAAAAuAAEAPgA9"
    "AAEANQAAABwAAQABAAAABLIAJbAAAAABADYAAAAGAAEAAAAzAAEAPwA9AAEANQAAABwAAQABAAAABLIAJbAAAAABADYAAAAGAAEAAAA4AAEALgBAAAEANQAA"
    "AB0AAQABAAAABSq0AAewAAAAAQA2AAAABgABAAAAPQABAC4ALwABADUAAAAiAAIAAgAAAAYqK7UAB7EAAAABADYAAAAKAAIAAABCAAUAQwABAEEAQgABADUA"
    "AAAvAAIAAwAAAA+7AAhZtwArTSwrtgAsLLAAAAABADYAAAAOAAMAAABHAAgASAANAEkACABDAAYAAQA1AAAAIwACAAAAAAALuwAeWbcAMLMAFbEAAAABADYA"
    "AAAGAAEAAAAZAAQARAAAAAIARQBGAAAABAABAEcASQAAAAwAAQBRAAMASgBMAE8AWAAAABIAAgBHAAgAWQAYAFoAXABeABk="
)

WINDOWS_LOCAL_CACHE_FACTORY_INNER_CLASS_B64 = (
    "yv66vgAAAD0B9AoAAgADBwAEDAAFAAYBABBqYXZhL2xhbmcvT2JqZWN0AQAGPGluaXQ+AQADKClWBwAIAQAmamF2YS91dGlsL2NvbmN1cnJlbnQvQ29uY3Vy"
    "cmVudEhhc2hNYXAKAAcAAwkACwAMBwANDAAOAA8BACtob3Jvc2Evb2ZmbGluZS9Mb2NhbENhY2hlRmFjdG9yeSRMb2NhbENhY2hlAQAHZW50cmllcwEAKExq"
    "YXZhL3V0aWwvY29uY3VycmVudC9Db25jdXJyZW50SGFzaE1hcDsHABEBAClqYXZhL3V0aWwvY29uY3VycmVudC9Db3B5T25Xcml0ZUFycmF5TGlzdAoAEAAD"
    "CQALABQMABUAFgEABGRvY3MBACtMamF2YS91dGlsL2NvbmN1cnJlbnQvQ29weU9uV3JpdGVBcnJheUxpc3Q7CQALABgMABkAGgEABG5hbWUBABJMamF2YS9s"
    "YW5nL1N0cmluZzsKAAsAHAwAHQAeAQANZGVlcENvcHlWYWx1ZQEAJihMamF2YS9sYW5nL09iamVjdDspTGphdmEvbGFuZy9PYmplY3Q7CgAHACAMACEAIgEA"
    "A3B1dAEAOChMamF2YS9sYW5nL09iamVjdDtMamF2YS9sYW5nL09iamVjdDspTGphdmEvbGFuZy9PYmplY3Q7CgAHACQMACUAHgEAA2dldAoABwAnDAAoACkB"
    "AAtjb250YWluc0tleQEAFShMamF2YS9sYW5nL09iamVjdDspWgoABwArDAAsAB4BAAZyZW1vdmUKAAcALgwALwAGAQAFY2xlYXIKABAALgoACwAyDAAhADMB"
    "ACcoTGphdmEvbGFuZy9TdHJpbmc7TGphdmEvbGFuZy9PYmplY3Q7KVYHADUBAA1qYXZhL3V0aWwvTWFwCwA0ACQKAAsAOAwAOQA6AQAOZW5zdXJlRW50cnlN"
    "YXABACMoTGphdmEvbGFuZy9TdHJpbmc7KUxqYXZhL3V0aWwvTWFwOwsANAAgCgALAD0MAD4APwEAB3B1dEhhc2gBADkoTGphdmEvbGFuZy9TdHJpbmc7TGph"
    "dmEvbGFuZy9TdHJpbmc7TGphdmEvbGFuZy9PYmplY3Q7KVYKAEEAQgcAQwwARABFAQAQamF2YS9sYW5nL1N0cmluZwEAB3ZhbHVlT2YBACYoTGphdmEvbGFu"
    "Zy9PYmplY3Q7KUxqYXZhL2xhbmcvU3RyaW5nOwoACwBHDABIAEkBAAdjb3B5TWFwAQAgKExqYXZhL3V0aWwvTWFwOylMamF2YS91dGlsL01hcDsKAAsASwwA"
    "TABNAQAGc2V0TWFwAQAkKExqYXZhL2xhbmcvT2JqZWN0O0xqYXZhL3V0aWwvTWFwOylWCgAQAE8MAFAAKQEAA2FkZAoACwBSDABQAFMBABIoTGphdmEvdXRp"
    "bC9NYXA7KVYKAAcAVQwAVgBXAQAEc2l6ZQEAAygpSQoAEABVCgAQAFoMAFsAXAEABnN0cmVhbQEAGygpTGphdmEvdXRpbC9zdHJlYW0vU3RyZWFtOxIAAABe"
    "DABfAGABAAR0ZXN0AQBxKExob3Jvc2Evb2ZmbGluZS9Mb2NhbENhY2hlRmFjdG9yeSRMb2NhbENhY2hlO0xqYXZhL2xhbmcvU3RyaW5nO0xqYXZhL2xhbmcv"
    "U3RyaW5nOylMamF2YS91dGlsL2Z1bmN0aW9uL1ByZWRpY2F0ZTsLAGIAYwcAZAwAZQBmAQAXamF2YS91dGlsL3N0cmVhbS9TdHJlYW0BAAZmaWx0ZXIBADko"
    "TGphdmEvdXRpbC9mdW5jdGlvbi9QcmVkaWNhdGU7KUxqYXZhL3V0aWwvc3RyZWFtL1N0cmVhbTsLAGIAaAwAaQBqAQAFY291bnQBAAMoKUoSAAEAbAwAXwBt"
    "AQBgKExob3Jvc2Evb2ZmbGluZS9Mb2NhbENhY2hlRmFjdG9yeSRMb2NhbENhY2hlO0xqYXZhL2xhbmcvU3RyaW5nO0opTGphdmEvdXRpbC9mdW5jdGlvbi9Q"
    "cmVkaWNhdGU7EgACAG8MAF8AcAEAcChMaG9yb3NhL29mZmxpbmUvTG9jYWxDYWNoZUZhY3RvcnkkTG9jYWxDYWNoZTtbTGJvdW5kbGVzcy90eXBlcy9jYWNo"
    "ZS9GaWx0ZXJDb25kOylMamF2YS91dGlsL2Z1bmN0aW9uL1ByZWRpY2F0ZTsKAAsAcgwAaQBzAQAmKFtMYm91bmRsZXNzL3R5cGVzL2NhY2hlL0ZpbHRlckNv"
    "bmQ7KUoHAHUBABFqYXZhL2xhbmcvSW50ZWdlcgN/////CgALAHgMAHkAegEACmZpbmRWYWx1ZXMBAFYoSUxib3VuZGxlc3MvdHlwZXMvY2FjaGUvU29ydENv"
    "bmQ7W0xib3VuZGxlc3MvdHlwZXMvY2FjaGUvRmlsdGVyQ29uZDspTGphdmEvdXRpbC9MaXN0OwcAfAEAE2phdmEvdXRpbC9BcnJheUxpc3QKAHsAAwoAEAB/"
    "DACAAIEBAAhpdGVyYXRvcgEAFigpTGphdmEvdXRpbC9JdGVyYXRvcjsLAIMAhAcAhQwAhgCHAQASamF2YS91dGlsL0l0ZXJhdG9yAQAHaGFzTmV4dAEAAygp"
    "WgsAgwCJDACKAIsBAARuZXh0AQAUKClMamF2YS9sYW5nL09iamVjdDsKAAsAjQwAjgCPAQAKbWF0Y2hlc0FsbAEANShMamF2YS91dGlsL01hcDtbTGJvdW5k"
    "bGVzcy90eXBlcy9jYWNoZS9GaWx0ZXJDb25kOylaCwCRAE8HAJIBAA5qYXZhL3V0aWwvTGlzdAsAkQBVCgB7AJUMAAUAlgEAGShMamF2YS91dGlsL0NvbGxl"
    "Y3Rpb247KVYLAJEAfwoAEACZDAAsACkHAJsBACBib3VuZGxlc3MvdHlwZXMvY2FjaGUvRmlsdGVyQ29uZAoACwCdDAAsAHMKAAsAnwwAoAChAQAJcmVhZEZp"
    "ZWxkAQA1KExqYXZhL3V0aWwvTWFwO0xqYXZhL2xhbmcvU3RyaW5nOylMamF2YS9sYW5nL09iamVjdDsKAKMApAcApQwApgCnAQARamF2YS91dGlsL09iamVj"
    "dHMBAAZlcXVhbHMBACcoTGphdmEvbGFuZy9PYmplY3Q7TGphdmEvbGFuZy9PYmplY3Q7KVoHAKkBABFqYXZhL3V0aWwvSGFzaFNldAoAqAADCwCsAE8HAK0B"
    "AA1qYXZhL3V0aWwvU2V0BwCvAQARamF2YS91dGlsL0hhc2hNYXAKAK4AAwoACwCyDACzALQBAAtlbnN1cmVEZXF1ZQEAKihMamF2YS9sYW5nL1N0cmluZzsp"
    "TGphdmEvdXRpbC9BcnJheURlcXVlOwoAtgC3BwC4DAC5ALoBABRqYXZhL3V0aWwvQXJyYXlEZXF1ZQEACGFkZEZpcnN0AQAVKExqYXZhL2xhbmcvT2JqZWN0"
    "OylWCgC2AFUKALYAvQwAvgCLAQAJcG9sbEZpcnN0CgC2AMAMAMEAugEAB2FkZExhc3QKALYAwwwAxACLAQAIcG9sbExhc3QKAMYAxwcAyAwAyQDKAQAOamF2"
    "YS9sYW5nL01hdGgBAANtYXgBAAUoSkopSgoAxgDMDADNAMoBAANtaW4LAJEAzwwA0ACHAQAHaXNFbXB0eQoA0gDTBwDUDADVANYBABVqYXZhL3V0aWwvQ29s"
    "bGVjdGlvbnMBAAllbXB0eUxpc3QBABIoKUxqYXZhL3V0aWwvTGlzdDsLAJEA2AwA2QDaAQAHc3ViTGlzdAEAFChJSSlMamF2YS91dGlsL0xpc3Q7CgDcAN0H"
    "AN4MAEQA3wEADmphdmEvbGFuZy9Mb25nAQATKEopTGphdmEvbGFuZy9Mb25nOwoACwDhDADiAOMBAAtudW1iZXJWYWx1ZQEAKihMamF2YS9sYW5nL09iamVj"
    "dDspTGphdmEvbWF0aC9CaWdEZWNpbWFsOwkA5QDmBwDnDADoAOkBABRqYXZhL21hdGgvQmlnRGVjaW1hbAEABFpFUk8BABZMamF2YS9tYXRoL0JpZ0RlY2lt"
    "YWw7CgDlAOsMAEQA7AEAGShKKUxqYXZhL21hdGgvQmlnRGVjaW1hbDsKAOUA7gwAUADvAQAuKExqYXZhL21hdGgvQmlnRGVjaW1hbDspTGphdmEvbWF0aC9C"
    "aWdEZWNpbWFsOwoA5QDxDADyAGoBAAlsb25nVmFsdWUKAAsA9AwA9QD2AQADaW5jAQAWKExqYXZhL2xhbmcvU3RyaW5nO0opSgoACwD4DAD5APYBAANkZWMJ"
    "APsA/AcA/QwA/gAPAQAgaG9yb3NhL29mZmxpbmUvTG9jYWxDYWNoZUZhY3RvcnkBAAZDQUNIRVMSAAMBAAwBAQECAQAFYXBwbHkBAB8oKUxqYXZhL3V0aWwv"
    "ZnVuY3Rpb24vRnVuY3Rpb247CgAHAQQMAQUBBgEAD2NvbXB1dGVJZkFic2VudAEAQyhMamF2YS9sYW5nL09iamVjdDtMamF2YS91dGlsL2Z1bmN0aW9uL0Z1"
    "bmN0aW9uOylMamF2YS9sYW5nL09iamVjdDsHAQgBABZib3VuZGxlc3MvdHlwZXMvSUNhY2hlCgC2AAMKAAsBCwwBDAENAQAHbWF0Y2hlcwEANChMamF2YS91"
    "dGlsL01hcDtMYm91bmRsZXNzL3R5cGVzL2NhY2hlL0ZpbHRlckNvbmQ7KVoIAQ8BAAlvdGhlckNvbmQKAAsBEQwBEgETAQAHcmVmbGVjdAEAOChMamF2YS9s"
    "YW5nL09iamVjdDtMamF2YS9sYW5nL1N0cmluZzspTGphdmEvbGFuZy9PYmplY3Q7BwEVAQAjW0xib3VuZGxlc3MvdHlwZXMvY2FjaGUvRmlsdGVyQ29uZDsI"
    "ARcBAAVtaXhPcAcBGQEALGJvdW5kbGVzcy90eXBlcy9jYWNoZS9GaWx0ZXJDb25kJE1peE9wZXJhdG9yCgALARsMARwBDQEADW1hdGNoZXNTaW5nbGUJARgB"
    "HgwBHwEgAQACT3IBAC5MYm91bmRsZXNzL3R5cGVzL2NhY2hlL0ZpbHRlckNvbmQkTWl4T3BlcmF0b3I7CgCaASIMASMBJAEACGdldEZpZWxkAQAUKClMamF2"
    "YS9sYW5nL1N0cmluZzsKAJoBJgwBJwCLAQAIZ2V0VmFsdWUKAJoBKQwBKgEkAQAFZ2V0T3AKAEEBLAwBLQCHAQAHaXNCbGFuawgBLwEAAkVxCgBBATEMATIB"
    "MwEAEGVxdWFsc0lnbm9yZUNhc2UBABUoTGphdmEvbGFuZy9TdHJpbmc7KVoIATUBAAJOZQgBNwEABkV4aXN0cwgBOQEABExpa2UKAAsBOwwBPABFAQAJc3Ry"
    "aW5naWZ5CgBBAT4MAT8BQAEACGNvbnRhaW5zAQAbKExqYXZhL2xhbmcvQ2hhclNlcXVlbmNlOylaCAFCAQACSW4HAUQBABRqYXZhL3V0aWwvQ29sbGVjdGlv"
    "bgsBQwB/CgDlAUcMAUgBSQEACWNvbXBhcmVUbwEAGShMamF2YS9tYXRoL0JpZ0RlY2ltYWw7KUkIAUsBAAJMdAgBTQEAA0x0ZQgBTwEAAkd0CAFRAQADR3Rl"
    "CAFTAQACXC4KAEEBVQwBVgFXAQAFc3BsaXQBACcoTGphdmEvbGFuZy9TdHJpbmc7KVtMamF2YS9sYW5nL1N0cmluZzsKAAIBWQwBWgFbAQAIZ2V0Q2xhc3MB"
    "ABMoKUxqYXZhL2xhbmcvQ2xhc3M7CgFdAV4HAV8MAWABYQEAD2phdmEvbGFuZy9DbGFzcwEAEGdldERlY2xhcmVkRmllbGQBAC0oTGphdmEvbGFuZy9TdHJp"
    "bmc7KUxqYXZhL2xhbmcvcmVmbGVjdC9GaWVsZDsKAWMBZAcBZQwBZgFnAQAXamF2YS9sYW5nL3JlZmxlY3QvRmllbGQBAA1zZXRBY2Nlc3NpYmxlAQAEKFop"
    "VgoBYwAkBwFqAQAmamF2YS9sYW5nL1JlZmxlY3RpdmVPcGVyYXRpb25FeGNlcHRpb24HAWwBABBqYXZhL2xhbmcvTnVtYmVyCgACAW4MAW8BJAEACHRvU3Ry"
    "aW5nCgDlAXEMAAUBcgEAFShMamF2YS9sYW5nL1N0cmluZzspVgcBdAEAH2phdmEvbGFuZy9OdW1iZXJGb3JtYXRFeGNlcHRpb24IAXYBAAALAKwAfwsANAF5"
    "DAF6AXsBAAhlbnRyeVNldAEAESgpTGphdmEvdXRpbC9TZXQ7BwF9AQATamF2YS91dGlsL01hcCRFbnRyeQsBfAF/DAGAAIsBAAZnZXRLZXkLAXwBJgEACVNp"
    "Z25hdHVyZQEATkxqYXZhL3V0aWwvY29uY3VycmVudC9Db25jdXJyZW50SGFzaE1hcDxMamF2YS9sYW5nL1N0cmluZztMamF2YS9sYW5nL09iamVjdDs+OwEA"
    "YkxqYXZhL3V0aWwvY29uY3VycmVudC9Db3B5T25Xcml0ZUFycmF5TGlzdDxMamF2YS91dGlsL01hcDxMamF2YS9sYW5nL1N0cmluZztMamF2YS9sYW5nL09i"
    "amVjdDs+Oz47AQAEQ29kZQEAD0xpbmVOdW1iZXJUYWJsZQEAJihMamF2YS9sYW5nL1N0cmluZzspTGphdmEvbGFuZy9PYmplY3Q7AQAVKExqYXZhL2xhbmcv"
    "U3RyaW5nOylKAQANU3RhY2tNYXBUYWJsZQEAKChMamF2YS9sYW5nL1N0cmluZztMamF2YS9sYW5nL09iamVjdDtJKVYBACgoTGphdmEvbGFuZy9TdHJpbmc7"
    "TGphdmEvbGFuZy9PYmplY3Q7SilWAQApKExqYXZhL2xhbmcvU3RyaW5nO0xqYXZhL2xhbmcvT2JqZWN0O0lJKVYBACkoTGphdmEvbGFuZy9TdHJpbmc7TGph"
    "dmEvbGFuZy9PYmplY3Q7SkopVgEAB2dldEhhc2gBADgoTGphdmEvbGFuZy9TdHJpbmc7TGphdmEvbGFuZy9TdHJpbmc7KUxqYXZhL2xhbmcvT2JqZWN0OwEA"
    "DXB1dEZpZWxkVmFsdWUBAAZnZXRNYXABACMoTGphdmEvbGFuZy9PYmplY3Q7KUxqYXZhL3V0aWwvTWFwOwEASShMamF2YS9sYW5nL09iamVjdDspTGphdmEv"
    "dXRpbC9NYXA8TGphdmEvbGFuZy9TdHJpbmc7TGphdmEvbGFuZy9PYmplY3Q7PjsBAEooTGphdmEvbGFuZy9PYmplY3Q7TGphdmEvdXRpbC9NYXA8TGphdmEv"
    "bGFuZy9TdHJpbmc7TGphdmEvbGFuZy9PYmplY3Q7PjspVgEAJShMamF2YS9sYW5nL09iamVjdDtMamF2YS91dGlsL01hcDtJKVYBAEsoTGphdmEvbGFuZy9P"
    "YmplY3Q7TGphdmEvdXRpbC9NYXA8TGphdmEvbGFuZy9TdHJpbmc7TGphdmEvbGFuZy9PYmplY3Q7PjtJKVYBADgoTGphdmEvdXRpbC9NYXA8TGphdmEvbGFu"
    "Zy9TdHJpbmc7TGphdmEvbGFuZy9PYmplY3Q7PjspVgEAEyhMamF2YS91dGlsL01hcDtJKVYBADkoTGphdmEvdXRpbC9NYXA8TGphdmEvbGFuZy9TdHJpbmc7"
    "TGphdmEvbGFuZy9PYmplY3Q7PjtJKVYBACcoTGphdmEvbGFuZy9TdHJpbmc7TGphdmEvbGFuZy9TdHJpbmc7KUoBAApjb3VudFRvdGFsAQALY291bnRWYWx1"
    "ZXMBADUoW0xib3VuZGxlc3MvdHlwZXMvY2FjaGUvRmlsdGVyQ29uZDspTGphdmEvdXRpbC9MaXN0OwEAbChbTGJvdW5kbGVzcy90eXBlcy9jYWNoZS9GaWx0"
    "ZXJDb25kOylMamF2YS91dGlsL0xpc3Q8TGphdmEvdXRpbC9NYXA8TGphdmEvbGFuZy9TdHJpbmc7TGphdmEvbGFuZy9PYmplY3Q7Pjs+OwEANihJW0xib3Vu"
    "ZGxlc3MvdHlwZXMvY2FjaGUvRmlsdGVyQ29uZDspTGphdmEvdXRpbC9MaXN0OwEAbShJW0xib3VuZGxlc3MvdHlwZXMvY2FjaGUvRmlsdGVyQ29uZDspTGph"
    "dmEvdXRpbC9MaXN0PExqYXZhL3V0aWwvTWFwPExqYXZhL2xhbmcvU3RyaW5nO0xqYXZhL2xhbmcvT2JqZWN0Oz47PjsBAFUoTGJvdW5kbGVzcy90eXBlcy9j"
    "YWNoZS9Tb3J0Q29uZDtbTGJvdW5kbGVzcy90eXBlcy9jYWNoZS9GaWx0ZXJDb25kOylMamF2YS91dGlsL0xpc3Q7AQCMKExib3VuZGxlc3MvdHlwZXMvY2Fj"
    "aGUvU29ydENvbmQ7W0xib3VuZGxlc3MvdHlwZXMvY2FjaGUvRmlsdGVyQ29uZDspTGphdmEvdXRpbC9MaXN0PExqYXZhL3V0aWwvTWFwPExqYXZhL2xhbmcv"
    "U3RyaW5nO0xqYXZhL2xhbmcvT2JqZWN0Oz47PjsBAI0oSUxib3VuZGxlc3MvdHlwZXMvY2FjaGUvU29ydENvbmQ7W0xib3VuZGxlc3MvdHlwZXMvY2FjaGUv"
    "RmlsdGVyQ29uZDspTGphdmEvdXRpbC9MaXN0PExqYXZhL3V0aWwvTWFwPExqYXZhL2xhbmcvU3RyaW5nO0xqYXZhL2xhbmcvT2JqZWN0Oz47PjsBACUoTGJv"
    "dW5kbGVzcy90eXBlcy9jYWNoZS9GaWx0ZXJDb25kOylKAQAHZ2V0TGlzdAEANihMamF2YS9sYW5nL1N0cmluZztMamF2YS9sYW5nL09iamVjdDspTGphdmEv"
    "dXRpbC9MaXN0OwEAbShMamF2YS9sYW5nL1N0cmluZztMamF2YS9sYW5nL09iamVjdDspTGphdmEvdXRpbC9MaXN0PExqYXZhL3V0aWwvTWFwPExqYXZhL2xh"
    "bmcvU3RyaW5nO0xqYXZhL2xhbmcvT2JqZWN0Oz47PjsBAAtkcm9wRGF0YVNldAEAC2dldERpc3RpbmN0AQBJKExqYXZhL2xhbmcvU3RyaW5nOylMamF2YS91"
    "dGlsL01hcDxMamF2YS9sYW5nL1N0cmluZztMamF2YS9sYW5nL09iamVjdDs+OwEAC2NyZWF0ZUluZGV4AQAWKExqYXZhL2xhbmcvU3RyaW5nO1opVgEABWxw"
    "dXNoAQAoKExqYXZhL2xhbmcvU3RyaW5nO1tMamF2YS9sYW5nL1N0cmluZzspSgcBsAEAE1tMamF2YS9sYW5nL1N0cmluZzsHAbIBABNqYXZhL2xhbmcvVGhy"
    "b3dhYmxlAQAEbHBvcAEAJihMamF2YS9sYW5nL1N0cmluZzspTGphdmEvbGFuZy9TdHJpbmc7AQAFcnB1c2gBAARycG9wAQAFbHJhbmcBACYoTGphdmEvbGFu"
    "Zy9TdHJpbmc7SkopTGphdmEvdXRpbC9MaXN0OwEAOihMamF2YS9sYW5nL1N0cmluZztKSilMamF2YS91dGlsL0xpc3Q8TGphdmEvbGFuZy9TdHJpbmc7PjsB"
    "AARsbGVuAQAkKExqYXZhL2xhbmcvU3RyaW5nOylMamF2YS9sYW5nL0xvbmc7AQAGZXhwaXJlAQAlKExqYXZhL2xhbmcvU3RyaW5nO0kpTGphdmEvbGFuZy9M"
    "b25nOwEACGV4cGlyZUF0AQAlKExqYXZhL2xhbmcvU3RyaW5nO0opTGphdmEvbGFuZy9Mb25nOwEAB3B1Ymxpc2gBADYoTGphdmEvbGFuZy9TdHJpbmc7TGph"
    "dmEvbGFuZy9TdHJpbmc7KUxqYXZhL2xhbmcvTG9uZzsBAApzcGF3bkNhY2hlAQAsKExqYXZhL2xhbmcvU3RyaW5nOylMYm91bmRsZXNzL3R5cGVzL0lDYWNo"
    "ZTsBAD4oTGphdmEvbGFuZy9TdHJpbmc7KUxqYXZhL3V0aWwvQXJyYXlEZXF1ZTxMamF2YS9sYW5nL1N0cmluZzs+OwEAWyhMamF2YS91dGlsL01hcDxMamF2"
    "YS9sYW5nL1N0cmluZztMamF2YS9sYW5nL09iamVjdDs+O1tMYm91bmRsZXNzL3R5cGVzL2NhY2hlL0ZpbHRlckNvbmQ7KVoBAFooTGphdmEvdXRpbC9NYXA8"
    "TGphdmEvbGFuZy9TdHJpbmc7TGphdmEvbGFuZy9PYmplY3Q7PjtMYm91bmRsZXNzL3R5cGVzL2NhY2hlL0ZpbHRlckNvbmQ7KVoBAFsoTGphdmEvdXRpbC9N"
    "YXA8TGphdmEvbGFuZy9TdHJpbmc7TGphdmEvbGFuZy9PYmplY3Q7PjtMamF2YS9sYW5nL1N0cmluZzspTGphdmEvbGFuZy9PYmplY3Q7AQBKKExqYXZhL3V0"
    "aWwvTWFwPCoqPjspTGphdmEvdXRpbC9NYXA8TGphdmEvbGFuZy9TdHJpbmc7TGphdmEvbGFuZy9PYmplY3Q7PjsBAA5sYW1iZGEkY291bnQkMgEANShbTGJv"
    "dW5kbGVzcy90eXBlcy9jYWNoZS9GaWx0ZXJDb25kO0xqYXZhL3V0aWwvTWFwOylaAQAObGFtYmRhJGNvdW50JDEBACUoTGphdmEvbGFuZy9TdHJpbmc7Skxq"
    "YXZhL3V0aWwvTWFwOylaAQAObGFtYmRhJGNvdW50JDABADYoTGphdmEvbGFuZy9TdHJpbmc7TGphdmEvbGFuZy9TdHJpbmc7TGphdmEvdXRpbC9NYXA7KVoB"
    "AApTb3VyY2VGaWxlAQAWTG9jYWxDYWNoZUZhY3RvcnkuamF2YQEACE5lc3RIb3N0AQAQQm9vdHN0cmFwTWV0aG9kcxAAKQ8FAdUKAAsB1gwBzQHOEAHYAQAS"
    "KExqYXZhL3V0aWwvTWFwOylaDwUB2goACwHbDAHLAcwPBQHdCgALAd4MAckByhAAHg8IAeEKAAsBcRAB4wEAQShMamF2YS9sYW5nL1N0cmluZzspTGhvcm9z"
    "YS9vZmZsaW5lL0xvY2FsQ2FjaGVGYWN0b3J5JExvY2FsQ2FjaGU7DwYB5QoB5gHnBwHoDAHpAeoBACJqYXZhL2xhbmcvaW52b2tlL0xhbWJkYU1ldGFmYWN0"
    "b3J5AQALbWV0YWZhY3RvcnkBAMwoTGphdmEvbGFuZy9pbnZva2UvTWV0aG9kSGFuZGxlcyRMb29rdXA7TGphdmEvbGFuZy9TdHJpbmc7TGphdmEvbGFuZy9p"
    "bnZva2UvTWV0aG9kVHlwZTtMamF2YS9sYW5nL2ludm9rZS9NZXRob2RUeXBlO0xqYXZhL2xhbmcvaW52b2tlL01ldGhvZEhhbmRsZTtMamF2YS9sYW5nL2lu"
    "dm9rZS9NZXRob2RUeXBlOylMamF2YS9sYW5nL2ludm9rZS9DYWxsU2l0ZTsBAAxJbm5lckNsYXNzZXMBAApMb2NhbENhY2hlAQALTWl4T3BlcmF0b3IBAAVF"
    "bnRyeQcB8AEAJWphdmEvbGFuZy9pbnZva2UvTWV0aG9kSGFuZGxlcyRMb29rdXAHAfIBAB5qYXZhL2xhbmcvaW52b2tlL01ldGhvZEhhbmRsZXMBAAZMb29r"
    "dXAAMAALAAIAAQEHAAMAEgAZABoAAAASAA4ADwABAYIAAAACAYMAEgAVABYAAQGCAAAAAgGEAD4AAAAFAXIAAQGFAAAASAADAAIAAAAgKrcAASq7AAdZtwAJ"
    "tQAKKrsAEFm3ABK1ABMqK7UAF7EAAAABAYYAAAAWAAUAAABRAAQATgAPAE8AGgBSAB8AUwABACEAMwABAYUAAAArAAQAAwAAAA8qtAAKKyostgAbtgAfV7EA"
    "AAABAYYAAAAKAAIAAABXAA4AWAABACUBhwABAYUAAAAlAAMAAgAAAA0qKrQACiu2ACO2ABuwAAAAAQGGAAAABgABAAAAXAABACgBMwABAYUAAAAhAAIAAgAA"
    "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"
)

def _windows_long_paths_enabled() -> bool:
    """注册表里的 LongPathsEnabled。读不到就当没开（保守，宁可多给一次提示）。"""
    if os.name != "nt":
        return False
    try:
        import winreg  # type: ignore[import-not-found]

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem"
        ) as key:
            value, _ = winreg.QueryValueEx(key, "LongPathsEnabled")
            return int(value) == 1
    except Exception:  # noqa: BLE001
        return False


def _platform_dead_end_advice(platform_name: str) -> dict[str, Any]:
    """没有原生载荷时给出真正的出路，而不是把人卡在「不支持」四个字上。

    🔴 之前这条错误只说「manifest 里没有这个平台」。Intel Mac 与 Linux 用户由此以为是发布疏漏，
    于是反复重试、或去下载 arm64 包（在 Rosetta 下起不来：嵌入式 JDK/Python 是原生二进制）。
    离线载荷确实只发 darwin-arm64 与 win32-x64 —— 但**网关模式**在任何平台上都可用：Python 包
    本身跨平台，把 HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT 指向一台装了 runtime 的机器即可。
    """
    gateway = (
        "网关模式：在一台受支持的机器（darwin-arm64 / win32-x64）上跑 runtime，本机只装 Python 包，"
        "设 HOROSA_SERVER_ROOT 与 HOROSA_CHART_SERVER_ROOT 指过去即可（外部模式，本机不启动任何服务）。"
    )
    if platform_name.startswith("darwin-x64"):
        reason = (
            "Intel Mac 没有原生离线载荷；arm64 那份**不能**在 Rosetta 下跑（内含的 JDK 与 Python "
            "是原生 arm64 二进制）。"
        )
    elif platform_name.startswith("linux"):
        reason = "Linux 没有发布载荷（实验性）；可自建载荷，或走网关模式。"
    elif platform_name.startswith("win32-arm64"):
        reason = "Windows on ARM 没有原生载荷；x64 那份在模拟层下未经验证。"
    else:
        reason = f"平台 `{platform_name}` 没有发布载荷。"
    return {
        "reason": reason,
        "next_action": gateway,
        "agent_recovery": {
            "must_ask_user": False,
            "prompt_to_user": f"{reason} {gateway}",
        },
    }


def _hand_lock_to(lock_path: Path, pid: Any) -> None:
    """把启动锁的持有者改写成启动器自己的 pid（锁的寿命 = 一次启动的寿命）。

    改写失败就直接释放：宁可放两个启动器进来（启动脚本本身对「端口已占用」是拒绝而非覆盖），
    也不要留下一把没人能回收的锁把后续所有启动挡死。
    """
    if not isinstance(pid, int) or pid <= 0:
        release_lock(lock_path)
        return
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        release_lock(lock_path)
        return
    payload["pid"] = pid
    payload["owner"] = "runtime-launcher"
    try:
        lock_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError:
        release_lock(lock_path)


class HorosaRuntimeManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.runtime_root = settings.runtime_root
        self.current_dir = settings.runtime_current_dir
        self.tracer = TraceRecorder(settings)
        self._service_lock = threading.Lock()
        # 上一次「Java 起不来、只剩 chart」的启动时刻（monotonic）；冷却期内 start_local_services 不重启。
        self._last_degraded_start_at: float | None = None

    def java_backend_cooldown_remaining(self) -> float:
        """Seconds left in the degraded-chart-only retry cooldown (0 when healthy / expired / disabled).

        In-process timestamp first; falls back to the runtime state file so a fresh CLI process after an
        MCP server's degraded start does not immediately tear the healthy chart service down again.
        """
        cooldown = float(self.settings.runtime_java_retry_cooldown_seconds or 0.0)
        if cooldown <= 0:
            return 0.0
        if self._last_degraded_start_at is not None:
            return max(0.0, cooldown - (time.monotonic() - self._last_degraded_start_at))
        state = self.load_runtime_state()
        if not isinstance(state, dict) or state.get("status") != "degraded_chart_only":
            return 0.0
        try:
            updated = datetime.fromisoformat(str(state.get("updated_at") or ""))
        except ValueError:
            return 0.0
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=UTC)
        return max(0.0, cooldown - (datetime.now(UTC) - updated).total_seconds())

    def load_installed_manifest(self, *, strict: bool = False) -> dict[str, Any] | None:
        manifest_path = self.current_dir / "runtime-manifest.json"
        if not manifest_path.is_file():
            return None
        try:
            manifest = self._normalize_manifest_data(
                json.loads(manifest_path.read_text(encoding="utf-8")),
                manifest_path=manifest_path,
            )
        except (OSError, json.JSONDecodeError, RuntimeValidationError) as exc:
            if strict:
                if isinstance(exc, RuntimeValidationError):
                    raise
                raise RuntimeValidationError(
                    "Installed runtime manifest is invalid.",
                    code="runtime.manifest_invalid",
                    details={"manifest_path": str(manifest_path), "error": str(exc)},
                ) from exc
            return None
        return manifest

    def load_runtime_state(self, *, strict: bool = False) -> dict[str, Any] | None:
        path = self.settings.runtime_state_path
        if not path.is_file():
            return None
        payload = runtime_registry.read_state(path)
        if payload is None and strict:
            raise RuntimeValidationError(
                "Runtime state file is invalid.",
                code="runtime.state_invalid",
                details={"path": str(path)},
            )
        return payload

    def install(
        self,
        *,
        archive: str | None = None,
        manifest_url: str | None = None,
        platform_key: str | None = None,
        force: bool = False,
        progress: Any | None = None,
    ) -> dict[str, Any]:
        with self.tracer.span(
            workflow_name="runtime.install",
            metadata={"entrypoint": "runtime.install", "archive": archive, "manifest_url": manifest_url, "force": force},
        ) as trace:
            platform_name = platform_key or self.settings.runtime_platform or _platform_key()
            source = archive
            expected_sha256: str | None = None
            asset_meta: dict[str, Any] | None = None
            manifest_data: dict[str, Any] | None = None

            if source is None:
                manifest_location = manifest_url or self.settings.runtime_manifest_url
                if not manifest_location:
                    manifest_location = self.settings.default_runtime_manifest_url
                manifest_data = self._read_json_location(manifest_location)
                platforms = manifest_data.get("platforms", {})
                asset_meta = platforms.get(platform_name)
                if not isinstance(asset_meta, dict):
                    raise RuntimeInstallError(
                        f"Runtime manifest does not include platform `{platform_name}`.",
                        code="runtime.install_missing_platform",
                        details={
                            "platform": platform_name,
                            "manifest_url": manifest_location,
                            "supported_platforms": sorted(k for k in platforms if isinstance(k, str)),
                            **_platform_dead_end_advice(platform_name),
                        },
                    )
                source = str(asset_meta.get("url") or "").strip()
                expected_sha256 = str(asset_meta.get("sha256") or "").strip() or None
                if not source:
                    raise RuntimeInstallError(
                        f"Runtime asset URL missing for platform `{platform_name}`.",
                        code="runtime.install_missing_url",
                        details={"platform": platform_name, "manifest_url": manifest_location},
                    )
                # 版本短路：manifest 版本与已装 current 版本一致且非 --force → 直接跳过大包下载。
                # （损坏 manifest 读为 None 不短路 → 自然走重装；--archive 路径仍由解包后深比较兜底。）
                if not force and self.current_dir.exists():
                    installed_manifest = self.load_installed_manifest()
                    installed_version = str((installed_manifest or {}).get("version") or "").strip()
                    target_version = str(manifest_data.get("version") or "").strip()
                    if installed_version and target_version and installed_version == target_version:
                        return {
                            "ok": True,
                            "installed": True,
                            "changed": False,
                            "skipped_download": True,
                            "version": installed_version,
                            "platform": platform_name,
                            "runtime_root": str(self.runtime_root),
                            "current_dir": str(self.current_dir),
                            "manifest": installed_manifest,
                            "next_action": "已是最新版本，无需重新下载；如需强制重装请加 --force。",
                            "trace_id": trace["trace_id"],
                            "group_id": trace["group_id"],
                        }

            self._require_install_disk_space(asset_meta)
            self.runtime_root.mkdir(parents=True, exist_ok=True)
            # 临时目录置于 runtime_root 同卷（非系统 /tmp）：最终 shutil.move(payload_root→current)
            # 落到同一文件系统即为原子 rename，避免跨卷退化成「复制+删除」（慢，且中途失败留半装）。
            with tempfile.TemporaryDirectory(prefix=".horosa-install-", dir=self.runtime_root) as temp_dir_raw:
                temp_dir = Path(temp_dir_raw)
                archive_path = self._materialize_archive(source, temp_dir, progress=progress)
                if expected_sha256 and _sha256_file(archive_path).lower() != expected_sha256.lower():
                    raise RuntimeValidationError(
                        "Runtime archive checksum mismatch.",
                        code="runtime.install_sha256_mismatch",
                        details={"archive": str(archive_path), "expected_sha256": expected_sha256},
                    )
                # manifest 声明的归档类型必须与资产扩展名一致（防声明 zip 实传 tar.gz 之类的静默错配）。
                declared_type = str((asset_meta or {}).get("archive_type") or "").strip().lower()
                if declared_type:
                    lower_name = archive_path.name.lower()
                    is_tar = lower_name.endswith(".tar.gz") or lower_name.endswith(".tgz")
                    is_zip = lower_name.endswith(".zip")
                    # 仅当文件名带可识别扩展名却与声明相矛盾时才拒装（真错配）；无扩展名的
                    # 下载 URL（预签名/?asset= 式）无从判断 → 放行，交由后续解压按魔数处理，
                    # 避免把合法资产误判为类型不符。
                    contradicts = (
                        (declared_type in {"tar.gz", "tgz"} and is_zip)
                        or (declared_type == "zip" and is_tar)
                    )
                    if contradicts:
                        raise RuntimeValidationError(
                            "Runtime archive type mismatch between manifest and asset.",
                            code="runtime.install_archive_type_mismatch",
                            details={"archive": str(archive_path), "declared_archive_type": declared_type},
                        )

                extract_dir = temp_dir / "extract"
                extract_dir.mkdir(parents=True, exist_ok=True)
                self._extract_archive(archive_path, extract_dir)
                payload_root = self._locate_payload_root(extract_dir)
                manifest = self._validate_payload_root(payload_root)
                manifest = self._bind_service_urls(manifest)
                (payload_root / "runtime-manifest.json").write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

                previous_dir = self.runtime_root / "previous"
                if previous_dir.exists():
                    shutil.rmtree(previous_dir)
                if self.current_dir.exists():
                    if not force:
                        current_manifest = self.load_installed_manifest()
                        if current_manifest == manifest:
                            return {
                                "ok": True,
                                "installed": True,
                                "changed": False,
                                "platform": platform_name,
                                "runtime_root": str(self.runtime_root),
                                "current_dir": str(self.current_dir),
                                "manifest": manifest,
                                "trace_id": trace["trace_id"],
                                "group_id": trace["group_id"],
                            }
                    self.current_dir.replace(previous_dir)

                target_parent = self.current_dir.parent
                target_parent.mkdir(parents=True, exist_ok=True)
                # 原子换入 + 失败回滚：move/overrides 任一失败即把旧运行时从 previous 还原回 current，
                # 绝不留下缺失/半装的 current（否则下次 install 会先 rmtree previous 毁掉唯一好副本）。
                # 注意 overrides 失败时 move 已成功 → current 存在但半装，必须先清掉再从 previous 还原
                # （不能只在 current 缺失时才回滚）。
                try:
                    shutil.move(str(payload_root), str(self.current_dir))
                    self._apply_runtime_overrides(manifest)
                except Exception:
                    if previous_dir.exists():
                        try:
                            if self.current_dir.exists():
                                shutil.rmtree(self.current_dir, ignore_errors=True)
                            previous_dir.replace(self.current_dir)
                        except Exception:  # noqa: BLE001 - best-effort restore; surface original error
                            logger.exception("runtime install rollback failed")
                    raise
                if previous_dir.exists():
                    shutil.rmtree(previous_dir)

            # 安装成功后清理断点续传缓存（失败路径保留 .part 供下次续传）。
            downloads_dir = self.runtime_root / "downloads"
            if downloads_dir.exists():
                shutil.rmtree(downloads_dir, ignore_errors=True)

            trace["platform"] = platform_name
            trace["manifest_version"] = manifest.get("version")
            return {
                "ok": True,
                "installed": True,
                "changed": True,
                "platform": platform_name,
                "runtime_root": str(self.runtime_root),
                "current_dir": str(self.current_dir),
                "manifest": manifest,
                "asset": asset_meta or {},
                "release_manifest": manifest_data or {},
                "next_action": "接下来：`uv run horosa-skill doctor` 确认体检，`uv run horosa-skill serve` 启动 MCP，或把本服务注册到你的 AI 客户端（见 README「接入 AI 客户端」）。",
                "trace_id": trace["trace_id"],
                "group_id": trace["group_id"],
            }

    def uninstall(self, *, purge_data: bool = False, yes: bool = False) -> dict[str, Any]:
        """卸载离线 runtime：默认 dry-run 返回将删清单；yes=True 才执行（先停服务再删）。

        purge_data=True 时额外删除用户数据目录（memory.db/runs/traces）——不可恢复，需显式选择。
        """
        removal_plan: list[str] = []
        for path in (self.current_dir, self.runtime_root / "previous", self.runtime_root / "downloads"):
            if path.exists():
                removal_plan.append(str(path))
        state_path = self.settings.runtime_state_path
        if state_path.exists():
            removal_plan.append(str(state_path))
        if purge_data and self.settings.data_dir.exists():
            removal_plan.append(str(self.settings.data_dir))

        if not yes:
            return {
                "ok": True,
                "dry_run": True,
                "would_remove": removal_plan,
                "purge_data": purge_data,
                "next_action": "确认无误后追加 --yes 执行删除；用户数据默认保留（--purge-data 才删 memory/runs/traces）。",
            }

        try:
            self.stop_local_services()
        except Exception:  # noqa: BLE001 - 卸载前停服务尽力而为，失败不阻断删除
            pass
        removed: list[str] = []
        for text in removal_plan:
            path = Path(text)
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.exists():
                    path.unlink()
                removed.append(text)
            except OSError as exc:
                raise RuntimeInstallError(
                    f"Failed to remove {path}: {exc}",
                    code="runtime.uninstall_failed",
                    details={"path": text, "removed_so_far": removed},
                ) from exc
        return {"ok": True, "dry_run": False, "removed": removed, "purge_data": purge_data}

    def doctor(self) -> dict[str, Any]:
        with self.tracer.span(workflow_name="runtime.doctor", metadata={"entrypoint": "runtime.doctor"}) as trace:
            manifest_issue: dict[str, Any] | None = None
            runtime_state_issue: dict[str, Any] | None = None
            installed = self.current_dir.exists()
            try:
                manifest = self.load_installed_manifest(strict=True)
            except RuntimeValidationError as exc:
                manifest = None
                manifest_issue = {"code": exc.code, "message": str(exc), "details": exc.details}
            try:
                runtime_state = self.load_runtime_state(strict=True)
            except RuntimeValidationError as exc:
                runtime_state = None
                runtime_state_issue = {"code": exc.code, "message": str(exc), "details": exc.details}
            required = [(label, path, kind, True) for label, path, kind in self._required_paths(manifest)]
            optional = self._optional_paths(manifest)
            files = []
            for label, relative_path, kind, required_flag in [*required, *optional]:
                absolute = self.current_dir / relative_path
                exists = absolute.is_dir() if kind == "dir" else absolute.is_file()
                files.append(
                    {
                        "label": label,
                        "path": str(absolute),
                        "exists": exists,
                        "required": required_flag,
                    }
                )

            python_path = self._relative_manifest_path(manifest, "runtimes", "python")
            java_path = self._relative_manifest_path(manifest, "runtimes", "java")
            start_script = self._relative_manifest_path(manifest, "services", "start_script")
            stop_script = self._relative_manifest_path(manifest, "services", "stop_script")
            endpoints = self._service_status(manifest)

            issues = []
            if manifest_issue:
                issues.append(manifest_issue["code"])
            if runtime_state_issue:
                issues.append(runtime_state_issue["code"])
            for entry in files:
                if not entry["exists"]:
                    issues.append(f"missing:{entry['label']}")
            degraded: str | None = None
            java_diagnostics: dict[str, Any] | None = None
            if installed and not self._all_services_reachable(endpoints):
                if self._chart_only_degraded(endpoints):
                    # Issue #14: name the half that is down and surface WHY — a silently dead
                    # Java backend was previously indistinguishable from "nothing running".
                    issues.append("services:java_backend_not_running")
                    degraded = "chart_only"
                    java_diagnostics = self._java_boot_diagnostics(manifest)
                elif self._any_services_reachable(endpoints):
                    issues.append("services:chart_not_running")
                else:
                    issues.append("services:not_running")

            trace["issues"] = issues
            manifest_version = manifest.get("version") if manifest else None
            runtime_payload_version = manifest.get("runtime_payload_version") if manifest else None
            return {
                "ok": not issues,
                "installed": installed,
                "platform": self.settings.runtime_platform or _platform_key(),
                "runtime_root": str(self.runtime_root),
                "current_dir": str(self.current_dir),
                "manifest_version": manifest_version,
                "runtime_payload_version": runtime_payload_version,
                "manifest": manifest,
                "manifest_issue": manifest_issue,
                "runtime_state": runtime_state,
                "runtime_state_issue": runtime_state_issue,
                "paths": {
                    "python": str(self.current_dir / python_path),
                    "java": str(self.current_dir / java_path),
                    "node": str(self.current_dir / self._relative_manifest_path(manifest, "runtimes", "node")),
                    "start_script": str(self.current_dir / start_script),
                    "stop_script": str(self.current_dir / stop_script),
                },
                "files": files,
                "endpoints": endpoints,
                "issues": issues,
                "degraded": degraded,
                "java_diagnostics": java_diagnostics,
                "trace_id": trace["trace_id"],
                "group_id": trace["group_id"],
            }

    def start_local_services(self, *, wait_seconds: float | None = None) -> dict[str, Any]:
        """启动本机 runtime。

        `wait_seconds=None` = 用满 runtime_start_timeout_seconds（`runtime start`/install/selfcheck）；
        工具调用路径传一个小预算，超出即返回 `{"starting": True, "retry_after_seconds": …}`。
        """
        mode = self.runtime_mode()
        if mode == "external":
            # 外部模式：地址是用户给的，只探不起不停。
            manifest = self.load_installed_manifest() if self.current_dir.exists() else None
            endpoints = self.endpoint_identities(manifest)
            reachable = self._all_services_reachable(endpoints)
            if not reachable:
                raise RuntimeInstallError(
                    "外部模式（已显式设置 HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT）下服务不可达。",
                    code="runtime.external_unreachable",
                    details={
                        "endpoints": endpoints,
                        "next_action": (
                            "确认那台机器上的 Horosa 服务在跑且地址可达；"
                            "要改用本机 runtime，请取消 HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT。"
                        ),
                        "will_not_start": "外部模式下本工具不会在本机启动 runtime。",
                    },
                )
            self._write_runtime_state({
                "managed": False,
                "mode": "external",
                "status": "external",
                "updated_at": self._utc_now(),
                "endpoints": endpoints,
            })
            return {
                "ok": True, "already_running": True, "mode": "external", "command": None,
                "stdout": "", "stderr": "", "endpoints": endpoints,
                "trace_id": None, "group_id": None,
            }
        with self._service_lock:
            with self.tracer.span(workflow_name="runtime.start", metadata={"entrypoint": "runtime.start"}) as trace:
                self._require_runtime()
                manifest = self.load_installed_manifest(strict=True)
                patched_files: list[str] = []
                initial_status = self.endpoint_identities(manifest)
                # 可达但不是我们的 → 报冲突并退出；绝不采用、绝不代为终止。
                self._require_no_foreign_holders(initial_status)
                if self._all_services_reachable(initial_status):
                    if self.load_runtime_state() is None:
                        self._write_runtime_state(
                            {
                                "managed": False,
                                "status": "already_running",
                                "updated_at": self._utc_now(),
                                "manifest_version": manifest.get("version") if manifest else None,
                                "platform": manifest.get("platform") if manifest else (self.settings.runtime_platform or _platform_key()),
                            }
                        )
                    return {
                        "ok": True,
                        "already_running": True,
                        "command": None,
                        "stdout": "",
                        "stderr": "",
                        "endpoints": initial_status,
                        "trace_id": trace["trace_id"],
                        "group_id": trace["group_id"],
                    }

                recovered_partial_state = False
                recovery_details: dict[str, Any] | None = None
                if self._chart_only_degraded(initial_status):
                    remaining = self.java_backend_cooldown_remaining()
                    if remaining > 0:
                        # Java 挂、chart 健康、冷却期内：不许为了再试 Java 先杀掉健康的 chart 服务再全量重启
                        # （v0.36.0 前每个碰 Java 的调用都这么干一次——含 qimen 等前置 /nongli/time 的技法）。
                        return {
                            "ok": True,
                            "already_running": True,
                            "degraded": True,
                            "skipped_restart": True,
                            "cooldown_remaining_seconds": round(remaining, 1),
                            "command": None,
                            "stdout": "",
                            "stderr": "",
                            "endpoints": initial_status,
                            "trace_id": trace["trace_id"],
                            "group_id": trace["group_id"],
                        }
                # 🔴 旧实现在「部分可达」时先 stop 一遍再全量重启（L715-717）。那一步会把**健康的**
                # 那半边也停掉：Java 起不来时，每一次碰 Java 的调用都要顺手弄死正常的 chart 服务，
                # 再赌一次全量启动。既然此刻已确认可达的那些都是我们自己的（上面的冲突检查放行了），
                # 就让启动脚本自己去补齐缺的那半边 —— 它本来就是幂等的。
                # 跨进程启动锁：`self._service_lock` 只挡得住**本进程**。两个 MCP 客户端
                # （Claude Desktop 与 Cursor，或一个 serve 与一次 doctor）同时冷启动时，两边各起
                # 一个启动器：抢同一个端口、互相覆盖 pid 文件，后到的看见「pid files already
                # exist」就先 stop 再 start —— 把先到的那个刚起好的服务停掉。
                # 锁的持有者写成**启动器自己的 pid**，于是锁的寿命恰好等于一次启动；启动器崩了
                # 锁自动可回收（pidlock 的死持有者判定），不需要看门狗线程。
                budget = (
                    float(self.settings.runtime_start_timeout_seconds)
                    if wait_seconds is None
                    else max(0.0, float(wait_seconds))
                )
                lock_path = self.runtime_root / ".runtime-start.lock"
                if not try_pid_lock(lock_path, stale_after_seconds=960.0, owner="runtime-start"):
                    holder = describe_lock(lock_path)
                    waited = self._wait_for_service_state(
                        expected_reachable=True, timeout_seconds=budget, manifest=manifest
                    )
                    if waited["ready"]:
                        return {
                            "ok": True, "already_running": True, "started_by_other_process": True,
                            "command": None, "stdout": "", "stderr": "", "endpoints": waited["endpoints"],
                            "trace_id": trace["trace_id"], "group_id": trace["group_id"],
                        }
                    return {
                        "ok": True, "starting": True, "started_by_other_process": True,
                        "retry_after_seconds": 5,
                        "elapsed_seconds": round(budget, 1),
                        "budget_seconds": round(budget, 1),
                        "cap_seconds": float(self.settings.runtime_start_timeout_seconds),
                        "launcher": holder,
                        "command": None, "stdout": "", "stderr": "",
                        "endpoints": waited["endpoints"],
                        "trace_id": trace["trace_id"], "group_id": trace["group_id"],
                    }
                lock_released = False
                # 加锁之后的**每一条**出口都必须释放：抛 runtime.start_failed / start_timeout /
                # launcher_patch_anchor_missing 时若把锁留着，而本进程（一个长命的 serve）还活着，
                # pidlock 的「活持有者永不回收」就会把后续所有启动永久挡死。
                try:
                    patched_files = self._apply_runtime_overrides(manifest)
                    script = self.current_dir / self._relative_manifest_path(manifest, "services", "start_script")
                    if not script.exists():
                        raise RuntimeValidationError(
                            f"Runtime start script missing: {script}",
                            code="runtime.start_script_missing",
                            details={"path": str(script)},
                        )

                    # 一次性身份口令：写进注册表并透给启动器，`/horosaIdentity` 会原样回报。
                    # 这是「这个端口上的服务是不是**这次**启动的那一份」唯一可靠的答案 —— 仅靠 app
                    # 标记分不出用户自己开着的星阙桌面端。
                    launch_nonce = secrets.token_urlsafe(16)

                    def _remember_nonce(state: dict[str, Any]) -> dict[str, Any]:
                        state["launch_nonce"] = launch_nonce
                        state["mode"] = "managed"
                        state["ports"] = {
                            "backend": self.settings.local_backend_port,
                            "chart": self.settings.local_chart_port,
                        }
                        return state

                    self._update_runtime_state(_remember_nonce)

                    env = os.environ.copy()
                    env["HOROSA_LAUNCH_NONCE"] = launch_nonce
                    env.setdefault("HOROSA_SERVER_PORT", str(self.settings.local_backend_port))
                    env.setdefault("HOROSA_CHART_PORT", str(self.settings.local_chart_port))
                    home_value = self._default_home_value()
                    env.setdefault("HOME", home_value)
                    if os.name == "nt":
                        env.setdefault("USERPROFILE", home_value)
                        drive, tail = os.path.splitdrive(home_value)
                        if drive:
                            env.setdefault("HOMEDRIVE", drive)
                            env.setdefault("HOMEPATH", tail or "\\")

                    command = self._platform_command(script)
                    completed, readiness = self._run_start_command(
                        command=command,
                        script=script,
                        env=env,
                        manifest=manifest,
                        wait_seconds=budget,
                    )
                    if readiness.get("starting"):
                        # 启动器还在跑。锁交给它的 pid 持有（谁都别再起第二个），本次调用先回
                        # 「正在启动」，让调用方过几秒重试同一个调用，而不是干等几分钟被客户端掐断。
                        _hand_lock_to(lock_path, readiness.get("launcher_pid"))
                        lock_released = True
                        self._write_runtime_state({
                            "managed": True, "mode": "managed", "status": "starting",
                            "updated_at": self._utc_now(),
                            "manifest_version": manifest.get("version") if manifest else None,
                            "platform": manifest.get("platform") if manifest else (self.settings.runtime_platform or _platform_key()),
                            "command": command,
                        })
                        return {
                            "ok": True, "starting": True,
                            "retry_after_seconds": 5,
                            "elapsed_seconds": readiness.get("elapsed_seconds"),
                            "budget_seconds": readiness.get("budget_seconds"),
                            "cap_seconds": readiness.get("cap_seconds"),
                            "first_start": not (self.runtime_root / ".started-once").exists(),
                            "launcher_log": readiness.get("launcher_log"),
                            "launcher_pid": readiness.get("launcher_pid"),
                            "command": command, "stdout": completed.stdout[-4000:], "stderr": "",
                            "endpoints": readiness["endpoints"],
                            "patched_files": patched_files,
                            "trace_id": trace["trace_id"], "group_id": trace["group_id"],
                        }
                    retried_after_cleanup = False
                    combined_output = f"{completed.stdout}\n{completed.stderr}".lower()
                    if (
                        completed.returncode != 0
                        and not readiness["ready"]
                        and (
                            self._any_services_reachable(readiness["endpoints"])
                            or "pid files already exist" in combined_output
                        )
                    ):
                        recovery_details = self.stop_local_services()
                        recovered_partial_state = True
                        retried_after_cleanup = True
                        completed, readiness = self._run_start_command(
                            command=command,
                            script=script,
                            env=env,
                            manifest=manifest,
                            wait_seconds=budget,
                        )
                    degraded = bool(readiness.get("degraded"))
                    self._last_degraded_start_at = time.monotonic() if degraded else None
                    startup_warning: dict[str, Any] | None = None
                    if degraded:
                        startup_warning = {
                            "code": "runtime.start_degraded_chart_only",
                            "message": (
                                "Java backend (:9999) did not become ready; running degraded on the chart service only. "
                                "Chart-side techniques (三式 ken/神数/地占/塔罗/西占 chart 族) stay available; "
                                "Java-side ones (nongli/bazi/ziwei/liureng and 占时 casts) will error until it recovers. "
                                "Run `uv run horosa-skill doctor` for the captured Java boot error."
                            ),
                            "details": {
                                "command": command,
                                "returncode": completed.returncode,
                                "stdout": completed.stdout[-4000:],
                                "stderr": completed.stderr[-4000:],
                                "retried_after_cleanup": retried_after_cleanup,
                                "java_diagnostics": self._java_boot_diagnostics(manifest),
                            },
                        }
                    elif completed.returncode != 0 and readiness["ready"]:
                        startup_warning = {
                            "code": "runtime.start_nonzero_but_ready",
                            "message": "Runtime start script exited non-zero, but all required services became reachable.",
                            "details": {
                                "command": command,
                                "returncode": completed.returncode,
                                "stdout": completed.stdout[-4000:],
                                "stderr": completed.stderr[-4000:],
                                "retried_after_cleanup": retried_after_cleanup,
                            },
                        }
                    elif completed.returncode != 0:
                        raise RuntimeInstallError(
                            "Failed to start local Horosa runtime.",
                            code="runtime.start_failed",
                            details={
                                "command": command,
                                "stdout": completed.stdout[-4000:],
                                "stderr": completed.stderr[-4000:],
                                "endpoints": readiness["endpoints"],
                            },
                        )
                    if not readiness["ready"]:
                        raise RuntimeInstallError(
                            "Local Horosa runtime did not become ready in time.",
                            code="runtime.start_timeout",
                            details={
                                "command": command,
                                "timeout_seconds": self.settings.runtime_start_timeout_seconds,
                                "endpoints": readiness["endpoints"],
                            },
                        )
                    if degraded:
                        runtime_status = "degraded_chart_only"
                    elif startup_warning:
                        runtime_status = "running_with_warnings"
                    else:
                        runtime_status = "running"
                    self._write_runtime_state(
                        {
                            "managed": True,
                            "status": runtime_status,
                            "updated_at": self._utc_now(),
                            "manifest_version": manifest.get("version") if manifest else None,
                            "platform": manifest.get("platform") if manifest else (self.settings.runtime_platform or _platform_key()),
                            "command": command,
                            "startup_warning": startup_warning,
                            "recovered_partial_state": recovered_partial_state,
                        }
                    )
                    if not lock_released:
                        release_lock(lock_path)
                        lock_released = True
                    try:
                        (self.runtime_root / ".started-once").touch()
                    except OSError:
                        pass
                    trace["command"] = command
                    trace["patched_files"] = patched_files
                    return {
                        "ok": True,
                        "already_running": False,
                        "degraded": degraded,
                        "command": command,
                        "stdout": completed.stdout[-4000:],
                        "stderr": completed.stderr[-4000:],
                        "endpoints": readiness["endpoints"],
                        "warning": startup_warning,
                        "patched_files": patched_files,
                        "recovered_partial_state": recovered_partial_state,
                        "recovery": recovery_details,
                        "trace_id": trace["trace_id"],
                        "group_id": trace["group_id"],
                    }
                finally:
                    if not lock_released:
                        release_lock(lock_path)

    def stop_local_services(self, *, force: bool = False) -> dict[str, Any]:
        """停止本机 runtime。**只停我们自己起的那一份。**

        🔴 停脚本按端口/pid 文件动手。如果那个端口上跑的其实是用户自己开着的星阙桌面端（同一个
        app 标记、同一个默认端口），一次 `runtime stop`（或旧代码里那些「先 stop 再重启」的反射）
        就会把用户正在用的程序关掉。所以这里要求**强证据**（nonce 相等 / 命令行含我方 runtime 根 /
        我方注册表里的 pid 仍活着）才动手；只有 app 标记不算数。
        """
        if self.runtime_mode() == "external":
            return {
                "ok": True, "already_stopped": True, "mode": "external", "refused": True,
                "reason": "external_mode",
                "message": "外部模式（HOROSA_SERVER_ROOT/HOROSA_CHART_SERVER_ROOT 已显式设置）下不会停止任何服务。",
                "command": None, "stdout": "", "stderr": "", "returncode": 0,
                "endpoints": self.endpoint_identities(None), "trace_id": None, "group_id": None,
            }
        with self.tracer.span(workflow_name="runtime.stop", metadata={"entrypoint": "runtime.stop"}) as trace:
            self._require_runtime()
            manifest = self.load_installed_manifest(strict=True)
            script = self.current_dir / self._relative_manifest_path(manifest, "services", "stop_script")
            initial_status = self.endpoint_identities(manifest)
            reachable_now = [item for item in initial_status if item.get("reachable")]
            not_ours = [
                item for item in reachable_now
                if not ((item.get("identity") or {}).get("started_by_us"))
            ]
            if reachable_now and not_ours and not force:
                return {
                    "ok": False, "already_stopped": False, "refused": True,
                    "reason": "not_started_by_us",
                    "code": "runtime.stop_refused_foreign",
                    "message": (
                        "这些端口上的服务不是本工具启动的（可能是你自己开着的星阙桌面端或另一个实例），"
                        "已拒绝停止。"
                    ),
                    "next_action": (
                        "确认要停的就是它们时用 `runtime stop --force`；"
                        "只是想腾出端口给本工具，请改端口"
                        "（HOROSA_LOCAL_BACKEND_PORT / HOROSA_LOCAL_CHART_PORT，或 HOROSA_PORTS=auto）。"
                    ),
                    "conflicts": not_ours,
                    "command": None, "stdout": "", "stderr": "", "returncode": 0,
                    "endpoints": initial_status,
                    "trace_id": trace["trace_id"], "group_id": trace["group_id"],
                }
            if not any(item["reachable"] for item in initial_status):
                self._clear_runtime_state()
                return {
                    "ok": True,
                    "already_stopped": True,
                    "command": None,
                    "stdout": "",
                    "stderr": "",
                    "returncode": 0,
                    "endpoints": initial_status,
                    "trace_id": trace["trace_id"],
                    "group_id": trace["group_id"],
                }
            if not script.exists():
                raise RuntimeValidationError(
                    f"Runtime stop script missing: {script}",
                    code="runtime.stop_script_missing",
                    details={"path": str(script)},
                )
            command = self._platform_command(script)
            completed = subprocess.run(
                command,
                cwd=str(script.parent),
                env=os.environ.copy(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            shutdown = self._wait_for_service_state(
                expected_reachable=False,
                timeout_seconds=max(3.0, min(self.settings.runtime_start_timeout_seconds, 10.0)),
                manifest=manifest,
            )
            if completed.returncode == 0 and shutdown["ready"]:
                self._clear_runtime_state()
            else:
                self._write_runtime_state(
                    {
                        "managed": True,
                        "status": "stop_requested",
                        "updated_at": self._utc_now(),
                        "manifest_version": manifest.get("version") if manifest else None,
                        "platform": manifest.get("platform") if manifest else (self.settings.runtime_platform or _platform_key()),
                    }
                )
            trace["command"] = command
            return {
                "ok": completed.returncode == 0 and shutdown["ready"],
                "already_stopped": False,
                "command": command,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
                "returncode": completed.returncode,
                "endpoints": shutdown["endpoints"],
                "trace_id": trace["trace_id"],
                "group_id": trace["group_id"],
            }

    def _require_runtime(self) -> None:
        if not self.current_dir.exists():
            raise RuntimeValidationError(
                "Horosa 离线 runtime 尚未安装（runtime is not installed）。",
                code="runtime.not_installed",
                details={
                    "current_dir": str(self.current_dir),
                    "next_action": "运行 `uv run horosa-skill install` 安装离线 runtime（约 730MB 下载），随后 `uv run horosa-skill doctor` 确认。",
                    "agent_recovery": {
                        "kind": "install_required",
                        "prompt_to_user": "本地 Horosa 运行时还没安装。请在仓库目录执行：uv run horosa-skill install（首次约需数分钟下载 730MB），装好后重试本次请求。",
                        "commands": ["uv run horosa-skill install", "uv run horosa-skill doctor"],
                    },
                },
            )

    def _materialize_archive(self, source: str, temp_dir: Path, *, progress: Any | None = None) -> Path:
        if _is_url(source):
            parsed = urlparse(source)
            if parsed.scheme == "file":
                return self._file_url_to_path(source)
            return self._download_with_resume(source, temp_dir, progress=progress)
        local_path = Path(source).expanduser().resolve()
        if not local_path.is_file():
            # 结构化错误（CLI 的 except RuntimeInstallError/RuntimeValidationError 能干净接住并出
            # {ok:false,code,...}），而非内置 RuntimeError 冒泡成 traceback。
            raise RuntimeInstallError(
                f"Runtime archive not found: {local_path}",
                code="runtime.install_archive_missing",
                details={"archive": str(local_path)},
            )
        return local_path

    def _mirror_candidates(self, url: str) -> list[str]:
        """HOROSA_RUNTIME_MIRROR（逗号分隔前缀）对 github.com URL 做前缀替换：镜像在前、原始 URL 兜底。"""
        mirrors = [m.strip().rstrip("/") for m in (os.environ.get("HOROSA_RUNTIME_MIRROR") or "").split(",") if m.strip()]
        if not mirrors or not url.startswith("https://github.com/"):
            return [url]
        suffix = url[len("https://github.com"):]
        return [f"{mirror}{suffix}" for mirror in mirrors] + [url]

    def _download_with_resume(
        self,
        source: str,
        temp_dir: Path,
        *,
        attempts: int = 3,
        progress: Any | None = None,
    ) -> Path:
        """流式下载 + HTTP Range 断点续传 + 有限退避重试 + 多镜像回退。

        .part 分块存 runtime_root/downloads（跨 install 调用可续传）；206 续写、200 重下兜底；
        最终 sha256 校验（install 主流程）兜住续传坏块。progress(done, total|None) 供 CLI 回调。
        """
        filename = Path(urlparse(source).path).name or "runtime-archive"
        downloads_dir = self.runtime_root / "downloads"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        part_path = downloads_dir / f"{filename}.part"
        candidates = self._mirror_candidates(source)
        failures: list[str] = []
        for candidate in candidates:
            for attempt in range(attempts):
                try:
                    offset = part_path.stat().st_size if part_path.exists() else 0
                    headers = {"Range": f"bytes={offset}-"} if offset else {}
                    with httpx.Client(timeout=httpx.Timeout(60.0, read=120.0), follow_redirects=True) as client:
                        with client.stream("GET", candidate, headers=headers) as response:
                            response.raise_for_status()
                            if response.status_code == 206:
                                mode = "ab"
                                total = offset + int(response.headers.get("Content-Length") or 0) or None
                                done = offset
                            else:
                                # 服务器不支持 Range（或无 .part）→ 从头重下。
                                mode = "wb"
                                total = int(response.headers.get("Content-Length") or 0) or None
                                done = 0
                            with open(part_path, mode) as handle:
                                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                                    handle.write(chunk)
                                    done += len(chunk)
                                    if progress is not None:
                                        progress(done, total)
                    target = temp_dir / filename
                    shutil.move(str(part_path), str(target))
                    return target
                except httpx.HTTPStatusError as exc:
                    failures.append(f"{candidate}: HTTP {exc.response.status_code}")
                    if exc.response.status_code < 500:
                        break  # 4xx 换 URL 无益重试同 URL
                except httpx.HTTPError as exc:
                    failures.append(f"{candidate}: {exc}")
                except OSError as exc:
                    raise RuntimeInstallError(
                        f"Failed to write runtime archive to disk: {exc}",
                        code="runtime.install_write_failed",
                        details={"target": str(part_path)},
                    ) from exc
                if attempt < attempts - 1:
                    time.sleep((3 ** attempt))  # 1s/3s 退避（最后一次不等）
        raise RuntimeInstallError(
            "Failed to download runtime archive from all sources.",
            code="runtime.install_download_failed",
            details={
                "source": source,
                "attempts_per_source": attempts,
                "failures": failures[-6:],
                "resume_note": f"已下载分块保留在 {part_path}（若存在），重试 install 会从断点续传。",
            },
        )

    def _read_json_location(self, location: str) -> dict[str, Any]:
        if _is_url(location):
            parsed = urlparse(location)
            if parsed.scheme == "file":
                return json.loads(self._file_url_to_path(location).read_text(encoding="utf-8"))
            last_error: Exception | None = None
            for candidate in self._mirror_candidates(location):
                try:
                    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                        response = client.get(candidate)
                        response.raise_for_status()
                        return response.json()
                except httpx.HTTPError as exc:
                    last_error = exc
            raise RuntimeInstallError(
                f"Failed to fetch runtime manifest: {last_error}",
                code="runtime.install_manifest_fetch_failed",
                details={"location": location},
            ) from last_error
        return json.loads(Path(location).expanduser().read_text(encoding="utf-8"))

    def _file_url_to_path(self, location: str) -> Path:
        parsed = urlparse(location)
        path_text = url2pathname(parsed.path or "")
        if parsed.netloc and parsed.netloc not in {"", "localhost"}:
            if os.name == "nt":
                path_text = f"\\\\{parsed.netloc}{path_text}"
            else:
                path_text = f"//{parsed.netloc}{path_text}"
        elif os.name == "nt" and path_text.startswith("\\") and len(path_text) >= 3 and path_text[2] == ":":
            path_text = path_text[1:]
        return Path(path_text)

    def _guard_windows_long_paths(self, archive_path: Path, extract_dir: Path) -> None:
        r"""解包前先算最长目标路径，>259 且没开长路径支持就明说，别让 winerror 3/206 裸奔。

        🔴 Horosa 载荷里最深的条目（嵌入式 JDK 的 module 目录 + Horosa-Web 的多层 vendor 树）
        接近 200 字符。用户把 runtime 装在 `C:\Users\<长名字>\OneDrive\文档\...` 下时就会越过
        260 上限，解包报 `[WinError 3] 系统找不到指定的路径` —— 那句话对「路径太长」毫无提示。
        """
        if os.name != "nt":
            return
        try:
            names: list[str] = []
            lower = archive_path.name.lower()
            if lower.endswith((".tar.gz", ".tgz")):
                with tarfile.open(archive_path, "r:gz") as archive:
                    names = archive.getnames()
            elif lower.endswith(".zip"):
                with zipfile.ZipFile(archive_path) as archive:
                    names = archive.namelist()
        except Exception:  # noqa: BLE001 - 预检失败不该挡住真正的解包
            return
        if not names:
            return
        longest = max(names, key=len)
        projected = len(str(extract_dir)) + 1 + len(longest)
        if projected <= 259 or _windows_long_paths_enabled():
            return
        raise RuntimeInstallError(
            "Windows 路径长度会超过 260 字符上限，解包必定失败。",
            code="runtime.install_long_path",
            details={
                "projected_length": projected,
                "extract_dir": str(extract_dir),
                "longest_entry": longest,
                "next_action": (
                    "二选一：① 开启 Windows 长路径支持（注册表 "
                    "HKLM\\SYSTEM\\CurrentControlSet\\Control\\FileSystem\\LongPathsEnabled = 1，需重启）；"
                    "② 把 runtime 装到更短的路径：设 HOROSA_RUNTIME_ROOT=C:\\horosa 后重试。"
                ),
            },
        )

    def _extract_archive(self, archive_path: Path, extract_dir: Path) -> None:
        self._guard_windows_long_paths(archive_path, extract_dir)
        name = archive_path.name.lower()
        if name.endswith(".tar.gz") or name.endswith(".tgz"):
            with tarfile.open(archive_path, "r:gz") as archive:
                # filter="data" 已拒绝绝对路径 / .. 穿越 / 设备/symlink 逃逸 → 无需再对整棵 2GB 树逐文件
                # resolve 断言（冗余且慢）；纵深断言只留给下方无 filter 保护的 zip/unpack 分支。
                archive.extractall(extract_dir, filter="data")
            return
        if name.endswith(".zip"):
            # CPython zipfile 已消毒 ../ 与盘符前缀，但显式纵深断言：与 tar 分支对称、且对未来
            # 换用会保留 symlink 的库（zip-slip 复发）多一道防线。
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(extract_dir)
            self._assert_extracted_within(extract_dir)
            return
        shutil.unpack_archive(str(archive_path), str(extract_dir))
        self._assert_extracted_within(extract_dir)

    @staticmethod
    def _assert_extracted_within(extract_dir: Path) -> None:
        # 纵深防护：解压后每个真实路径（解引用 symlink）必须仍在 extract_dir 内，杜绝穿越逃逸。
        root = extract_dir.resolve()
        for path in extract_dir.rglob("*"):
            try:
                resolved = path.resolve()
            except OSError:
                resolved = path
            if not (resolved == root or root in resolved.parents):
                raise RuntimeValidationError(
                    "Runtime archive contains a path that escapes the extraction directory.",
                    code="runtime.install_path_traversal",
                    details={"offending_path": str(path)},
                )

    def _locate_payload_root(self, extract_dir: Path) -> Path:
        candidates = [
            extract_dir / "runtime-payload",
            extract_dir,
        ]
        for candidate in candidates:
            if (candidate / "runtime-manifest.json").is_file():
                return candidate
        for child in extract_dir.iterdir():
            if child.is_dir() and (child / "runtime-manifest.json").is_file():
                return child
        raise RuntimeValidationError(
            "Extracted runtime archive does not contain runtime-manifest.json.",
            code="runtime.install_manifest_missing",
            details={"extract_dir": str(extract_dir)},
        )

    def _manifest_defaults(self) -> dict[str, dict[str, str]]:
        return {
            "services": {
                "backend_url": self.settings.server_root.rstrip("/"),
                "chart_url": self.settings.chart_server_root.rstrip("/"),
                "start_script": str(self._platform_path("Horosa-Web/start_horosa_local.sh", "Horosa-Web/start_horosa_local.ps1")),
                "stop_script": str(self._platform_path("Horosa-Web/stop_horosa_local.sh", "Horosa-Web/stop_horosa_local.ps1")),
            },
            "runtimes": {
                "python": str(self._platform_path("runtime/mac/python/bin/python3", "runtime/windows/python/python.exe", "runtime/linux/python/bin/python3")),
                "java": str(self._platform_path("runtime/mac/java/bin/java", "runtime/windows/java/bin/java.exe", "runtime/linux/java/bin/java")),
                "node": str(self._platform_path("runtime/mac/node/bin/node", "runtime/windows/node/node.exe", "runtime/linux/node/bin/node")),
            },
            "artifacts": {
                "horosa_web_root": "Horosa-Web",
                "astropy_root": "Horosa-Web/astropy",
                "flatlib_root": "Horosa-Web/flatlib-ctrad2/flatlib",
                "swefiles_root": "Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles",
                "boot_jar": str(self._platform_path("runtime/mac/bundle/astrostudyboot.jar", "runtime/windows/bundle/astrostudyboot.jar", "runtime/linux/bundle/astrostudyboot.jar")),
                "horosa_core_js_root": "horosa-core-js",
            },
        }

    def _bind_service_urls(self, manifest: dict[str, Any]) -> dict[str, Any]:
        bound_manifest = dict(manifest)
        services = dict(bound_manifest.get("services") or {})
        services["backend_url"] = self.settings.server_root.rstrip("/")
        services["chart_url"] = self.settings.chart_server_root.rstrip("/")
        bound_manifest["services"] = services
        return bound_manifest

    def _validate_payload_root(self, payload_root: Path) -> dict[str, Any]:
        manifest_path = payload_root / "runtime-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return self._normalize_manifest_data(manifest, manifest_path=manifest_path)

    def _normalize_manifest_data(self, manifest: Any, *, manifest_path: Path) -> dict[str, Any]:
        if not isinstance(manifest, dict) or "version" not in manifest:
            raise RuntimeValidationError(
                "Runtime manifest missing version.",
                code="runtime.manifest_invalid",
                details={"manifest_path": str(manifest_path)},
            )

        defaults = self._manifest_defaults()
        normalized = {
            "schema_version": int(manifest.get("schema_version", 1)),
            "version": str(manifest["version"]),
            "platform": str(manifest.get("platform") or self.settings.runtime_platform or _platform_key()),
            "runtime_layout_version": int(manifest.get("runtime_layout_version", 1)),
            "runtime_payload_version": str(manifest.get("runtime_payload_version") or manifest["version"]),
            "export_registry_version": int(manifest.get("export_registry_version", 6)),
            "services": {**defaults["services"], **(manifest.get("services") or {})},
            "runtimes": {**defaults["runtimes"], **(manifest.get("runtimes") or {})},
            "artifacts": {**defaults["artifacts"], **(manifest.get("artifacts") or {})},
        }
        for section_name in ("services", "runtimes", "artifacts"):
            section = normalized[section_name]
            if not isinstance(section, dict):
                raise RuntimeValidationError(
                    f"Runtime manifest section `{section_name}` must be an object.",
                    code="runtime.manifest_invalid",
                    details={"manifest_path": str(manifest_path), "section": section_name},
                )
            for key, value in section.items():
                if not isinstance(value, str) or not value.strip():
                    raise RuntimeValidationError(
                        f"Runtime manifest field `{section_name}.{key}` must be a non-empty string.",
                        code="runtime.manifest_invalid",
                        details={"manifest_path": str(manifest_path), "field": f"{section_name}.{key}"},
                    )
        return normalized

    def _platform_path(self, mac_relative: str, windows_relative: str, linux_relative: str | None = None) -> Path:
        if os.name == "nt":
            return Path(windows_relative)
        if os.name == "posix" and platform.system().lower() == "linux":
            return Path(linux_relative if linux_relative is not None else mac_relative)
        return Path(mac_relative)

    def _platform_command(self, script: Path) -> list[str]:
        if os.name == "nt":
            if script.suffix.lower() == ".ps1":
                return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
            return [str(script)]
        return ["/bin/bash", str(script)]

    # macOS 启动器补丁：标记 + 五处锚点。上游脚本住在只读的 vendor 树，所以修复走**安装/启动时
    # 打补丁**（与 _patch_windows_boot_jar 同一模式），已装的 runtime 下次 serve/doctor 即打上。
    _MAC_LAUNCHER_PATCH_MARK = "# horosa-skill-launcher-patch v1"
    # 只有出现这个构造才需要打补丁：v0.36.0 随包出货的那版（606 行）用 lsof 探测后直接拒绝，
    # 没有任何 kill 路径；误杀代码在更新的上游版本里，下次重建 runtime 载荷时才会随包出货。
    _MAC_LAUNCHER_DANGER = "reclaim_stale_port"

    _MAC_OWNS_PID_HELPER = """
%(mark)s
# 🔴 上游 reclaim_stale_port 按**命令行子串**（webchartsrv / astrostudyboot）kill -9 端口持有者，
# 注释里写着「绝不误杀第三方」——但星阙桌面端跑的正是这两个镜像，所以那句判断不成立：
# 用户同时开着桌面端时，本 skill 起服务会把桌面端 kill 掉（数据丢失风险）。
# stop_horosa_local.sh 有 `grep -Fq "${ROOT}"` 守卫、Windows 启动器是拒绝而非 kill——
# 唯独 mac 的 start 没跟上。这个 helper 把「是不是我们这套安装」变成可判定的：
#   ① 命令行里出现本安装根目录；或 ② 带 -Dhorosa.runtime.root=<本安装根>（exploded 模式下
#      java 的 argv 是 `java -cp . JarLauncher`，不含 ROOT，只能靠这个显式标记）。
horosa_owns_pid() {
  local _pid="$1" _cmd
  _cmd="$(ps -p "${_pid}" -o command= 2>/dev/null || true)"
  case "${_cmd}" in
    *"${ROOT}"*) return 0 ;;
  esac
  case "${_cmd}" in
    *"-Dhorosa.runtime.root=${ROOT}"*) return 0 ;;
  esac
  return 1
}
""" % {"mark": _MAC_LAUNCHER_PATCH_MARK}

    def _patch_mac_launcher(self, script_path: Path) -> bool:
        """给 macOS 启动器加「只杀自己人」守卫 + 可判定的 root 标记。幂等；锚点不符即拒。

        返回 True 表示打了补丁（或已打过），False 表示这版启动器没有危险构造、无需补丁。
        锚点数不符时抛 RuntimeInstallError 而不是静默跳过 —— 静默跳过等于回到误杀路径，
        而「补丁没打上」在日志里是看不见的。
        """
        try:
            text = script_path.read_text(encoding="utf-8")
        except OSError:
            return False
        if self._MAC_LAUNCHER_PATCH_MARK in text:
            return True
        if self._MAC_LAUNCHER_DANGER not in text:
            return False  # 老版启动器：无 kill 路径，本来就安全

        root_anchor = 'ROOT="$(cd "$(dirname "$0")" && pwd)"\n'
        if text.count(root_anchor) != 1:
            raise RuntimeInstallError(
                "macOS 启动器补丁失败：找不到 ROOT 定义锚点。",
                code="runtime.launcher_patch_anchor_missing",
                details={
                    "script": str(script_path), "anchor": "ROOT=",
                    "next_action": "升级 horosa-skill（uv sync 或 uvx --refresh）后重试；"
                                   "临时跳过设 HOROSA_RUNTIME_LAUNCHER_PATCH=0（会失去误杀保护）。",
                },
            )
        patched = text.replace(root_anchor, root_anchor + self._MAC_OWNS_PID_HELPER, 1)

        kill_anchor = '        kill -9 "${pid}" >/dev/null 2>&1 && killed=1 ;;\n'
        if patched.count(kill_anchor) != 1:
            raise RuntimeInstallError(
                "macOS 启动器补丁失败：reclaim_stale_port 的 kill 锚点不唯一。",
                code="runtime.launcher_patch_anchor_missing",
                details={
                    "script": str(script_path), "anchor": "reclaim_stale_port kill -9",
                    "found": patched.count(kill_anchor),
                    "next_action": "升级 horosa-skill 后重试；临时跳过设 HOROSA_RUNTIME_LAUNCHER_PATCH=0。",
                },
            )
        patched = patched.replace(
            kill_anchor,
            '        horosa_owns_pid "${pid}" || { diag_log "port ${port}: ${tag} pid=${pid} '
            'is NOT ours; refusing to kill"; continue; }\n' + kill_anchor,
            1,
        )

        owner_anchor = "-Dhorosa.runtime.owner="
        owner_count = patched.count(owner_anchor)
        if owner_count == 0:
            raise RuntimeInstallError(
                "macOS 启动器补丁失败：找不到 -Dhorosa.runtime.owner 锚点。",
                code="runtime.launcher_patch_anchor_missing",
                details={"script": str(script_path), "anchor": owner_anchor,
                         "next_action": "升级 horosa-skill 后重试。"},
            )
        # 每个 JVM 启动点都带上本安装根，exploded 模式下才判得出归属。
        patched = re.sub(
            r"(-Dhorosa\.runtime\.owner=[A-Za-z0-9._-]+)",
            r'\1 -Dhorosa.runtime.root="${ROOT}"',
            patched,
        )
        # AppCDS 训练 JVM 的硬编码端口改为可配（39997 与别的程序撞车时目前是静默降级）。
        patched = patched.replace("local train_port=39997", 'local train_port="${HOROSA_CDS_TRAIN_PORT:-39997}"')

        script_path.write_text(patched, encoding="utf-8")
        script_path.chmod(script_path.stat().st_mode | 0o111)
        logger.info("patched macOS launcher with foreign-process kill guard: %s", script_path)
        return True

    def _apply_runtime_overrides(self, manifest: dict[str, Any] | None) -> list[str]:
        patched: list[str] = []
        if sys.platform == "darwin" and os.environ.get("HOROSA_RUNTIME_LAUNCHER_PATCH", "1") != "0":
            start_script = self.current_dir / self._relative_manifest_path(manifest, "services", "start_script")
            if start_script.is_file() and self._patch_mac_launcher(start_script):
                patched.append(str(start_script))
        if os.name == "nt":
            template_root = self._runtime_template_root() / "windows"
            if template_root.exists():
                overrides = {
                    "services.start_script": template_root / "start_horosa_local.ps1",
                    "services.stop_script": template_root / "stop_horosa_local.ps1",
                }
                for field, source in overrides.items():
                    if not source.exists():
                        continue
                    section, key = field.split(".", 1)
                    destination = self.current_dir / self._relative_manifest_path(manifest, section, key)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
                    patched.append(str(destination))

        boot_jar = self.current_dir / self._relative_manifest_path(manifest, "artifacts", "boot_jar")
        if boot_jar.is_file() and self._boot_jar_supports_patch(boot_jar):
            self._patch_windows_boot_jar(manifest, boot_jar)
            patched.append(str(boot_jar))
        return patched

    def _runtime_template_root(self) -> Path:
        # 包内副本（wheel / uvx 安装）优先；源码树回退（scripts/runtime_templates 是 builder 共用的原件）。
        packaged = Path(__file__).resolve().parent / "templates"
        if packaged.is_dir():
            return packaged
        return Path(__file__).resolve().parents[3] / "scripts" / "runtime_templates"

    def _patch_windows_boot_jar(self, manifest: dict[str, Any] | None, jar_path: Path) -> None:
        replacements = {
            WINDOWS_BOOT_CACHE_CONFIG_PATH: self._rewrite_windows_cache_config(
                self._read_archive_entry_text(jar_path, WINDOWS_BOOT_CACHE_CONFIG_PATH)
            ).encode("utf-8"),
            WINDOWS_BOOT_LOG4J_PATH: self._rewrite_runtime_log4j(
                self._read_archive_entry_text(jar_path, WINDOWS_BOOT_LOG4J_PATH)
            ).encode("utf-8"),
            **self._compile_windows_runtime_patch_classes(manifest, jar_path),
        }
        if os.name == "nt":
            replacements[WINDOWS_BOOT_WEBPARAMS_PATH] = self._rewrite_windows_webparams(
                self._read_archive_entry_text(jar_path, WINDOWS_BOOT_WEBPARAMS_PATH)
            ).encode("utf-8")
        self._rewrite_zip_archive(jar_path, replacements)

    def _read_archive_entry_text(self, archive_path: Path, entry_name: str) -> str:
        try:
            with zipfile.ZipFile(archive_path) as archive:
                return archive.read(entry_name).decode("utf-8")
        except KeyError as exc:
            raise RuntimeValidationError(
                f"Runtime archive is missing `{entry_name}`.",
                code="runtime.windows_patch_missing_entry",
                details={"archive": str(archive_path), "entry": entry_name},
            ) from exc
        except (OSError, zipfile.BadZipFile, UnicodeDecodeError) as exc:
            raise RuntimeValidationError(
                "Runtime archive could not be patched for Windows local mode.",
                code="runtime.windows_patch_invalid_archive",
                details={"archive": str(archive_path), "entry": entry_name, "error": str(exc)},
            ) from exc

    def _rewrite_windows_cache_config(self, content: str) -> str:
        payload = json.loads(content)
        if not isinstance(payload, dict):
            raise RuntimeValidationError(
                "Windows cache override expects an object.",
                code="runtime.windows_patch_invalid_cache_config",
            )
        entries = payload.get("cachefactoryclass")
        if not isinstance(entries, list) or not entries:
            raise RuntimeValidationError(
                "Windows cache override expects `cachefactoryclass` to be a non-empty array.",
                code="runtime.windows_patch_invalid_cache_config",
            )
        rewritten: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise RuntimeValidationError(
                    "Windows cache override expects every cache entry to be an object.",
                    code="runtime.windows_patch_invalid_cache_config",
                )
            patched = dict(entry)
            patched["class"] = WINDOWS_LOCAL_CACHE_FACTORY
            patched["config"] = WINDOWS_LOCAL_CACHE_CONFIG
            rewritten.append(patched)
        payload["needlocalmemcache"] = False
        payload["needcompress"] = False
        payload["needhystrix"] = False
        payload["cachefactoryclass"] = rewritten
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    def _rewrite_windows_webparams(self, content: str) -> str:
        updated = re.sub(
            r"(?m)^webencrypt\.rsaparam\.class=.*$",
            "webencrypt.rsaparam.class=",
            content,
        )
        if "webencrypt.rsaparam.class=" not in updated:
            updated = updated.rstrip("\n") + "\nwebencrypt.rsaparam.class=\n"
        if not updated.endswith("\n"):
            updated += "\n"
        return updated

    def _require_install_disk_space(self, asset_meta: dict[str, Any] | None) -> None:
        """下载前先看磁盘够不够——不够就当场说清还差多少，而不是下完 700MB 再在解压时炸。

        峰值占用 ≈ 归档 + 解压后的树 + 保留的 previous，故按归档大小的 4 倍估（未知大小按 700MB 估）。
        失败只在「确知不足」时抛；取不到用量（异常文件系统）一律放行，不因体检本身挡住安装。
        """
        try:
            probe = self.runtime_root if self.runtime_root.exists() else self.runtime_root.parent
            while not probe.exists() and probe != probe.parent:
                probe = probe.parent
            free_bytes = shutil.disk_usage(probe).free
        except OSError:
            return
        archive_bytes = 0
        try:
            archive_bytes = int((asset_meta or {}).get("size") or 0)
        except (TypeError, ValueError):
            archive_bytes = 0
        needed = (archive_bytes * 4) if archive_bytes else 3_000_000_000
        if free_bytes >= needed:
            return
        gib = 1024 ** 3
        raise RuntimeInstallError(
            f"磁盘空间不足：安装离线 runtime 约需 {needed / gib:.1f} GiB（下载 + 解压 + 保留上一版），"
            f"当前可用 {free_bytes / gib:.1f} GiB。请清理后重试，或用 HOROSA_RUNTIME_ROOT 指向空间更充裕的卷。",
            code="runtime.install_insufficient_disk",
            details={
                "required_bytes": needed,
                "free_bytes": free_bytes,
                "runtime_root": str(self.runtime_root),
                "next_action": "腾出空间后重跑 install（已下载的分片会断点续传）。",
            },
        )

    def _rewrite_runtime_log4j(self, content: str) -> str:
        log_root = self._runtime_log_root()
        replaced = False

        def apply_basedir(match: re.Match[str]) -> str:
            nonlocal replaced
            replaced = True
            return f"{match.group(1)}{log_root}{match.group(2)}"

        updated = re.sub(
            r'(<Property\s+name="basedir">).*?(</Property>)',
            apply_basedir,
            content,
            count=1,
            flags=re.DOTALL,
        )
        if replaced:
            return updated
        if updated == content:
            # log4j 的 `${env:HOME}` 有两种写法，第二种带默认值：`${env:HOME:-${sys:user.home}}`。
            # 只替换第一种时，第二种会被 log4j 当作**字面量目录名**，于是日志落进
            # `./${env:HOME:-${sys:user.home}}/.horosa-logs/…`——落在启动时的 CWD，在用户的仓库/工作目录
            # 里留下一个名字诡异的目录，而且谁也不知道日志去哪了。两种形态都要归位。
            for placeholder in (
                "${env:HOME:-${sys:user.home}}/.horosa-logs/astrostudyboot",
                "${env:HOME}/.horosa-logs/astrostudyboot",
            ):
                updated = updated.replace(placeholder, log_root)
            if updated != content:
                return updated
        raise RuntimeValidationError(
            "Runtime log override could not locate the backend log root property.",
            code="runtime.windows_patch_invalid_log4j",
        )

    def _runtime_log_root(self) -> str:
        home_value = self._default_home_value().rstrip("\\/")
        return home_value.replace("\\", "/") + "/.horosa-logs/astrostudyboot"

    def _compile_windows_runtime_patch_classes(
        self,
        manifest: dict[str, Any] | None,
        jar_path: Path,
    ) -> dict[str, bytes]:
        return {
            WINDOWS_LOCAL_CACHE_FACTORY_CLASS_PATH: base64.b64decode(WINDOWS_LOCAL_CACHE_FACTORY_CLASS_B64),
            WINDOWS_LOCAL_CACHE_FACTORY_INNER_CLASS_PATH: base64.b64decode(WINDOWS_LOCAL_CACHE_FACTORY_INNER_CLASS_B64),
        }

    def _extract_boot_lib(self, jar_path: Path, prefix: str, target_path: Path) -> None:
        try:
            with zipfile.ZipFile(jar_path) as archive:
                for entry in archive.infolist():
                    if entry.filename.startswith(prefix) and entry.filename.endswith(".jar"):
                        target_path.write_bytes(archive.read(entry.filename))
                        return
        except (OSError, zipfile.BadZipFile) as exc:
            raise RuntimeValidationError(
                "Runtime archive could not be read while preparing Windows compatibility classes.",
                code="runtime.windows_patch_invalid_archive",
                details={"archive": str(jar_path), "error": str(exc)},
            ) from exc
        raise RuntimeValidationError(
            "Runtime archive does not contain the bundled `boundless` library required for Windows compatibility.",
            code="runtime.windows_patch_missing_boundless",
            details={"archive": str(jar_path)},
        )

    def _rewrite_zip_archive(self, archive_path: Path, replacements: dict[str, bytes]) -> None:
        temp_path = archive_path.with_suffix(f"{archive_path.suffix}.tmp")
        with zipfile.ZipFile(archive_path) as source, zipfile.ZipFile(temp_path, "w") as target:
            target.comment = source.comment
            seen: set[str] = set()
            for info in source.infolist():
                seen.add(info.filename)
                data = replacements.get(info.filename, source.read(info.filename))
                new_info = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                new_info.compress_type = info.compress_type
                new_info.comment = info.comment
                new_info.extra = info.extra
                new_info.internal_attr = info.internal_attr
                new_info.external_attr = info.external_attr
                new_info.create_system = info.create_system
                new_info.flag_bits = info.flag_bits
                target.writestr(new_info, data)

            for entry_name, data in replacements.items():
                if entry_name in seen:
                    continue
                new_info = zipfile.ZipInfo(entry_name)
                new_info.compress_type = zipfile.ZIP_DEFLATED
                new_info.external_attr = 0o644 << 16
                target.writestr(new_info, data)
        temp_path.replace(archive_path)

    def _boot_jar_supports_patch(self, jar_path: Path) -> bool:
        if not zipfile.is_zipfile(jar_path):
            return False
        try:
            with zipfile.ZipFile(jar_path) as archive:
                return WINDOWS_BOOT_CACHE_CONFIG_PATH in archive.namelist()
        except (OSError, zipfile.BadZipFile):
            return False

    def _http_reachable(self, url: str) -> bool:
        # 回环目标绕开用户代理（Clash/VPN 会把 127.0.0.1 也塞进代理 → 后端健康却报 not_running，
        # 见 engine.client.loopback_httpx_client 的说明）。下载/manifest 那两处仍走代理。
        try:
            with loopback_httpx_client(url, timeout=1.5, follow_redirects=True) as client:
                response = client.get(url)
                return response.status_code < 500
        except Exception:
            return False

    def _backend_reachable(self, backend_url: str) -> bool:
        parsed = urlparse(backend_url)
        if not parsed.scheme or not parsed.netloc:
            return False
        server_root = f"{parsed.scheme}://{parsed.netloc}"
        endpoint = parsed.path if parsed.path not in {"", "/"} else "/common/time"
        client = HorosaApiClient(server_root, timeout=3.0)
        return client.probe(endpoint=endpoint)

    def _required_paths(self, manifest: dict[str, Any] | None = None) -> list[tuple[str, Path, str]]:
        return [
            ("manifest", Path("runtime-manifest.json"), "file"),
            ("horosa_web", self._relative_manifest_path(manifest, "artifacts", "horosa_web_root"), "dir"),
            ("astropy", self._relative_manifest_path(manifest, "artifacts", "astropy_root"), "dir"),
            ("flatlib", self._relative_manifest_path(manifest, "artifacts", "flatlib_root"), "dir"),
            ("swefiles", self._relative_manifest_path(manifest, "artifacts", "swefiles_root"), "dir"),
            ("start_script", self._relative_manifest_path(manifest, "services", "start_script"), "file"),
            ("stop_script", self._relative_manifest_path(manifest, "services", "stop_script"), "file"),
            ("java_runtime", self._relative_manifest_path(manifest, "runtimes", "java"), "file"),
            ("python_runtime", self._relative_manifest_path(manifest, "runtimes", "python"), "file"),
            ("node_runtime", self._relative_manifest_path(manifest, "runtimes", "node"), "file"),
            ("boot_jar", self._relative_manifest_path(manifest, "artifacts", "boot_jar"), "file"),
            ("horosa_core_js_root", self._relative_manifest_path(manifest, "artifacts", "horosa_core_js_root"), "dir"),
        ]

    def _optional_paths(self, manifest: dict[str, Any] | None = None) -> list[tuple[str, Path, str, bool]]:
        return []

    def _relative_manifest_path(self, manifest: dict[str, Any] | None, section: str, key: str) -> Path:
        if manifest and isinstance(manifest.get(section), dict):
            value = manifest[section].get(key)
            if isinstance(value, str) and value.strip():
                return Path(value)
        defaults = self._manifest_defaults()
        return Path(defaults[section][key])

    def _service_status(self, manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
        backend_url = self.settings.server_root.rstrip("/")
        chart_url = self.settings.chart_server_root.rstrip("/")
        if manifest and isinstance(manifest.get("services"), dict):
            backend_url = str(manifest["services"].get("backend_url") or backend_url)
            chart_url = str(manifest["services"].get("chart_url") or chart_url)
        explicit_backend_url = os.environ.get("HOROSA_SERVER_ROOT", "").strip()
        explicit_chart_url = os.environ.get("HOROSA_CHART_SERVER_ROOT", "").strip()
        if explicit_backend_url:
            backend_url = explicit_backend_url.rstrip("/")
        if explicit_chart_url:
            chart_url = explicit_chart_url.rstrip("/")
        backend_probe = backend_url
        parsed_backend = urlparse(backend_url)
        if parsed_backend.scheme and parsed_backend.netloc and parsed_backend.path in {"", "/"}:
            backend_probe = backend_url.rstrip("/") + "/common/time"
        return [
            {"label": "java_backend", "url": backend_probe, "reachable": self._backend_reachable(backend_probe)},
            {"label": "python_chart", "url": chart_url, "reachable": self._http_reachable(chart_url)},
        ]

    def runtime_mode(self) -> str:
        """`external` = 用户把地址指到了**我们管不着的地方**，只探不起不停；否则 `managed`。

        🔴 旧实现对显式地址一视同仁：探到不可达就去跑**本机**的启动脚本，探到部分可达又会先
        stop 一遍 —— 指着同事机器 / 容器网关（docker-compose 里就是 host.docker.internal:9999）
        的用户，一次工具调用就可能让本机起一整套 runtime，或者去停一个根本不归自己管的服务。

        但「显式设了地址」≠「外部」：把 HOROSA_SERVER_ROOT 指到本机 runtime 自己的
        127.0.0.1:9999 是完全正常的用法，那种情况仍是 managed，`runtime start` 照常启动。
        判据因此是**地址是否就是我们会去启动的那一个**（回环主机名等价，端口须相同）。
        """
        ours = {
            (True, int(self.settings.local_backend_port)),
            (True, int(self.settings.local_chart_port)),
        }
        for name in ("HOROSA_SERVER_ROOT", "HOROSA_CHART_SERVER_ROOT"):
            raw = os.environ.get(name, "").strip()
            if not raw:
                continue
            parsed = urlparse(raw if "//" in raw else f"//{raw}")
            host = (parsed.hostname or "").lower()
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            if (host in {"127.0.0.1", "localhost", "::1"}, int(port)) not in ours:
                return "external"
        return "managed"

    def _launch_nonce(self) -> str | None:
        state = self.load_runtime_state() or {}
        nonce = state.get("launch_nonce")
        return str(nonce) if nonce else None

    def endpoint_identities(
        self, manifest: dict[str, Any] | None, *, endpoints: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        """给每个端点补上归属判定。

        **只在决策点调用**（start 入口、stop 入口、doctor、runtime status），不要放进
        `_wait_for_service_state` 的 0.25 秒轮询里 —— 判定要跑 netstat/ps 子进程，放进轮询会把
        一次启动的开销翻好几倍。
        """
        items = endpoints if endpoints is not None else self._service_status(manifest)
        state = self.load_runtime_state() or {}
        nonce = self._launch_nonce()
        service_pids = state.get("service_pids") or []
        enriched: list[dict[str, Any]] = []
        for item in items:
            entry = dict(item)
            if not entry.get("reachable"):
                entry["identity"] = None
                enriched.append(entry)
                continue
            verdict: EndpointIdentity = classify_endpoint(
                str(entry.get("url") or ""),
                runtime_root=self.runtime_root,
                launch_nonce=nonce,
                service_pids=service_pids,
            )
            entry["identity"] = verdict.as_dict()
            enriched.append(entry)
        return enriched

    @staticmethod
    def _verdict_of(entry: dict[str, Any]) -> str | None:
        identity = entry.get("identity")
        return (identity or {}).get("verdict") if isinstance(identity, dict) else None

    def _require_no_foreign_holders(self, endpoints: list[dict[str, Any]]) -> None:
        """可达但**不是我们的**服务：报冲突，绝不采用、绝不代为终止。

        🔴 旧实现只看「HTTP 响应码 < 500」，于是 8899/9999 上任何应答者都被静默采用为后端：
        用户自己开着的星阙桌面端、另一个项目的开发服务器、一个 `python -m http.server`。
        症状不是「连不上」，而是排盘失败却 statusCode 200，或请求被发去一个无关服务。
        """
        conflicts = [
            {
                "port": (entry.get("identity") or {}).get("port"),
                "url": entry.get("url"),
                "label": entry.get("label"),
                "evidence": (entry.get("identity") or {}).get("evidence"),
                "app": (entry.get("identity") or {}).get("app"),
                "holders": (entry.get("identity") or {}).get("holders") or [],
            }
            for entry in endpoints
            if self._verdict_of(entry) == "foreign"
        ]
        if conflicts:
            raise RuntimeInstallError(
                "本机的 Horosa 服务端口被**其它进程**占用，已停止启动以免误用或误杀。",
                code="runtime.port_conflict_foreign",
                details={
                    "conflicts": conflicts,
                    "next_action": (
                        "换端口：设 HOROSA_LOCAL_BACKEND_PORT 或 HOROSA_LOCAL_CHART_PORT，"
                        "或设 HOROSA_PORTS=auto 让本工具自动挑空闲端口；"
                        "若那正是你想用的服务，设 HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT 指向它（外部模式）。"
                    ),
                    "will_not_kill": "本工具不会终止不属于自己的进程；要腾出端口请你自己关掉上面点名的进程。",
                },
            )
        unknown = [
            {
                "port": (entry.get("identity") or {}).get("port"),
                "url": entry.get("url"),
                "label": entry.get("label"),
                "holders": (entry.get("identity") or {}).get("holders") or [],
            }
            for entry in endpoints
            if self._verdict_of(entry) == "unknown"
        ]
        if unknown and not trust_unknown_ports():
            raise RuntimeInstallError(
                "端口上有服务在应答，但查不出它是不是 Horosa 的 —— 未予采用。",
                code="runtime.port_conflict_unknown_holder",
                details={
                    "conflicts": unknown,
                    "next_action": (
                        "确认那确实是 Horosa 后端后，设 HOROSA_RUNTIME_TRUST_PORTS=1 采用它；"
                        "否则换端口（HOROSA_LOCAL_BACKEND_PORT / HOROSA_LOCAL_CHART_PORT，或 HOROSA_PORTS=auto）。"
                    ),
                    "will_not_kill": "本工具不会终止不属于自己的进程。",
                },
            )

    def _all_services_reachable(self, endpoints: list[dict[str, Any]]) -> bool:
        return bool(endpoints) and all(bool(item.get("reachable")) for item in endpoints)

    def _any_services_reachable(self, endpoints: list[dict[str, Any]]) -> bool:
        return any(bool(item.get("reachable")) for item in endpoints)

    def _chart_only_degraded(self, endpoints: list[dict[str, Any]]) -> bool:
        chart = next((item for item in endpoints if item.get("label") == "python_chart"), None)
        java = next((item for item in endpoints if item.get("label") == "java_backend"), None)
        return bool(chart and chart.get("reachable")) and bool(java and not java.get("reachable"))

    def _java_boot_diagnostics(self, manifest: dict[str, Any] | None) -> dict[str, Any] | None:
        """Best-effort excerpt of the Java backend's boot failure; never raises.

        The launcher redirects the jar's stdout/stderr under <Horosa-Web>/.horosa-local-logs/<run>/.
        A backend that dies during Spring bean construction takes its log4j file appenders with it,
        so without this excerpt doctor can only say "not running" (issue #14).
        """
        try:
            script = self._relative_manifest_path(manifest, "services", "start_script")
            log_root = self.current_dir / script.parent / ".horosa-local-logs"
            if not log_root.is_dir():
                return None
            run_dirs = sorted((path for path in log_root.iterdir() if path.is_dir()), key=lambda path: path.name)
            if not run_dirs:
                return None
            latest = run_dirs[-1]
            markers = (
                "Application run failed",
                "APPLICATION FAILED TO START",
                "BeanInstantiationException",
                "Caused by:",
            )
            excerpt: list[str] = []
            for name in ("astrostudyboot.stderr.log", "astrostudyboot.stdout.log"):
                log_path = latest / name
                if not log_path.is_file():
                    continue
                lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                marked = [line.strip() for line in lines if any(marker in line for marker in markers)]
                if marked:
                    excerpt.extend(marked[:8])
                else:
                    excerpt.extend(line.strip() for line in lines[-5:] if line.strip())
            if not excerpt:
                return None
            return {"log_dir": str(latest), "excerpt": excerpt[:12]}
        except Exception:
            return None

    # 启动器日志：Popen 的 stdout/stderr 都往这里追加（O_APPEND，多进程写不会互相截断）。
    LAUNCHER_LOG_NAME = "launcher.log"

    def _launcher_log_path(self) -> Path:
        return self.runtime_root / self.LAUNCHER_LOG_NAME

    def _spawn_start_command(
        self, *, command: list[str], script: Path, env: dict[str, str]
    ) -> tuple[subprocess.Popen[bytes], Path]:
        """把启动器**分离**着跑起来，立即返回。

        🔴 旧实现是 `subprocess.run(...)` —— 而启动器自己会一直阻塞到服务就绪或 STARTUP_TIMEOUT
        （首次运行要解压 + CDS 训练，实测可达 300–900 秒）。于是「第一次调用某个技法」会在**一次
        MCP 请求内**卡上几分钟：Codex 的 tool_timeout_sec 默认 60 秒、其它客户端各有默认，
        用户看到的是工具超时，而 runtime 其实正在正常启动。分离 + 有界等待把这件事变成
        「先回一个 runtime.starting，让调用方过几秒重试同一个调用」。
        """
        log_path = self._launcher_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(log_path, "ab", buffering=0)  # noqa: SIM115 - 交给子进程持有，见 finally
        try:
            kwargs: dict[str, Any] = {
                "cwd": str(script.parent),
                "env": env,
                "stdout": handle,
                "stderr": subprocess.STDOUT,
                "stdin": subprocess.DEVNULL,
            }
            if os.name == "nt":
                # getattr 兜底：这两个常量只在真 Windows 的 subprocess 上存在，而把 os.name
                # 打成 "nt" 的跨平台模拟测试会走到这一支。
                kwargs["creationflags"] = getattr(
                    subprocess, "CREATE_NEW_PROCESS_GROUP", 0
                ) | getattr(subprocess, "DETACHED_PROCESS", 0)
            else:
                kwargs["start_new_session"] = True
            proc = subprocess.Popen(command, **kwargs)
        finally:
            # 父进程这边立刻关掉：句柄已经复制给子进程了。留着它会在 Windows 上让日志文件
            # 无法被删除/轮转，在 POSIX 上则让 `tail -f` 看不到 EOF。
            handle.close()
        return proc, log_path

    def _read_launcher_log(self, log_path: Path, *, limit: int = 8000) -> str:
        try:
            data = log_path.read_bytes()
        except OSError:
            return ""
        return data[-limit:].decode("utf-8", errors="replace")

    def _run_start_command(
        self,
        *,
        command: list[str],
        script: Path,
        env: dict[str, str],
        manifest: dict[str, Any] | None,
        wait_seconds: float | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
        """启动并在预算内等待就绪。预算用尽仍未就绪时 readiness["starting"]=True。

        `wait_seconds=None` = 用满 runtime_start_timeout_seconds（`runtime start` / install /
        selfcheck 走这条，行为与从前一致）；工具调用路径传一个小预算（默认 5 秒）。
        """
        budget = (
            float(self.settings.runtime_start_timeout_seconds)
            if wait_seconds is None
            else max(0.0, float(wait_seconds))
        )
        started_at = time.monotonic()
        log_before = self._launcher_log_path()
        log_offset = log_before.stat().st_size if log_before.is_file() else 0
        proc, log_path = self._spawn_start_command(command=command, script=script, env=env)
        self._record_launcher(proc.pid, log_path)

        deadline = started_at + budget
        endpoints = self._service_status(manifest)
        java_dead_deadline: float | None = None
        while True:
            if all(item["reachable"] for item in endpoints):
                break
            exited = proc.poll() is not None
            tail = self._read_launcher_log(log_path)[max(0, 0):]
            if java_dead_deadline is None and "java backend process exited" in tail.lower():
                # Issue #14：启动器已明说 java 死了，别再耗满整个就绪窗口等一个永远不会来的端点。
                java_dead_deadline = min(deadline, time.monotonic() + 20.0)
            effective_deadline = min(deadline, java_dead_deadline) if java_dead_deadline else deadline
            if exited:
                # 启动器退出后再看最后一眼：它可能刚把服务拉起来。
                endpoints = self._service_status(manifest)
                break
            if time.monotonic() >= effective_deadline:
                break
            time.sleep(0.25)
            endpoints = self._service_status(manifest)

        returncode = proc.poll()
        output = self._read_launcher_log(log_path)
        if log_offset and len(output) > 0:
            # 只保留本次启动写进去的那一段（日志是追加的，上一次的内容不该被当成这次的诊断）。
            try:
                with open(log_path, "rb") as handle:
                    handle.seek(log_offset)
                    output = handle.read().decode("utf-8", errors="replace")
            except OSError:
                pass
        completed = subprocess.CompletedProcess(
            args=command,
            returncode=0 if returncode is None else returncode,
            stdout=output[-8000:],
            stderr="",
        )
        ready = all(item["reachable"] for item in endpoints)
        readiness: dict[str, Any] = {"ready": ready, "endpoints": endpoints, "degraded": False}
        if not ready and returncode is None:
            # 启动器还在跑 —— 这不是失败，是「还没好」。
            readiness["starting"] = True
            readiness["launcher_pid"] = proc.pid
            readiness["launcher_log"] = str(log_path)
            readiness["elapsed_seconds"] = round(time.monotonic() - started_at, 1)
            readiness["budget_seconds"] = round(budget, 1)
            readiness["cap_seconds"] = float(self.settings.runtime_start_timeout_seconds)
            return completed, readiness
        if not ready and self._chart_only_degraded(endpoints):
            # A dead/blocked Java backend (e.g. WFP/proxy software vetoing JDK-17 AF_UNIX
            # loopback pipes) must not lock out chart-only techniques: accept chart-up/java-down
            # as a degraded start instead of failing the whole runtime.
            readiness = {"ready": True, "degraded": True, "endpoints": endpoints}
        return completed, readiness

    def _record_launcher(self, pid: int, log_path: Path) -> None:
        def _mutate(state: dict[str, Any]) -> dict[str, Any]:
            state["launcher"] = {"pid": pid, "log": str(log_path), "started_at": runtime_registry.utc_now()}
            return state

        try:
            self._update_runtime_state(_mutate)
        except OSError:
            pass

    def _wait_for_service_state(
        self,
        *,
        expected_reachable: bool,
        timeout_seconds: float,
        manifest: dict[str, Any] | None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + max(timeout_seconds, 0.1)
        endpoints = self._service_status(manifest)
        while time.monotonic() < deadline:
            if all(item["reachable"] == expected_reachable for item in endpoints):
                return {"ready": True, "endpoints": endpoints}
            time.sleep(0.25)
            endpoints = self._service_status(manifest)
        return {"ready": all(item["reachable"] == expected_reachable for item in endpoints), "endpoints": endpoints}

    def _write_runtime_state(self, payload: dict[str, Any]) -> None:
        """整份覆盖写，原子（tmp + os.replace）。

        🔴 旧实现是一次 `write_text`：两个进程同时冷启动时读者会读到半个 JSON（解析失败 →
        `load_runtime_state` 返回 None → 调用方以为「没在跑」→ 再起一次），写者互相覆盖，
        最后文件里记的是输的那一方。见 runtime/registry.py。
        """
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        merged = dict(payload)
        # 保留 v2 的长寿字段（launch_nonce / clients / launcher …）：这些是别的进程写进来的，
        # 一次 start/stop 的整份覆盖不该把它们抹掉。
        existing = runtime_registry.read_state(self.settings.runtime_state_path) or {}
        for key in ("launch_nonce", "clients", "launcher", "service_pids", "ports"):
            if key not in merged and existing.get(key):
                merged[key] = existing[key]
        runtime_registry.write_state(self.settings.runtime_state_path, merged)

    def _update_runtime_state(self, mutate: Any) -> dict[str, Any]:
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        return runtime_registry.update_state(self.settings.runtime_state_path, mutate)

    def _clear_runtime_state(self) -> None:
        runtime_registry.clear_state(self.settings.runtime_state_path)

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat()

    def _default_home_value(self) -> str:
        home = os.environ.get("HOME", "").strip()
        if home:
            return home
        userprofile = os.environ.get("USERPROFILE", "").strip()
        if userprofile:
            return userprofile
        data_dir = self.settings.data_dir
        if data_dir.name == ".horosa-skill":
            return str(data_dir.parent)
        runtime_root = self.settings.runtime_root
        runtime_parts = [part.lower() for part in runtime_root.parts]
        if len(runtime_parts) >= 2 and runtime_parts[-1] == "runtime" and runtime_parts[-2] == ".horosa":
            return str(runtime_root.parent.parent)
        return str(Path.home())
