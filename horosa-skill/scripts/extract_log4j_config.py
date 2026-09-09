#!/usr/bin/env python3
"""从 jar 里抽出 log4j2.xml，把 basedir 改写成真路径。

🔴 jar 内的配置写的是 `<Property name="basedir">${env:HOME:-${sys:user.home}}/.horosa-logs/…</Property>`。
log4j 不展开这个**带默认值**的写法，于是把整串当字面量目录名，日志落进启动时 CWD 下的
`./${env:HOME:-${sys:user.home}}/.horosa-logs/…` —— 仓根、horosa-skill/、vendor/runtime-source/ 下
各攒了一份（v0.37.0 清理时实见三处）。
`-Dbasedir=` 覆盖不了它：<Property> 在配置里已定义，系统属性只在**未定义**时兜底。
唯一办法就是抽出来改写，再用 -Dlog4j2.configurationFile 指过去。
已装 runtime 走 manager._rewrite_runtime_log4j（安装时补丁）；dev 直跑 vendored jar 是漏网的那条路。
"""
import pathlib
import re
import sys
import zipfile

jar, out, log_root = sys.argv[1], sys.argv[2], sys.argv[3]
with zipfile.ZipFile(jar) as archive:
    names = [n for n in archive.namelist() if n.endswith("log4j2.xml")]
    if not names:
        raise SystemExit(1)
    text = archive.read(names[0]).decode("utf-8", "replace")
updated = re.sub(
    r'(<Property\s+name="basedir">).*?(</Property>)',
    lambda m: f"{m.group(1)}{log_root}/astrostudyboot{m.group(2)}",
    text,
    count=1,
    flags=re.DOTALL,
)
if updated == text:
    raise SystemExit(2)
path = pathlib.Path(out)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(updated, encoding="utf-8")
