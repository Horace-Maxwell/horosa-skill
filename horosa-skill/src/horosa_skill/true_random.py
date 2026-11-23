"""真随机起卦（星阙 v3.15.0「随机起卦一律真随机」）。

上游口径（utils/trueRandom.js + astropy/astrostudy/truerandom.py）：随机只取操作系统随机源，取不到就报错，绝不退回伪随机；
要能原样重开的起法（塔罗 / 灵棋 / 地占 / 五兆 / 荆诀 / 太玄）把一段系统随机字节写成「真随机记录」`tr1-<十六进制>` 当种子，
引擎按顺序读这段字节定每一个随机决定——同一条记录传回去就是同一卦。手动整数种子、时间起卦、生辰种子、报数是确定性起法，照旧。

skill 是无头起卦：后端读种子的技法（地占 / 五兆 / 荆诀 / 太玄）在这里生成记录、作种子下发并随结果回传；本机 JS 起卦的技法
（六爻 / 灵棋 / 塔罗 / 小成图）由 vendored 上游 trueRandom.js 取 Node 的系统随机源。
"""

from __future__ import annotations

import re
import secrets
from typing import Any

ENTROPY_SEED_PREFIX = "tr1-"
_ENTROPY_SEED_RE = re.compile(r"^tr1-(?:[0-9a-fA-F]{2})+$")

# 每类一次随机起卦取的字节数 = 上游各页常量（tests/test_true_random_casting.py 读上游源逐个对拍）：
#   塔罗 shuffle.js FULL_ENTROPY_BYTES（主洗牌 + 三指定牌 + 切牌 + 计时 + 开钥五操作）/ 灵棋 lingqiCast.js LINGQI_ENTROPY_BYTES /
#   地占 geomancy/main/cast.js GEOMANCY_ENTROPY_BYTES / 五兆 WuZhaoMain.js CAST_ENTROPY_BYTES / 荆诀·太玄 各页 CAST_ENTROPY_BYTES。
ENTROPY_BYTES: dict[str, int] = {
    "tarot": 1344,
    "lingqi": 2,
    "geomancy": 192,
    "wuzhao": 64,
    "jingjue": 32,
    "taixuan": 32,
}


def new_entropy_seed(nbytes: int) -> str:
    """取 nbytes 个系统随机字节，写成真随机记录（= 上游 newEntropySeed / new_entropy_seed）。"""
    return ENTROPY_SEED_PREFIX + secrets.token_hex(int(nbytes))


def new_seed_for(technique: str) -> str:
    return new_entropy_seed(ENTROPY_BYTES[technique])


def is_entropy_seed(value: Any) -> bool:
    return isinstance(value, str) and bool(_ENTROPY_SEED_RE.match(value.strip()))


def normalized_entropy_seed(value: Any) -> str | None:
    """请求里的种子是真随机记录 → 去空白、十六进制转小写（上游 parseManualSeedInput 同口径）；否则 None。"""
    return value.strip().lower() if is_entropy_seed(value) else None


def seed_display_text(seed: Any) -> str:
    """= 上游 seedDisplayText：真随机记录只写开头 8 位短指纹（全文另在结构化字段里）；其它种子原样。"""
    if seed is None:
        return ""
    if not is_entropy_seed(seed):
        return f"{seed}"
    hexpart = seed.strip()[len(ENTROPY_SEED_PREFIX):].lower()
    return f"真随机 {hexpart}" if len(hexpart) <= 16 else f"真随机 {hexpart[:8]}…"


def random_below(n: int) -> int:
    """[0, n) 上严格等概率的整数（secrets.randbelow 内部拒绝采样，与上游 randomInt 同义）。"""
    return secrets.randbelow(int(n))


def cast_record(method: str, *, random: bool, replay: dict[str, Any]) -> dict[str, Any]:
    """所有起卦技法统一回传的 data.cast（v0.53.0）：怎么起的、是不是软件真随机、把哪几个字段原样传回就能重开同一卦。

    method 各技法自己的起法名（random / yarrow / coins / time / seed / birth_fields / counts / manual / …）；
    random=True 时 source='system'（系统随机源）；replay = {传回字段: 值}——真随机时就是完整的 tr1- 记录或掷出的结果。
    调用方无状态（save_result=False 的插件）也能凭它重开：不依赖本地记忆库。"""
    return {"method": method, "random": bool(random), "source": "system" if random else None, "replay": replay}

