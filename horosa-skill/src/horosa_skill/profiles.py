"""命主档案（saved birth profiles）：把「我妈 1962-03-05 06:00 衡阳」存成有名字的一条，下次只说「妈妈」。

AI 客户端每开一个新对话就忘了上一次的出生信息；档案放在本机，技法载荷里带 `profile="妈妈"`（或 dispatch / hecan 的
`birth.profile` / `subject.profile`，合盘的 `inner.profile` / `outer.profile`）即由 run_tool 在**校验之前**并进载荷。

规则（每条都有测试）：
- 只存出生事实：date / time / zone / lat / lon（+ gpsLat / gpsLon）/ ad / gender / timeAlg / cnUnifiedZone，外加
  aliases（别名）、place（地点文字）、notes（备注，永不回显进技法结果）。宫制、流派、日界这类口径不是档案字段：它们每次
  调用由澄清闸问（铁律 2 不动）；save 收到这类键只报 `ignored_fields`，不存。
- place：save 只给地名、没给经纬度时，门面（service/api/tools.py `_profile_place_coordinates`）用技法同一条地名解析
  （含 v0.50.0 接受规则）把坐标与按出生日期的 zone **解析并存进档案**，地名本身照留作标签；歧义 / 找不到照常拒绝。
  给了经纬度就只存标签。本模块自己不解析地名（下层，不碰引擎）。
- 档案名：查找键折叠全角 / 大小写 / 空白，并**折叠繁简**（「媽媽」与「妈妈」是同一份档案；显示名保留第一次存的写法）。
  v0.50.0 之前存下的「妈妈」「媽媽」两条照旧各自可取（精确名优先），不自动合并；用 rename / delete 自己整理。
- save 用技法同一套归一化（input_normalization）校验：日期不存在、时刻越界、经纬度越界 → `tool.invalid_payload`；
  时区认不出 → `tool.invalid_zone`。按名字合并更新（给 null 删一个字段），返回 previous 作为撤销依据。
- 并进载荷时**显式字段逐键优先**（lat 与 gpsLat、lon 与 gpsLon 各算一组）；档案只给它存了的字段，没存的照旧缺、
  照旧被闸门问。gender 只进中式 / 神数技法（它们读性别；西占模型没有这个键）与声明了它的模型，其余字段只进声明了它的模型。
- 认不出 / 有歧义的档案名 → `profile.not_found` / `profile.ambiguous`，details 列出全部已存档案名。
- 存储：`<data_dir>/profiles/profiles.db`（SQLite WAL + busy_timeout，写用 BEGIN IMMEDIATE：多个 MCP 进程并发安全）。
  这是用户数据，不是缓存：库坏了**不**自动隔离重建（那等于删档），报 `profile.store_corrupt` 让用户处理。
  `runtime uninstall --purge-data` 缺省保留它（与自备知识库同一口径），`--purge-profiles` 才删。

本模块是下层：不 import service / surfaces（tests/test_layering.py）。
"""
from __future__ import annotations

import inspect
import json
import os
import re
import sqlite3
import threading
import unicodedata
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from horosa_skill.civil_calendar import _civil_ymd_exists, _parse_date_parts
from horosa_skill.errors import ToolValidationError, bilingual
from horosa_skill.input_normalization import normalize_request_payload

PROFILE_KEY = "profile"
DIRNAME = "profiles"
DB_NAME = "profiles.db"
SCHEMA_VERSION = 1

# 出生事实（并进技法载荷的字段）。顺序 = get 返回的顺序。
BIRTH_FIELDS: tuple[str, ...] = (
    "date", "time", "zone", "lat", "gpsLat", "lon", "gpsLon", "ad", "gender", "timeAlg", "cnUnifiedZone",
)
LABEL_FIELDS: tuple[str, ...] = ("aliases", "place", "notes")
# 显式优先按组判：给了 lat（或 gpsLat）就两个都不从档案取，免得一半坐标来自档案、一半来自本次。
_FIELD_GROUPS: dict[str, tuple[str, ...]] = {
    "lat": ("lat", "gpsLat"), "gpsLat": ("lat", "gpsLat"),
    "lon": ("lon", "gpsLon"), "gpsLon": ("lon", "gpsLon"),
}
# 读性别的技法族：中式与神数的 runner 都读 payload["gender"]（八字 / 参评数 / 河洛等模型没声明它，照样读）；西占模型没有这个键。
GENDER_DOMAINS = frozenset({"cn", "shenshu"})
# 日子馆 `rizi.persons[]` 的人（calendar_month）：引擎只读这几个键。
_RIZI_PERSON_FIELDS = frozenset({"date", "time", "zone", "gender"})
_NAME_MAX = 64
_PLACE_MAX = 200
_NOTES_MAX = 2000
_ALIASES_MAX = 12
_OFFSET_RE = re.compile(r"^([+-])(\d{2}):(\d{2})$")
_DATE_RE = re.compile(r"^-?\d{4,5}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2})$")
_COORD_RE = re.compile(r"^(\d{1,3})([nsew])(\d{2})$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_CORRUPTION_MARKERS = ("malformed", "not a database", "corrupt", "file is not a database")


# ───────────────────────────── 数据结构 ─────────────────────────────


@dataclass(frozen=True)
class Profile:
    name: str
    fields: dict[str, Any]
    aliases: tuple[str, ...] = ()
    place: str | None = None
    notes: str | None = None
    created_at: str = ""
    updated_at: str = ""
    # 库里这一行的主键（v0.50.0 前 = name_key(name)，之后 = store_key(name)）：更新 / 删除 / 改名按它定位。
    key: str = field(default="", compare=False)

    def summary(self) -> dict[str, Any]:
        return {"name": self.name, "aliases": list(self.aliases)}

    def as_dict(self) -> dict[str, Any]:
        """get / list(detail) 的形状：`payload` 原样并进技法载荷即可。"""
        out: dict[str, Any] = {"name": self.name, "aliases": list(self.aliases), "payload": dict(self.fields)}
        if self.place:
            out["place"] = self.place
        if self.notes:
            out["notes"] = self.notes
        out["created_at"] = self.created_at
        out["updated_at"] = self.updated_at
        return out


@dataclass(frozen=True)
class ProfileUse:
    """一次并进载荷的记录（技法卡 `profiles` 与 summary 读它）。不带 notes。"""

    slot: str  # "" = 载荷顶层；"inner" / "outer" / "birth" / "subject.birth" / "rizi.persons[0]" …
    name: str
    filled: tuple[str, ...]
    overridden: tuple[str, ...]
    stored: tuple[str, ...] = field(default=())

    def card(self) -> dict[str, Any]:
        return {"slot": self.slot or "subject", "name": self.name, "filled": list(self.filled),
                "overridden": list(self.overridden)}


# ───────────────────────────── 错误 ─────────────────────────────


def _invalid(errors: list[dict[str, Any]], zh: str, en: str) -> ToolValidationError:
    """出生字段写坏了 / 缺了：要问用户（must_ask_user=true），不是 AI 自己能补的字段。说清是「写法不对」还是「缺」，
    并点名真实的工具 horosa_profile（v0.50.0 前这里写的是不存在的 horosa_profile_data，且一律说「请补充」）。"""
    from horosa_skill.agent_guidance import build_clarification_recovery

    ask: list[dict[str, Any]] = []
    for error in errors:
        field_name = str((error.get("loc") or ["data", "?"])[-1])
        if error.get("type") == "missing":
            question = bilingual(f"缺 `{field_name}`：{error.get('msg')}。请向用户要，再用 horosa_profile 重存。",
                                 f"`{field_name}` is missing: {error.get('msg')}. Ask the user, then save again with horosa_profile.")
        else:
            question = bilingual(f"`{field_name}` 写法不对：{error.get('msg')}。请与用户核对后用 horosa_profile 重存。",
                                 f"`{field_name}` is malformed: {error.get('msg')}. Check it with the user, then save again with horosa_profile.")
        ask.append({"field": f"data.{field_name}", "question": question})
    recovery = build_clarification_recovery(
        tool_name="horosa_profile", ask_if_missing=ask[:8],
        do_not_assume=["Do not guess or reformat a birth date, time, zone or coordinate yourself; ask the user."],
        reason="invalid_birth_fields",
    )
    return ToolValidationError(
        bilingual(zh, en),
        code="tool.invalid_payload",
        details={"errors": errors, "agent_recovery": recovery},
    )


def _request_error(problem_zh: str, problem_en: str, **details: Any) -> ToolValidationError:
    """调用方（AI）自己能改的入参问题：action / name / data 的形状。"""
    return ToolValidationError(bilingual(problem_zh, problem_en), code="profile.invalid_payload", details=details)


def _store_error(path: Path, exc: BaseException) -> ToolValidationError:
    text = f"{exc}"
    if isinstance(exc, sqlite3.DatabaseError) and "locked" not in text.lower() and any(m in text.lower() for m in _CORRUPTION_MARKERS):
        return ToolValidationError(
            bilingual(f"命主档案库损坏（{path}）：{text}。档案是你的数据，不会自动删除重建。",
                      f"The birth-profile database is corrupt ({path}): {text}. It is your data, so it is never rebuilt automatically."),
            code="profile.store_corrupt",
            details={"path": str(path), "error": text},
        )
    return ToolValidationError(
        bilingual(f"命主档案库暂时用不了（{path}）：{type(exc).__name__}: {text}",
                  f"The birth-profile database is unavailable ({path}): {type(exc).__name__}: {text}"),
        code="profile.store_unavailable",
        details={"path": str(path), "error": f"{type(exc).__name__}: {text}"},
    )


# ───────────────────────────── 名字 ─────────────────────────────


def name_key(text: str) -> str:
    """查找键：NFKC（全角字母数字归半角）+ casefold + 空白折叠。"""
    folded = unicodedata.normalize("NFKC", f"{text}").casefold()
    return " ".join(folded.split())


def store_key(text: str) -> str:
    """档案的身份键（v0.50.0）：name_key 再折繁简（与 resolve_in 第三步、本仓其余繁简折叠同一个 fold_to_simplified）。
    「媽媽」与「妈妈」是同一个人：save 合并进已有那条，显示名不改写。"""
    from horosa_skill.textscript import fold_to_simplified

    return name_key(fold_to_simplified(name_key(text)))


def _same_person(rows: list[Profile], display: str) -> Profile | None:
    """save / rename 用：同名档案。精确名（name_key）优先——v0.50.0 前存下的「妈妈」「媽媽」两条各自照旧；只有一条
    繁简折叠后同名时才并到它；折叠后有两条以上且没有精确的，不替用户挑。"""
    exact = [p for p in rows if name_key(p.name) == name_key(display)]
    if exact:
        return exact[0]
    folded = [p for p in rows if store_key(p.name) == store_key(display)]
    if len(folded) > 1:
        names = [p.name for p in folded]
        raise ToolValidationError(
            bilingual(f"「{display}」与已存的 {'、'.join(names)} 繁简折叠后同名：请先用 rename / delete 整理，或用其中一个的原名。",
                      f"'{display}' folds to the same name as {', '.join(names)}; rename or delete one first, or use one of their exact names."),
            code="profile.ambiguous",
            details={"profile": display, "candidates": names, "known_profiles": [p.name for p in rows],
                     "agent_recovery": {"kind": "input", "next_action": "pick_one_candidate_by_name", "candidates": names}},
        )
    return folded[0] if folded else None


def _clean_name(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _request_error(f"{what}不能为空，须是文字。", f"{what} must be non-empty text.", field=what)
    text = unicodedata.normalize("NFC", " ".join(value.split()))
    if _CONTROL.search(text) or len(text) > _NAME_MAX:
        raise _request_error(f"{what}不能含换行 / 控制字符，且不超过 {_NAME_MAX} 字。",
                             f"{what} may not contain line breaks / control characters and is limited to {_NAME_MAX} characters.",
                             field=what)
    return text


def _clean_text(value: Any, what: str, limit: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _request_error(f"{what} 须是文字。", f"{what} must be text.", field=what)
    text = unicodedata.normalize("NFC", value).strip()
    if len(text) > limit:
        raise _request_error(f"{what} 不超过 {limit} 字。", f"{what} is limited to {limit} characters.", field=what)
    return text or None


def _clean_aliases(value: Any, own_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    items = [value] if isinstance(value, str) else value
    if not isinstance(items, list) or len(items) > _ALIASES_MAX:
        raise _request_error(f"aliases 须是文字列表（最多 {_ALIASES_MAX} 个）。",
                             f"aliases must be a list of text (at most {_ALIASES_MAX}).", field="aliases")
    out: list[str] = []
    seen = {name_key(own_name)}
    for item in items:
        alias = _clean_name(item, "alias")
        if name_key(alias) not in seen:
            seen.add(name_key(alias))
            out.append(alias)
    return tuple(out)


# ───────────────────────────── 出生字段校验 ─────────────────────────────


def _error(field_name: str, message: str, *, kind: str = "value_error") -> dict[str, Any]:
    return {"loc": ["data", field_name], "msg": message, "type": kind}


def _check_zone(raw: Any, normalized: Any) -> Any:
    """返回要存的时区：IANA 名原样存（起盘时按出生日期换算偏移、新疆时区归并照常生效），其余存归一后的偏移。"""
    if isinstance(normalized, str):
        match = _OFFSET_RE.match(normalized)
        if match and int(match.group(2)) * 60 + int(match.group(3)) <= 15 * 60 and int(match.group(3)) < 60:
            return raw.strip() if isinstance(raw, str) and "/" in raw else normalized
    if isinstance(raw, str) and "/" in raw:
        try:
            ZoneInfo(raw.strip())
            return raw.strip()
        except (ZoneInfoNotFoundError, ValueError):
            pass
    raise ToolValidationError(
        bilingual(f"认不出时区：{raw!r}。", f"Unrecognized time zone: {raw!r}."),
        code="tool.invalid_zone",
        details={"zone": raw, "accepted_forms": ["+08:00", "-05:00", "8", "Asia/Shanghai"]},
    )


def validate_birth_fields(data: dict[str, Any]) -> dict[str, Any]:
    """出生字段 → 要存的规范形（技法载荷原样可收）。用的是技法同一套归一化；认不出的值报错，绝不换默认值蒙混。"""
    raw = {key: data[key] for key in BIRTH_FIELDS if data.get(key) is not None}
    normalized = normalize_request_payload(dict(raw))
    errors: list[dict[str, Any]] = []
    out: dict[str, Any] = {}

    ad = normalized.get("ad")
    if ad is not None:
        try:
            ad = int(ad)
        except (TypeError, ValueError):
            ad = None
        if ad not in (1, -1):
            errors.append(_error("ad", "ad 只能是 1（公元后）或 -1（公元前）/ ad must be 1 (AD) or -1 (BC)"))
        else:
            out["ad"] = ad

    date = normalized.get("date")
    if date is not None:
        parts = _parse_date_parts(date) if isinstance(date, str) and _DATE_RE.match(date) else None
        if parts is not None:
            year, month, day = parts
            if year > 0 and ad == -1:
                year = -year
        if parts is None or not _civil_ymd_exists(year, month, day):
            errors.append(_error("date", f"不是存在的公历日期：{raw.get('date')!r}（YYYY-MM-DD）/ not a real calendar date: {raw.get('date')!r}"))
        else:
            out["date"] = date

    time = normalized.get("time")
    if time is not None:
        match = _TIME_RE.match(time) if isinstance(time, str) else None
        if not match or int(match.group(1)) > 23 or int(match.group(2)) > 59 or int(match.group(3)) > 59:
            errors.append(_error("time", f"不是合法时刻：{raw.get('time')!r}（HH:mm[:ss]，24 小时制）/ not a valid time: {raw.get('time')!r}"))
        else:
            out["time"] = time

    for axis, gps, limit in (("lat", "gpsLat", 90), ("lon", "gpsLon", 180)):
        value = normalized.get(axis)
        if value is None:
            continue
        match = _COORD_RE.match(value) if isinstance(value, str) else None
        hemispheres = "ns" if axis == "lat" else "ew"
        if not match or match.group(2) not in hemispheres or int(match.group(1)) + int(match.group(3)) / 60 > limit:
            errors.append(_error(axis, f"不是合法{('纬度' if axis == 'lat' else '经度')}：{raw.get(axis, raw.get(gps))!r} / not a valid {axis}"))
            continue
        out[axis] = value
        if isinstance(normalized.get(gps), (int, float)) and not isinstance(normalized.get(gps), bool):
            out[gps] = normalized[gps]
    if ("lat" in out) != ("lon" in out) and not any(e["loc"][1] in ("lat", "lon") for e in errors):
        errors.append(_error("lat" if "lon" in out else "lon", "经纬度要成对给出 / lat and lon go together"))

    gender = normalized.get("gender")
    if gender is not None:
        if gender in (0, 1) and not isinstance(gender, bool):
            out["gender"] = int(gender)
        else:
            errors.append(_error("gender", f"认不出性别：{raw.get('gender')!r}（男 / 女 / 1 / 0）/ unrecognized gender"))

    time_alg = normalized.get("timeAlg")
    if isinstance(time_alg, str) and time_alg.strip() in ("0", "1"):
        time_alg = int(time_alg.strip())
    if time_alg is not None:
        if time_alg in (0, 1) and not isinstance(time_alg, bool):
            out["timeAlg"] = int(time_alg)
        else:
            errors.append(_error("timeAlg", "timeAlg 只存 0（按经度折真太阳时）或 1（时刻已是真太阳时 / 直接用）/ timeAlg must be 0 or 1"))

    unified = normalized.get("cnUnifiedZone")
    if unified is not None:
        if isinstance(unified, bool):
            out["cnUnifiedZone"] = unified
        else:
            errors.append(_error("cnUnifiedZone", "cnUnifiedZone 须是 true / false"))

    if errors:
        raise _invalid(errors, "档案的出生信息有误，请与用户核对后重存。", "Some birth fields are invalid; check them with the user and save again.")
    if raw.get("zone") is not None:
        out["zone"] = _check_zone(raw["zone"], normalized.get("zone"))
    return {key: out[key] for key in BIRTH_FIELDS if key in out}


# ───────────────────────────── 存储 ─────────────────────────────


def profiles_dir(settings: Any) -> Path:
    return Path(settings.data_dir) / DIRNAME


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


_THREAD_LOCK = threading.RLock()


@contextmanager
def _exclusive(lock_path: Path) -> Iterator[None]:
    """进程内 + 跨进程的写锁（同 knowledge/user.py 的写锁形状）。

    为什么 SQLite 自己的锁不够：新库还在回滚日志模式时，两个写者各持 SHARED 再争 EXCLUSIVE（切 WAL / 提交）是死锁，
    SQLite 直接回 `database is locked`、**不走** busy_timeout——三个进程同时第一次存档就撞上（tests/test_profiles.py 的并发用例）。
    写者先排队，读者不切日志模式，就没有这种死锁。"""
    with _THREAD_LOCK, open(lock_path, "a+b") as handle:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:  # LK_LOCK 只重试 10 秒；继续等
                    continue
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class ProfileStore:
    """档案库。构造不碰磁盘；读一个不存在的库 = 没有档案（不建文件），第一次 save 才建库。"""

    def __init__(self, settings: Any) -> None:
        self.settings = settings
        self.path = profiles_dir(settings) / DB_NAME

    @contextmanager
    def _connect(self, *, write: bool) -> Iterator[sqlite3.Connection | None]:
        if not write:
            if not self.path.exists():
                yield None
                return
            with self._open(write=False) as connection:
                yield connection
            return
        with ExitStack() as stack:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                stack.enter_context(_exclusive(self.path.parent / ".lock"))
            except OSError as exc:
                raise _store_error(self.path, exc) from exc
            yield stack.enter_context(self._open(write=True))

    @contextmanager
    def _open(self, *, write: bool) -> Iterator[sqlite3.Connection]:
        try:
            connection = sqlite3.connect(self.path, timeout=30.0)
        except (OSError, sqlite3.Error) as exc:
            raise _store_error(self.path, exc) from exc
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA busy_timeout=30000")
            if write:
                # 只有写者（已排队）切 WAL：WAL 让读者与写者并行；读者切日志模式会与写者互相死锁。
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA synchronous=NORMAL")
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS profiles (key TEXT PRIMARY KEY, name TEXT NOT NULL, fields_json TEXT NOT NULL,"
                    " aliases_json TEXT NOT NULL DEFAULT '[]', place TEXT, notes TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
                )
                if connection.execute("PRAGMA user_version").fetchone()[0] < SCHEMA_VERSION:
                    connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            yield connection
            if write:
                connection.commit()
        except sqlite3.Error as exc:
            connection.rollback()
            raise _store_error(self.path, exc) from exc
        finally:
            connection.close()

    @staticmethod
    def _rows(connection: sqlite3.Connection | None) -> list[Profile]:
        if connection is None:
            return []
        try:
            rows = connection.execute("SELECT * FROM profiles ORDER BY created_at, key").fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in f"{exc}":
                return []
            raise
        return [
            Profile(
                name=row["name"], fields=json.loads(row["fields_json"] or "{}"),
                aliases=tuple(json.loads(row["aliases_json"] or "[]")), place=row["place"], notes=row["notes"],
                created_at=row["created_at"], updated_at=row["updated_at"], key=row["key"],
            )
            for row in rows
        ]

    def all(self) -> list[Profile]:
        with self._connect(write=False) as connection:
            return self._rows(connection)

    def names(self) -> list[str]:
        return [profile.name for profile in self.all()]

    def private_terms(self) -> list[str]:
        """决策层脱敏用：档案名、别名、地点标签（出生数据本身另有日期 / 时刻 / 坐标规则）。"""
        terms: set[str] = set()
        for profile in self.all():
            terms.update(term for term in (profile.name, *profile.aliases, profile.place or "") if term.strip())
        return sorted(terms, key=lambda term: (-len(term), term))

    def resolve(self, ref: Any) -> Profile:
        return resolve_in(self.all(), ref)

    def save(self, name: Any, data: Any) -> dict[str, Any]:
        display = _clean_name(name, "name")
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise _request_error("data 须是对象（出生字段 + aliases / place / notes）。",
                                 "data must be an object (birth fields + aliases / place / notes).", field="data")
        unknown = sorted(key for key in data if key not in BIRTH_FIELDS and key not in LABEL_FIELDS)
        with self._connect(write=True) as connection:
            assert connection is not None
            rows = self._rows(connection)
            previous = _same_person(rows, display)
            key = previous.key if previous is not None else store_key(display)
            fields = dict(previous.fields) if previous else {}
            for field_name in BIRTH_FIELDS:
                if field_name in data:
                    fields.pop(field_name, None)  # 显式 null = 删这个字段；有值的下面整组重验
                    for partner in _FIELD_GROUPS.get(field_name, ()):
                        if partner not in data:
                            fields.pop(partner, None)  # 改了 lat 就别留旧的 gpsLat
            fields.update({k: v for k, v in data.items() if k in BIRTH_FIELDS and v is not None})
            fields = validate_birth_fields(fields)
            if "date" not in fields:
                raise _invalid([_error("date", "档案至少要有出生日期 / a profile needs at least a birth date", kind="missing")],
                               "档案至少要有出生日期。", "A profile needs at least a birth date.")
            aliases = _clean_aliases(data["aliases"], display) if "aliases" in data else (previous.aliases if previous else ())
            place = _clean_text(data["place"], "place", _PLACE_MAX) if "place" in data else (previous.place if previous else None)
            notes = _clean_text(data["notes"], "notes", _NOTES_MAX) if "notes" in data else (previous.notes if previous else None)
            now = _now()
            stored_name = previous.name if previous else display
            connection.execute(
                "INSERT INTO profiles (key, name, fields_json, aliases_json, place, notes, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET fields_json=excluded.fields_json,"
                " aliases_json=excluded.aliases_json, place=excluded.place, notes=excluded.notes, updated_at=excluded.updated_at",
                (key, stored_name, json.dumps(fields, ensure_ascii=False), json.dumps(list(aliases), ensure_ascii=False),
                 place, notes, previous.created_at if previous else now, now),
            )
        saved = Profile(stored_name, fields, aliases, place, notes, previous.created_at if previous else now, now, key=key)
        result: dict[str, Any] = {"ok": True, "action": "save", "created": previous is None, "profile": saved.as_dict()}
        if previous is not None:
            result["previous"] = previous.as_dict()
        warnings = _alias_warnings(saved, [p for p in rows if p.key != key])
        if previous is not None and previous.name != display:
            warnings.append(bilingual(
                f"「{display}」与已存的「{previous.name}」是同一份档案（大小写 / 全半角 / 繁简不同），已更新「{previous.name}」，显示名不变。",
                f"'{display}' is the saved profile '{previous.name}' (case / width / script differ); it was updated and keeps its name.",
            ))
        if unknown:
            result["ignored_fields"] = unknown
            warnings.append(bilingual(
                f"这些键不是档案字段，没有保存：{', '.join(unknown)}（宫制、流派、日界等口径每次调用由澄清闸问用户）。",
                f"Not profile fields, not saved: {', '.join(unknown)} (settings such as house system or school are asked per call by the clarification gate).",
            ))
        if warnings:
            result["warnings"] = warnings
        return result

    def delete(self, ref: Any) -> dict[str, Any]:
        with self._connect(write=True) as connection:
            assert connection is not None
            profile = resolve_in(self._rows(connection), ref)
            connection.execute("DELETE FROM profiles WHERE key = ?", (profile.key,))
        # 整条交回：要撤销就把它原样 save 回去。
        return {"ok": True, "action": "delete", "deleted": profile.as_dict()}

    def rename(self, ref: Any, new_name: Any) -> dict[str, Any]:
        """改档案名（出生信息、别名、备注不动）。新名与别的档案（折叠后）同名就拒绝——不合并两个人。只改写法
        （妈妈 → 媽媽、mom → Mom）也行。撤销：用新名再 rename 回旧名。"""
        display = _clean_name(new_name, "new_name")
        with self._connect(write=True) as connection:
            assert connection is not None
            rows = self._rows(connection)
            profile = resolve_in(rows, ref)
            clash = [p.name for p in rows if p.key != profile.key and store_key(p.name) == store_key(display)]
            if clash:
                raise _request_error(
                    f"已有档案叫「{clash[0]}」（与「{display}」繁简 / 大小写折叠后同名）：换一个名字，或先删掉那一条。",
                    f"A profile named '{clash[0]}' already exists (same name once script/case are folded): pick another name or delete it first.",
                    field="new_name", known_profiles=[p.name for p in rows],
                )
            new_key = store_key(display)
            now = _now()
            connection.execute("UPDATE profiles SET key = ?, name = ?, updated_at = ? WHERE key = ?",
                               (new_key, display, now, profile.key))
        renamed = Profile(display, profile.fields, profile.aliases, profile.place, profile.notes, profile.created_at, now, key=new_key)
        result: dict[str, Any] = {"ok": True, "action": "rename", "previous_name": profile.name, "profile": renamed.as_dict()}
        warnings = _alias_warnings(renamed, [p for p in rows if p.key != profile.key])
        if warnings:
            result["warnings"] = warnings
        return result


EXPORT_FORMAT = "horosa-birth-profiles"
EXPORT_VERSION = 1


def export_profiles(store: ProfileStore) -> dict[str, Any]:
    """全部档案 → 一个 JSON 文档（CLI `profile export`）。含 notes 与出生信息：是用户的私人数据，文件由用户自己保管。"""
    items = store.all()
    return {"format": EXPORT_FORMAT, "version": EXPORT_VERSION, "exported_at": _now(), "count": len(items),
            "profiles": [item.as_dict() for item in items]}


def import_profiles(store: ProfileStore, document: Any, *, overwrite: bool = False) -> dict[str, Any]:
    """CLI `profile import`：先整份校验（任何一条坏了就一条都不写，报出全部问题），再逐条 save。已有同名档案默认跳过，
    overwrite=True 才按名合并覆盖（与 save 同一套合并：文件里没有的字段保留）。坐标 / 时区照文件里存的，不重新解析地名。"""
    if not isinstance(document, dict) or document.get("format") != EXPORT_FORMAT or not isinstance(document.get("profiles"), list):
        raise _request_error(f"不是档案导出文件：要 {{\"format\": \"{EXPORT_FORMAT}\", \"profiles\": [...]}}（profile export 的输出）。",
                             f"Not a profile export: expected {{\"format\": \"{EXPORT_FORMAT}\", \"profiles\": [...]}} (the output of profile export).",
                             field="document")
    if document.get("version") != EXPORT_VERSION:
        raise _request_error(f"导出文件版本 {document.get('version')!r} 不认识（本版只读 {EXPORT_VERSION}）。",
                             f"Unknown export version {document.get('version')!r} (this build reads {EXPORT_VERSION}).", field="version")
    problems: list[dict[str, Any]] = []
    planned: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for index, item in enumerate(document["profiles"]):
        try:
            if not isinstance(item, dict):
                raise _request_error("每条档案须是对象。", "Each profile must be an object.", field=f"profiles[{index}]")
            name = _clean_name(item.get("name"), "name")
            if store_key(name) in seen:
                raise _request_error(f"文件里「{name}」出现了两次。", f"'{name}' appears twice in the file.", field=f"profiles[{index}].name")
            seen.add(store_key(name))
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
            data = {**{k: v for k, v in payload.items() if k in BIRTH_FIELDS},
                    **{k: item[k] for k in LABEL_FIELDS if item.get(k) is not None}}
            fields = validate_birth_fields(data)
            if "date" not in fields:
                raise _invalid([_error("date", "档案至少要有出生日期 / a profile needs at least a birth date", kind="missing")],
                               "档案至少要有出生日期。", "A profile needs at least a birth date.")
            _clean_aliases(data.get("aliases"), name)
            _clean_text(data.get("place"), "place", _PLACE_MAX)
            _clean_text(data.get("notes"), "notes", _NOTES_MAX)
            planned.append((name, data))
        except ToolValidationError as exc:
            problems.append({"index": index, "name": item.get("name") if isinstance(item, dict) else None,
                             "code": exc.code, "message": str(exc), "errors": exc.details.get("errors")})
    if problems:
        raise ToolValidationError(
            bilingual(f"导入文件里有 {len(problems)} 条档案有问题，一条都没写入（details.problems）。",
                      f"{len(problems)} profile(s) in the file are invalid; nothing was imported (details.problems)."),
            code="profile.invalid_payload",
            details={"problems": problems},
        )
    existing = {store_key(p.name): p.name for p in store.all()}
    imported: list[str] = []
    skipped: list[dict[str, str]] = []
    for name, data in planned:
        if store_key(name) in existing and not overwrite:
            skipped.append({"name": name, "existing": existing[store_key(name)], "reason": "exists"})
            continue
        imported.append(store.save(name, data)["profile"]["name"])
    return {"ok": True, "action": "import", "imported": imported, "skipped": skipped,
            **({"hint": bilingual("已有同名档案的条目被跳过；要覆盖请加 --overwrite。",
                                  "Profiles that already exist were skipped; pass --overwrite to update them.")} if skipped else {})}


USE_HINT = (
    "技法载荷带 profile=\"档案名\" 即填入出生信息（显式字段优先，缺的照旧由澄清闸问）；合盘 inner.profile / outer.profile；"
    "dispatch / hecan 用 birth.profile 或 subject.profile。"
)


def run_action(store: ProfileStore, payload: Any) -> dict[str, Any]:
    """horosa_profile / CLI `profile`：save / get / list / delete / rename（rename 的新名放 data.new_name）。
    export / import 只在 CLI（profile export / profile import），MCP 面暂不开（留给维护者定）。"""
    from pydantic import ValidationError

    from horosa_skill.errors import validation_errors
    from horosa_skill.schemas.tools.facades import ProfileInput

    try:
        request = ProfileInput.model_validate(payload if isinstance(payload, dict) else {})
    except ValidationError as exc:
        raise _request_error("命主档案的参数不对：action 取 save / get / list / delete / rename，除 list 外都要给 name。",
                             "Invalid horosa_profile payload: action is save / get / list / delete / rename; all but list need a name.",
                             errors=validation_errors(exc)) from exc
    if request.action == "list":
        items = store.all()
        return {"ok": True, "action": "list", "count": len(items),
                "profiles": [item.as_dict() if request.detail else item.summary() for item in items], "use": USE_HINT}
    if request.action == "save":
        return {**store.save(request.name, request.data), "use": USE_HINT}
    if _blank(request.name):
        raise _request_error(f"{request.action} 要给 name。", f"{request.action} needs a name.", field="name",
                             known_profiles=store.names())
    if request.action == "delete":
        return store.delete(request.name)
    if request.action == "rename":
        new_name = (request.data or {}).get("new_name")
        if _blank(new_name):
            raise _request_error("rename 要在 data.new_name 给新名字。", "rename needs the new name in data.new_name.",
                                 field="data.new_name", known_profiles=store.names())
        return {**store.rename(request.name, new_name), "use": USE_HINT}
    return {"ok": True, "action": "get", "profile": store.resolve(request.name).as_dict(), "use": USE_HINT}


def _alias_warnings(saved: Profile, others: list[Profile]) -> list[str]:
    warnings: list[str] = []
    for alias in saved.aliases:
        key = name_key(alias)
        clash = [p.name for p in others if name_key(p.name) == key]
        shared = [p.name for p in others if key in {name_key(a) for a in p.aliases}]
        if clash:
            warnings.append(bilingual(f"别名「{alias}」与档案「{clash[0]}」同名：叫这个名字时取的是「{clash[0]}」。",
                                      f"Alias '{alias}' is also the name of profile '{clash[0]}', which wins on lookup."))
        elif shared:
            warnings.append(bilingual(f"别名「{alias}」也是「{'、'.join(shared)}」的别名：只叫别名会有歧义。",
                                      f"Alias '{alias}' is shared with {', '.join(shared)}; looking it up alone is ambiguous."))
    key = name_key(saved.name)
    shadowed = [p.name for p in others if key in {name_key(a) for a in p.aliases}]
    if shadowed:
        warnings.append(bilingual(f"「{saved.name}」也是「{'、'.join(shadowed)}」的别名：现在这个名字取的是新存的档案。",
                                  f"'{saved.name}' is also an alias of {', '.join(shadowed)}; the name now resolves to this profile."))
    return warnings


def resolve_in(profiles: list[Profile], ref: Any) -> Profile:
    """档案名 → 一条档案：精确名 → 唯一别名 → 繁简折叠后唯一。认不出 / 有歧义一律报错并列出已存档案名，绝不「挑第一个」。"""
    if not isinstance(ref, str) or not ref.strip():
        raise _request_error("profile 须是档案名或别名（文字）。", "profile must be a profile name or alias (text).",
                             field=PROFILE_KEY, known_profiles=[p.name for p in profiles])
    key = name_key(ref)
    for profile in profiles:
        if name_key(profile.name) == key:
            return profile
    by_alias = [p for p in profiles if key in {name_key(alias) for alias in p.aliases}]
    if not by_alias:
        from horosa_skill.textscript import fold_to_simplified

        folded = name_key(fold_to_simplified(ref))
        by_alias = [
            p for p in profiles
            if folded in {name_key(fold_to_simplified(term)) for term in (p.name, *p.aliases)}
        ]
    if len(by_alias) == 1:
        return by_alias[0]
    known = [p.name for p in profiles]
    if by_alias:
        candidates = [p.name for p in by_alias]
        raise ToolValidationError(
            bilingual(f"「{ref}」对应多条命主档案：{'、'.join(candidates)}。", f"'{ref}' matches several profiles: {', '.join(candidates)}."),
            code="profile.ambiguous",
            details={"profile": ref, "candidates": candidates, "known_profiles": known,
                     "agent_recovery": {"kind": "input", "next_action": "pick_one_candidate_by_name", "known_profiles": known,
                                        "candidates": candidates}},
        )
    raise ToolValidationError(
        bilingual(f"没有叫「{ref}」的命主档案。", f"No saved birth profile named '{ref}'."),
        code="profile.not_found",
        details={"profile": ref, "known_profiles": known,
                 "agent_recovery": {"kind": "input", "next_action": "pick_profile_from_list_or_ask_user", "known_profiles": known}},
    )


# ───────────────────────────── 并进载荷 ─────────────────────────────


def owns_profile_key(model: Any) -> bool:
    """技法模型自己声明了 `profile`（天文地占的传本流派）：那里的 `profile` 是技法旋钮，不是档案名。"""
    for cls in getattr(model, "__mro__", ()):
        if isinstance(cls, type) and PROFILE_KEY in inspect.get_annotations(cls):
            return cls.__name__ != "FlexibleModel"
    return False


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _fill(target: dict[str, Any], profile: Profile, allowed: Any, slot: str) -> ProfileUse:
    filled: list[str] = []
    overridden: list[str] = []
    # 「显式」只看调用方给的：刚从档案填进去的 lat 不能让 gpsLat 当成被显式值压过（那样十进制坐标会被重算、与显式起盘差末位）。
    explicit = {key for key, value in target.items() if value is not None}
    for field_name, value in profile.fields.items():
        if not allowed(field_name):
            continue
        group = _FIELD_GROUPS.get(field_name, (field_name,))
        if any(member in explicit for member in group):
            if target.get(field_name) is not None and target.get(field_name) != value:
                overridden.append(field_name)
            continue
        target[field_name] = value
        filled.append(field_name)
    return ProfileUse(slot, profile.name, tuple(filled), tuple(overridden), tuple(profile.fields))


def _field_filter(model_fields: Any, domain: str | None) -> Any:
    names = set(model_fields or ())

    def allowed(field_name: str) -> bool:
        if field_name in ("gpsLat", "gpsLon"):  # 十进制坐标跟着 lat / lon 走（归一化本来就成对处理）
            return ("lat" if field_name == "gpsLat" else "lon") in names
        return field_name in names or (field_name == "gender" and domain in GENDER_DOMAINS)

    return allowed


def _person_slots(payload: dict[str, Any], model: Any) -> Iterator[tuple[str, dict[str, Any], Any]]:
    """技法载荷里会装一个人的位置：(slot 名, 那个人的 dict, 字段过滤器)。合盘两人在 inner / outer，日子馆在 rizi.persons[]。"""
    fields = getattr(model, "model_fields", {}) or {}
    for slot in ("inner", "outer"):
        party = payload.get(slot)
        if slot in fields and isinstance(party, dict):
            annotation = fields[slot].annotation
            party_fields = getattr(annotation, "model_fields", None) or {"date", "time", "zone", "lat", "lon", "ad"}
            yield slot, party, _field_filter(party_fields, None)
    rizi = payload.get("rizi")
    if "rizi" in fields and isinstance(rizi, dict) and isinstance(rizi.get("persons"), list):
        for index, person in enumerate(rizi["persons"]):
            if isinstance(person, dict):
                yield f"rizi.persons[{index}]", person, _field_filter(_RIZI_PERSON_FIELDS, None)


def carries_profile(payload: Any, model: Any) -> bool:
    """载荷里有没有要并进来的档案名（纯判断，不碰档案库）。只对装人的模型（有 date，或有 inner / outer / rizi，或 dispatch 形）
    成立：门面（记忆 / 报告 / 知识）载荷里多一个 `profile` 不算。"""
    if not isinstance(payload, dict):
        return False
    fields = getattr(model, "model_fields", {}) or {}
    dispatch_shaped = "birth" in fields or "subject" in fields
    holds_people = "date" in fields or any(slot in fields for slot in ("inner", "outer", "rizi"))
    if not _blank(payload.get(PROFILE_KEY)) and not owns_profile_key(model) and (holds_people or dispatch_shaped):
        return True
    if dispatch_shaped:  # dispatch / hecan
        return any(not _blank(slot.get(PROFILE_KEY)) for _name, slot in _dispatch_slots(payload))
    return any(not _blank(person.get(PROFILE_KEY)) for _slot, person, _allowed in _person_slots(payload, model))


def expand_tool_payload(store: ProfileStore, payload: dict[str, Any], *, model: Any, domain: str | None) -> tuple[dict[str, Any], list[ProfileUse]]:
    """技法载荷里的档案名 → 字段（显式字段逐键优先）。没有档案名时原样返回、不碰档案库。"""
    if not carries_profile(payload, model) and not (isinstance(payload, dict) and PROFILE_KEY in payload and not owns_profile_key(model)):
        return payload, []
    out = dict(payload)
    uses: list[ProfileUse] = []
    profiles: list[Profile] | None = None

    def lookup(ref: Any) -> Profile:
        nonlocal profiles
        if profiles is None:
            profiles = store.all()
        return resolve_in(profiles, ref)

    fields = getattr(model, "model_fields", {}) or {}
    if PROFILE_KEY in out and not owns_profile_key(model):
        ref = out.pop(PROFILE_KEY)
        if not _blank(ref):
            if "date" not in fields:
                raise ToolValidationError(
                    bilingual(
                        "这个技法的载荷顶层不收出生信息，`profile` 放不进来；合盘用 inner.profile / outer.profile。",
                        "This tool takes no birth data at the top level, so `profile` does not apply; for relationship charts use inner.profile / outer.profile.",
                    ),
                    code="profile.not_applicable",
                    details={"profile": ref, "person_slots": [slot for slot in ("inner", "outer") if slot in fields]},
                )
            uses.append(_fill(out, lookup(ref), _field_filter(fields, domain), ""))
    for slot, person, allowed in list(_person_slots(out, model)):
        if PROFILE_KEY not in person:
            continue
        expanded = dict(person)
        ref = expanded.pop(PROFILE_KEY)
        if not _blank(ref):
            uses.append(_fill(expanded, lookup(ref), allowed, slot))
        _replace_slot(out, slot, expanded)
    return out, uses


def _replace_slot(payload: dict[str, Any], slot: str, person: dict[str, Any]) -> None:
    if slot.startswith("rizi.persons["):
        index = int(slot[len("rizi.persons["):-1])
        rizi = dict(payload["rizi"])
        persons = list(rizi["persons"])
        persons[index] = person
        rizi["persons"] = persons
        payload["rizi"] = rizi
        return
    head, _, tail = slot.partition(".")
    if not tail:
        payload[head] = person
        return
    container = dict(payload.get(head) or {})
    _replace_slot(container, tail, person)
    payload[head] = container


# dispatch / hecan：载荷装人的位置（不知道最后选中哪个技法，所以并进**全部**已存出生字段，只为过 DispatchInput 校验；
# 交给各技法之前 restore_refs 摘回去，由 run_tool 按那个技法重新并、记出处）。
_DISPATCH_PARTY_FIELDS = frozenset({"date", "time", "zone", "lat", "lon", "ad"})


def _dispatch_slots(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    slots: list[tuple[str, dict[str, Any]]] = []
    if isinstance(payload.get("birth"), dict):
        slots.append(("birth", payload["birth"]))
    subject = payload.get("subject")
    if isinstance(subject, dict):
        if not _blank(subject.get(PROFILE_KEY)):
            slots.append(("subject", subject))
        for name in ("birth", "inner", "outer"):
            if isinstance(subject.get(name), dict):
                slots.append((f"subject.{name}", subject[name]))
    return slots


def expand_dispatch_payload(store: ProfileStore, payload: dict[str, Any]) -> tuple[dict[str, Any], list[ProfileUse]]:
    """dispatch / hecan 载荷里的档案名 → 字段（只为过校验）。顶层 `profile` 与 `subject.profile` 落到出生信息的位置。"""
    if not carries_profile(payload, _DispatchShape):
        return payload, []
    from horosa_skill.schemas.tools.facades import _DISPATCH_OWN_FIELDS as own_fields

    out = dict(payload)
    profiles = store.all()
    uses: list[ProfileUse] = []
    if PROFILE_KEY in out:
        ref = out.pop(PROFILE_KEY)
        if not _blank(ref):
            if out.get("birth") is None and out.get("subject") is None:
                # 平铺写法（技法工具的习惯）：其余非 dispatch 自有键也收进 birth，显式字段照样逐键优先。
                lifted = {k: v for k, v in out.items() if k not in own_fields}
                out = {k: v for k, v in out.items() if k in own_fields}
                out["birth"] = {**lifted, PROFILE_KEY: ref}
            else:
                birth = dict(out.get("birth") or {}) if isinstance(out.get("birth"), dict) or out.get("birth") is None else None
                if birth is None or not _blank(birth.get(PROFILE_KEY)):
                    raise _request_error("顶层 profile 与 birth.profile 只能给一个。", "Give either a top-level profile or birth.profile, not both.",
                                         field=PROFILE_KEY)
                birth[PROFILE_KEY] = ref
                out["birth"] = birth
    subject = out.get("subject")
    if isinstance(subject, dict) and not _blank(subject.get(PROFILE_KEY)):
        subject = dict(subject)
        ref = subject.pop(PROFILE_KEY)
        birth = dict(subject.get("birth") or {}) if isinstance(subject.get("birth"), dict) or subject.get("birth") is None else {}
        if not _blank(birth.get(PROFILE_KEY)):
            raise _request_error("subject.profile 与 subject.birth.profile 只能给一个。",
                                 "Give either subject.profile or subject.birth.profile, not both.", field="subject.profile")
        birth[PROFILE_KEY] = ref
        subject["birth"] = birth
        out["subject"] = subject
    for slot, person in _dispatch_slots(out):
        if slot == "subject" or _blank(person.get(PROFILE_KEY)):
            continue
        expanded = dict(person)
        allowed = _field_filter(_DISPATCH_PARTY_FIELDS, None) if slot in ("subject.inner", "subject.outer") else (lambda _f: True)
        uses.append(_fill(expanded, resolve_in(profiles, expanded[PROFILE_KEY]), allowed, slot))
        _replace_slot(out, slot, expanded)
    return out, uses


class _DispatchShape:
    model_fields = {"birth": None, "subject": None}


def restore_refs(person: dict[str, Any], use: ProfileUse | None) -> dict[str, Any]:
    """把并进来的字段摘回去、只留档案名：下一层（run_tool）按选中的技法重新并，技法卡记得是哪个档案。"""
    if use is None:
        return person
    out = {k: v for k, v in person.items() if k not in use.filled}
    out[PROFILE_KEY] = use.name
    return out


def restore_dispatch_refs(payload: dict[str, Any], uses: list[ProfileUse]) -> dict[str, Any]:
    """hecan → dispatch：校验用的展开整份摘回去（dispatch 自己再展开、再交给各技法）。"""
    out = dict(payload)
    for use in uses:
        head, _, tail = use.slot.partition(".")
        container = out.get(head)
        person = container.get(tail) if tail and isinstance(container, dict) else container
        if isinstance(person, dict):
            _replace_slot(out, use.slot, restore_refs(person, use))
    return out


def use_for(uses: list[ProfileUse], slot: str) -> ProfileUse | None:
    return next((use for use in uses if use.slot == slot), None)


def gate_view(settings: Any, tool_name: str, payload: Any) -> Any:
    """澄清闸看的载荷：档案字段并进来，闸门就不再追问档案里已有的出生信息（问不问、拦不拦仍由闸门定）。

    认不出的档案名在这里就报错（早于闸门追问）；没有档案名 = 原样返回、不碰档案库。dispatch / hecan 的闸门问题是固定的，
    只做名字校验、载荷原样返回。
    """
    if settings is None or not isinstance(payload, dict):
        return payload
    if tool_name in {"dispatch", "hecan", "horosa_dispatch", "horosa_hecan"}:
        expand_dispatch_payload(ProfileStore(settings), payload)
        return payload
    from horosa_skill.engine.registry import TOOL_DEFINITIONS, resolve_tool_name

    definition = TOOL_DEFINITIONS.get(resolve_tool_name(tool_name) or "")
    if definition is None or not carries_profile(payload, definition.input_model):
        return payload
    return expand_tool_payload(ProfileStore(settings), payload, model=definition.input_model, domain=definition.domain)[0]


def profile_summary_line(uses: list[ProfileUse]) -> str | None:
    if not uses:
        return None
    parts = []
    for use in uses:
        where = f"（{use.slot}）" if use.slot else ""
        filled = "/".join(f for f in use.filled if f not in ("gpsLat", "gpsLon")) or "无"
        extra = f"；本次显式给出的 {'/'.join(use.overridden)} 优先" if use.overridden else ""
        parts.append(f"「{use.name}」{where}：{filled}{extra}")
    return "出生信息取自命主档案" + "；".join(parts) + "。"
