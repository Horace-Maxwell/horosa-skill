"""`uninstall --purge-data` 删什么：只删本工具自己写进数据目录的东西。

🔴 为什么（v0.50.0-dev，E-01）：旧实现在「要保留的（知识库 / 档案）都不在」时把 `HOROSA_SKILL_DATA_DIR` **整个 rmtree**。
数据目录是用户指的（MCPB / 插件的设置项里就能填）：指到一个已经放着别的东西的文件夹、指到家目录都发生得了，
而 dry-run 只印一行目录名，看不出里面还有什么。

三条纪律：
  · **白名单**：数据目录的直接子项里，只有名字登记在这里的才算本工具的；其余原地不动，在结果里列成 `left_in_place`。
    新增一种落在数据目录里的文件 → 在 `OWNED_NAMES` 登记（`tests/test_uninstall_purge.py` 用真实的各个存储跑一遍，
    漏登记的会让「全是我们的」那条测试红）。
  · **目录只 rmdir**：数据目录本身从不 rmtree，空了才删。
  · **名字不是所有权的证明**：数据目录是家目录、家目录的上级、文件系统根，或者把 runtime 根包在里面时，
    `runs/`、`profiles/` 这些名字很可能是别人的 —— 整条命令拒绝（`runtime.purge_refused`），一个字节都不删。

dry-run 的清单与真删用的是同一个 `plan_data_purge` 的结果（调用方只算一次）。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 数据目录直接子项里本工具写的名字（记忆库及其 SQLite 伴生文件另按 db 文件名判，见 `_is_db_family`）。
OWNED_NAMES: frozenset[str] = frozenset({
    "runs",                               # Settings.output_dir 的缺省位置
    "traces",                             # Settings.trace_dir 的缺省位置
    "jev_events.jsonl",                   # decisions/ledger.py
    "openclaw_setup_smoke_check.json",    # surfaces/openclaw_flow.py
    "openclaw_smoke_check.json",
    "openclaw_full_check.json",
})
DEFAULT_DB_NAME = "memory.db"
_SQLITE_SIDECARS = ("-wal", "-shm", "-journal")


@dataclass
class DataPurgePlan:
    remove: list[Path] = field(default_factory=list)          # 逐个删（目录递归、链接只摘链接）
    kept: list[Path] = field(default_factory=list)            # 用户没让删的：知识库 / 回收站 / 命主档案
    left_in_place: list[Path] = field(default_factory=list)   # 不是本工具写的
    outside_data_dir: list[Path] = field(default_factory=list)  # 本工具的数据，但配在数据目录之外：不删，只告知
    rmdir_data_dir: bool = False                              # 上面删完后数据目录应当空了


def refusal_reason(path: Path, *, runtime_root: Path, home: Path | None = None) -> str | None:
    """这个目录不可能整个归本工具时给出原因码；否则 None。只看路径，不碰磁盘内容。"""
    target = _resolved(path)
    if target.parent == target:
        return "filesystem_root"
    home_dir = _resolved(home if home is not None else Path.home())
    if target == home_dir:
        return "home"
    if home_dir.is_relative_to(target):
        return "above_home"
    if _resolved(runtime_root).is_relative_to(target):
        return "contains_runtime_root"
    return None


def owned_children_present(data_dir: Path, *, db_name: str = DEFAULT_DB_NAME) -> list[Path]:
    """拒绝时告诉用户「如果确实是你要删的，是这几样」：数据目录里名字在白名单上的直接子项。"""
    try:
        children = sorted(data_dir.iterdir())
    except OSError:
        return []
    return [child for child in children if child.name in OWNED_NAMES or _is_db_family(child.name, {db_name, DEFAULT_DB_NAME})]


def plan_data_purge(settings: Any, *, purge_knowledge: bool, purge_profiles: bool) -> DataPurgePlan:
    from horosa_skill.knowledge.user import STATE_DIRNAME, knowledge_dir
    from horosa_skill.profiles import profiles_dir

    plan = DataPurgePlan()
    data_dir = Path(settings.data_dir)
    if not data_dir.exists():
        return plan
    data_resolved = _resolved(data_dir)
    notes_dir = Path(knowledge_dir(settings))
    optional = {  # 用户数据里要单独点头才删的三样
        _resolved(notes_dir): purge_knowledge,
        _resolved(data_dir / STATE_DIRNAME): purge_knowledge,
        _resolved(Path(profiles_dir(settings))): purge_profiles,
    }
    protected = {path for path, purge in optional.items() if not purge}
    db_names = {DEFAULT_DB_NAME}
    # 名字不在白名单上、但按配置就是本工具的目录：点了头要删的知识库 / 档案，以及指到数据目录里别处的产物 / trace 目录
    configured: set[Path] = {path for path, purge in optional.items() if purge}
    for label in ("db_path", "output_dir", "trace_dir"):
        value = getattr(settings, label, None)
        if value is None:
            continue
        resolved = _resolved(Path(value))
        if not resolved.is_relative_to(data_resolved) or resolved == data_resolved:
            if resolved != data_resolved and Path(value).exists():
                plan.outside_data_dir.append(Path(value))
            continue
        if label == "db_path":
            if resolved.parent == data_resolved:
                db_names.add(resolved.name)
        else:
            configured.add(resolved)

    for child in sorted(data_dir.iterdir()):
        resolved = _resolved(child)
        if any(path.is_relative_to(resolved) for path in protected):
            plan.kept.append(child)  # 知识库 / 状态目录 / 档案本身，或包着它们的目录：整体保留，不深入挑删
            continue
        owned = child.name in OWNED_NAMES or _is_db_family(child.name, db_names) or resolved in configured
        if owned:
            plan.remove.append(child)
            continue
        # 用户自己的目录，但配置把本工具的某个目录指到了它里面：只删那个目录，外层留着
        plan.remove.extend(sorted(path for path in configured if path != resolved and path.is_relative_to(resolved) and path.exists()))
        plan.left_in_place.append(child)
    plan.rmdir_data_dir = not plan.kept and not plan.left_in_place
    if purge_knowledge and notes_dir.exists() and not _resolved(notes_dir).is_relative_to(data_resolved):
        plan.remove.append(notes_dir)  # 知识库配在数据目录之外：显式连它一起删时单独列出
    return plan


def remove_owned(path: Path) -> None:
    """删一个白名单上的路径。链接（含 Windows 的目录联接）只摘链接本身，不跟进去。"""
    from horosa_skill.runtime.manager import _rmtree_force

    if path.is_symlink() or _is_junction(path):
        try:
            path.unlink()
        except OSError:
            os.rmdir(path)  # 目录联接在部分 Windows 版本上要按目录删
        return
    if path.is_dir():
        _rmtree_force(path)  # 嵌入式 JDK 的部分文件在 Windows 上带只读位，裸 rmtree 会 PermissionError
    elif path.exists():
        path.unlink()


def _is_db_family(name: str, db_names: set[str]) -> bool:
    for db_name in db_names:
        if name == db_name or name in {db_name + suffix for suffix in _SQLITE_SIDECARS}:
            return True
        if name.startswith(db_name + ".corrupt-"):  # memory/store.py 隔离坏库时留下的备份（连同它的 -wal / -shm）
            return True
    return False


def _is_junction(path: Path) -> bool:
    try:
        return bool(path.is_junction())
    except (AttributeError, OSError):
        return False


def _resolved(path: Path) -> Path:
    try:
        return Path(path).expanduser().resolve()
    except (OSError, RuntimeError):
        return Path(os.path.abspath(os.path.expanduser(str(path))))


__all__ = ["DataPurgePlan", "OWNED_NAMES", "owned_children_present", "plan_data_purge", "refusal_reason", "remove_owned"]
