from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import platform
import re
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
from horosa_skill.engine.client import HorosaApiClient
from horosa_skill.errors import RuntimeInstallError, RuntimeValidationError
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
        if not self.settings.runtime_state_path.is_file():
            return None
        try:
            payload = json.loads(self.settings.runtime_state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            if strict:
                raise RuntimeValidationError(
                    "Runtime state file is invalid.",
                    code="runtime.state_invalid",
                    details={"path": str(self.settings.runtime_state_path), "error": str(exc)},
                ) from exc
            return None
        if not isinstance(payload, dict):
            if strict:
                raise RuntimeValidationError(
                    "Runtime state file must contain an object.",
                    code="runtime.state_invalid",
                    details={"path": str(self.settings.runtime_state_path)},
                )
            return None
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
                        details={"platform": platform_name, "manifest_url": manifest_location},
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

    def start_local_services(self) -> dict[str, Any]:
        with self._service_lock:
            with self.tracer.span(workflow_name="runtime.start", metadata={"entrypoint": "runtime.start"}) as trace:
                self._require_runtime()
                manifest = self.load_installed_manifest(strict=True)
                patched_files: list[str] = []
                initial_status = self._service_status(manifest)
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
                if self._any_services_reachable(initial_status):
                    recovery_details = self.stop_local_services()
                    recovered_partial_state = True

                patched_files = self._apply_runtime_overrides(manifest)
                script = self.current_dir / self._relative_manifest_path(manifest, "services", "start_script")
                if not script.exists():
                    raise RuntimeValidationError(
                        f"Runtime start script missing: {script}",
                        code="runtime.start_script_missing",
                        details={"path": str(script)},
                    )

                env = os.environ.copy()
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
                )
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

    def stop_local_services(self) -> dict[str, Any]:
        with self.tracer.span(workflow_name="runtime.stop", metadata={"entrypoint": "runtime.stop"}) as trace:
            self._require_runtime()
            manifest = self.load_installed_manifest(strict=True)
            script = self.current_dir / self._relative_manifest_path(manifest, "services", "stop_script")
            initial_status = self._service_status(manifest)
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

    def _extract_archive(self, archive_path: Path, extract_dir: Path) -> None:
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

    def _apply_runtime_overrides(self, manifest: dict[str, Any] | None) -> list[str]:
        patched: list[str] = []
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
        try:
            with httpx.Client(timeout=1.5, follow_redirects=True) as client:
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

    def _run_start_command(
        self,
        *,
        command: list[str],
        script: Path,
        env: dict[str, str],
        manifest: dict[str, Any] | None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
        if os.name == "nt":
            # Detached Windows runtime children can keep inherited pipe handles
            # alive, so file-backed capture avoids hanging on communicate().
            temp_dir = tempfile.mkdtemp(prefix="horosa-runtime-start-")
            stdout_path = os.path.join(temp_dir, "stdout.log")
            stderr_path = os.path.join(temp_dir, "stderr.log")
            try:
                with open(stdout_path, "wb") as stdout_handle, open(stderr_path, "wb") as stderr_handle:
                    completed_result = subprocess.run(
                        command,
                        cwd=str(script.parent),
                        env=env,
                        stdout=stdout_handle,
                        stderr=stderr_handle,
                        check=False,
                    )
                with open(stdout_path, "r", encoding="utf-8", errors="replace") as stdout_reader:
                    captured_stdout = stdout_reader.read()
                with open(stderr_path, "r", encoding="utf-8", errors="replace") as stderr_reader:
                    captured_stderr = stderr_reader.read()
                completed = subprocess.CompletedProcess(
                    args=completed_result.args,
                    returncode=completed_result.returncode,
                    stdout=captured_stdout,
                    stderr=captured_stderr,
                )
            finally:
                # Close the readers (above) before rmtree — on Windows an open handle
                # blocks deletion and would leak the temp dir.
                shutil.rmtree(temp_dir, ignore_errors=True)
        else:
            completed = subprocess.run(
                command,
                cwd=str(script.parent),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        # Issue #14: when the launcher already reports the java process dead (its marker line),
        # don't burn the full readiness window waiting for an endpoint that can never come up.
        java_dead_marker = "java backend process exited" in f"{completed.stdout}\n{completed.stderr}"
        wait_timeout = (
            min(self.settings.runtime_start_timeout_seconds, 20.0)
            if java_dead_marker
            else self.settings.runtime_start_timeout_seconds
        )
        readiness = self._wait_for_service_state(
            expected_reachable=True,
            timeout_seconds=wait_timeout,
            manifest=manifest,
        )
        readiness.setdefault("degraded", False)
        if not readiness["ready"] and self._chart_only_degraded(readiness["endpoints"]):
            # A dead/blocked Java backend (e.g. WFP/proxy software vetoing JDK-17 AF_UNIX
            # loopback pipes) must not lock out chart-only techniques: accept chart-up/java-down
            # as a degraded start instead of failing the whole runtime.
            readiness = {"ready": True, "degraded": True, "endpoints": readiness["endpoints"]}
        return completed, readiness

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
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.settings.runtime_state_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _clear_runtime_state(self) -> None:
        if self.settings.runtime_state_path.exists():
            self.settings.runtime_state_path.unlink()

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
