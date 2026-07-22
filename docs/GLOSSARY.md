# 领域名词表 / Glossary

术数体系、引擎与工程术语速查。给第一次接触本仓库的人（人或 agent）一个统一口径；
详细算法见各引擎源码，详细契约见 [`INPUT_CONTRACTS.md`](./INPUT_CONTRACTS.md) /
[`DATA_CONTRACTS.md`](./DATA_CONTRACTS.md)，架构见 [`ARCHITECTURE.md`](./ARCHITECTURE.md)。

## 三式（奇门 / 太乙 / 金口）

| 术语 | 英文 / 键 | 含义 |
| --- | --- | --- |
| 奇门遁甲 | qimen · `/qimen/pan` | 以时家奇门排盘，九宫布星/门/神。盘面由 `ken` 引擎 **kinqimen** 计算。 |
| 太乙神数 | taiyi · `/taiyi/pan` | 太乙式盘，主客算、积年。盘面由 **kintaiyi** 计算。 |
| 金口诀 | jinkou · `/jinkou/pan` | 大六壬支系，贵神/将神起课。盘面由 **kinjinkou** 计算。 |
| 三式合一 | sanshiunited | 奇门 + 太乙 + 金口 三盘合参的富化导出段，聚合三个既有 `ken` 引擎的结果。 |
| 法奇门 | fa-qimen · `DunJiaFaCalc.js` | 奇门的“法术”流派排盘（对宫表等），JS 层实现。 |

## 星盘 / 占星族（chart family）

| 术语 | 英文 / 键 | 含义 |
| --- | --- | --- |
| 本命盘 / 星盘 | natal chart · `/chart` | 出生时刻的西洋占星盘，flatlib + Swiss Ephemeris 计算。 |
| 世俗盘 | mundane | 以入宫节气（春分/夏至/秋分/冬至）为时刻的世俗占星盘 + 子盘群（新月/满月/日月食/行星周期/地区盘），走 `/astroextra/*` 精算端点。 |
| 天文地占 | geomancy · `/geomancy/reading` | 由起卦时刻确定性派生 4 母卦 → 16 图形 → 十二宫入宫 + 判官见证。 |
| 塔罗 | tarot | 由起卦时刻派生确定性抽牌种子，同刻同问可复现；牌阵直断/细论/综合建议。 |
| 占星地图 | acg / astrocartography · `/location/acg` | 行星地平/子午线在地表的投影线（ACG lines）+ parans + 中点。 |
| 名人星盘库 | astrodata | 内置名人出生数据库（`astrodata-aa.sqlite.gz`，约 5.9 万人），支持检索比对；`name_zh` 列为中文化名。 |
| 推运 | progression / predictive · `/predict/*` · `/astroextra/*` | 三分主星、次限、太阳弧、行星返照、赤纬推运等预测技法。 |

## 神数族（14 引擎）

| 术语 | 键 | 含义 |
| --- | --- | --- |
| 5 独立神数 | wangji / wuzhao / taixuan / jingjue / shenyishu | 皇极经世（心易发微）、五兆、太玄筮法、undefined 靖爵、神仪数等，各自独立 Python 引擎。 |
| 9 kinastro 神数 | shaozi / tieban / fendjing / beiji / nanji / chunzi / xianqin / cetian / qizhengkin | 邵子、铁板、分金、北极、南极、纯子、先秦、测天、七政等，共用 **kinastro** 引擎。 |
| 邵子神数 | shaozi | 需从条文 CSV 生成 `shaozi_tiaowen_6144.json`（打包时生成 4608 条真条文，否则出占位条文）。 |
| 一掌经 | yizhangjing | 十二支六道排盘 + 大限小限流年 + 神煞合参，JS 层实现（v0.17.0）。 |

## 其他术数

| 术语 | 键 | 含义 |
| --- | --- | --- |
| 大六壬 | liureng | 十二天将起课；断卦层含年月神煞/课体/三传旺衰/空亡等；六壬七政为其扩展（v0.20.0）。 |
| 八字 / 四柱 | bazi | 年月日时四柱；参评（canping）/河洛（heluo）在进程内经 `lunar-javascript` 排四柱。 |
| 紫微斗数 | ziwei | 十二宫主星排盘。 |
| 六爻 | sixyao | 纳甲装卦，含世应/六亲/用神/旺衰/飞伏/六神/动变。 |
| 黄历 / 万年历 | almanac | 农历/节气/神煞，依赖 java 端 `/nongli/time` + `/jieqi/year`（v0.20.0 新工具）。 |
| 统摄法 | tongshefa | 星阙自有的本地 JS 算法。 |
| 择日 / 卜卦 | election / divination · horary | 择吉与起卦断验。 |
| 大运 | dayun / decennial | 十年大运。 |
| 晚子时 | late-zi hour | 23:00–24:00 归当日或次日的处理开关（`lateZiHourUseNextDay`）。 |

## 运行时与工程

| 术语 | 含义 |
| --- | --- |
| `ken` 引擎 | [kentang2017](https://github.com/kentang2017) 开源的 kinqimen / kintaiyi / kinjinkou 三个 Python 引擎（MIT），随离线 runtime 分发，是奇门/太乙/金口的算权威。 |
| kentang | 把 `ken` + 神数 服务挂载到 chart service 的注册表；离线 payload 只带部分引擎，故需优雅降级（新版 registry 自带惰性挂载 `_LazyMountedService`）。 |
| chart service（:8899） | Python astropy `websrv`，对外 `/qimen/pan`、`/geomancy/reading`、`/location/acg`、各 `/*/pan` 等端点。 |
| java 后端（:9999） | `astrostudyboot.jar`，对外 `/chart`、`/nongli/time`、`/jieqi/year` 等；Temurin 17 需 `-Dfile.encoding=UTF-8 -Dsun.jnu.encoding=UTF-8` 避免 CJK 乱码。 |
| horosa-core-js | headless Node/JS 层：`tongshefa` 计算 + 把 `ken` 结果格式化成 `aiExport.js` 段。技法 JS（如 yizhangjing/liureng/dunjia）在此，随 repo 走。 |
| aiExport.js | 星阙的导出段格式化器（各技法的 `[段名]` 富化）。 |
| 离线 runtime / offline runtime | 打包 Python(embed) + JDK17 + Node + astropy + 引擎 + core-js 的自足运行时，作为 GitHub Release 资产分发。 |
| `runtime-manifest.json` | 发布清单：映射平台→归档 URL/sha（外层），以及嵌入 payload 的版本/契约（内层）。 |
| `export_registry_version` | 导出契约版本号，两个 builder 必须同步 stamp（数字漂移由 `verify_builder_parity.py` 拦截）。 |
| 双平台 manifest | 同时含 `darwin-arm64` + `win32-x64` 两个平台条目。 |
| pin-forward | mac 侧把新版 manifest 的 `win32-x64` 临时指向上一个已构建 win zip 的策略——守卫绿、install 不坏，但 Windows 落后若干版，直到 Windows 侧补齐真半边。详见 [`LESSONS.md`](./LESSONS.md)。 |
| release-completeness 守卫 | CI：发布后查 `latest` 是否双平台 / 归档是否 404。 |
| builder-parity lint | CI：查 mac 与 Windows 两个 builder + 验证器契约是否漂移。 |
| `sync_windows_release.py` | Windows 侧一条命令补齐：检测缺半边 → 构建 → 下载 darwin → 双 manifest + 校验和 → 验证 → 上传。 |

## 导出契约与闸门（工程补充）

| 术语 | 含义 |
| --- | --- |
| envelope / ToolEnvelope | 每个工具统一返回信封 `{ok, tool, version, data, error, …}`；失败 `ok=False` + `error.code`，永不抛裸异常。 |
| export_snapshot / export_text | 星阙式 AI 导出正文（`[小节]` 结构纯文本）——解释结果的唯一事实来源。 |
| preset / `AI_EXPORT_PRESET_SECTIONS` | 每技法「应出哪些段」的契约表（镜像上游 aiExport.js），在 `exports/registry.py`。 |
| `AI_EXPORT_OPTIONAL_SECTIONS` | 条件段白名单：段可能不出现时登记于此；条件段必须 preset+optional 双登记。 |
| missing / unknown_detected_sections | 契约核对两类偏差：预期未出现 / 出现但不在 preset；干净导出 = 两者皆空。 |
| `MIRRORED_UPSTREAM_AIEXPORT_VERSION` | 机读镜像基线：导出契约对齐到上游 aiExport 第几版（现 48，逐技法对齐；`verify_export_contract_mirror.py` 断言 vendored aiExport 版本 == 本常量）。 |
| 冻结值（课/局/卦） | 占卦型技法（小六壬/飞宫/小成图/皇极轨策/卜卦）的起卦结果一经起出即冻结——改流派/设置只重排判读，绝不按时重起（重起=伪造用户没见过的盘）。 |
| 神数正传五流派 | `zhengchuan` 一入口含 铁板/邵子/大定/六亲/铁算心易；`school` 选定；除铁算心易（查询层）外皆需生辰四柱（走 `/nongli/time` 权威柱）。 |
| agent_guidance 闸门 / `agent_recovery` | 运行时澄清闸：设置未确认返回 `agent_guidance.required`；`details.agent_recovery.prompt_to_user` 可直接转发追问；确认后带 `agent_confirmed_settings`/`defaults_accepted`。 |
| elicitation 双轨 | 客户端声明 MCP elicitation 能力时闸门弹原生表单（按默认一跳闭环），否则回落错误往返；`HOROSA_MCP_ELICIT=0` 关闭。 |
| 命盘 / 事盘 | 上游概念：命盘=出生数据可重算；事盘=一次性占例（六爻/卜卦），永不按时间重算。 |
| FakeClient / FakeJsClient | 离线测试桩（HTTP/JS 层），必须返回真内容（禁裸「无」、禁 generated_template 回退）。 |
| pdSyncRev | chart 服务心跳回显的主限引擎同步版本号（防陈旧实例静默吞新钥匙）。 |
| run / artifact / memory | 每次调用落一条可检索记录（SQLite FTS + JSON artifact + AI 回答写回）。 |
