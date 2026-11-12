# Horosa Skill 输入契约

> 读者：AI 客户端 + 维护者。何时读：查每个工具的必填字段与输入契约时。

本页说明 AI、CLI、MCP 客户端调用 Horosa Skill 时必须提供哪些输入，以及输出应该长什么样。它的目标是防止 Agent 自己猜参数、绕过 MCP 手算，或把可用工具误判成不可用。

## 通用硬规则

- 会改变结果的问题还没回答时，调用返回 `agent_guidance.required`（澄清闸）。闸门只问**还没回答**的：载荷已回答的不问、与本次无关的不问，什么都不缺就直接起盘、不需要任何确认标记（例：`huangli {"date": "2026-11-12"}`）。
- **事实**（出生 / 起课钟点、性别、合盘的另一个人、起课的「此刻」、推运目标年、卦名等，追问条目带 `fact: true`）只有用户知道：`agent_confirmed_settings` / `defaults_accepted` 代替不了，必须把值写进载荷再重试（`details.agent_recovery.example_payload` 给出位置）。
- **设置**（宫制、流派、起局方式…）：用户回答后带 `agent_confirmed_settings: true` + `clarification_notes`；用户明确说「按星阙默认」时带 `defaults_accepted: true`（仍建议写 `clarification_notes`）。两个标记都必须是 JSON `true`——`"true"` / `1` 回 `tool.confirmation_flag_not_boolean`。Agent 不得在用户没回答时自己带上。
- 字段写法错误先于闸门报出（见下「逐字段校验」）：同一次调用不会先弹设置问卷、再报字段错。
- 任何 AI 客户端都应该先调用 `horosa_agent_guidance` 或 CLI `agent guidance`，再调用真实技法（`intent` 传用户原话时只回最相关的几种技法和各自要的字段）。
- 计算结果必须以 `export_snapshot.export_text`、`export_snapshot.sections` 和 `summary` 为准，不能用 Shell/Python/Web Search 手写算法替代。MCP 缺省返回阅读视图（正文 + 段索引 + 技法依据卡，见 [`DATA_CONTRACTS.md`](./DATA_CONTRACTS.md)「MCP 结果视图」）；CLI 与存档是完整信封。

CLI 查询方式：

```bash
uv run horosa-skill agent guidance --tool solarreturn
uv run horosa-skill tool list
```

MCP 查询方式：

```text
horosa_agent_guidance({ "tool_name": "solarreturn" })
```

## 基础星盘类输入

这些字段是星盘、返照、推运、主限等西洋/七政类工具的基础：

| 字段 | 含义 | 示例 | 说明 |
| --- | --- | --- | --- |
| `date` | 本命/事件日期 | `1995-06-03` | 公历时用 `ad=1` |
| `time` | 本命/事件时间 | `05:30` | 不知道精确时间必须先问用户（没有「时间不详」模式，见下） |
| `zone` | 本命/事件时区 | `+08:00` | 也接受小时数 `8` / `-5` / `5.5`、`UTC+8`、`东八区`、`E8` / `W5`、IANA 名称如 `America/Los_Angeles`（按起盘日期时间规范化）；给了 `place` 可省 |
| `lat` | 本命/事件纬度 | `31n13` | 也可用 `gpsLat` 输入小数；给了 `place` 可省 |
| `lon` | 本命/事件经度 | `121e28` | 也可用 `gpsLon` 输入小数；给了 `place` 可省 |
| `place` | 地名 | `上海` / `London, UK` | 解析出坐标与那一天的时区（含夏令时）；同名多地会请用户选（`place.ambiguous`） |
| `name` | 当事人 | `妈妈` | 透传盘头；存档可按人查找（`horosa_memory_query {"entity": …}`） |
| `profile` | 命主档案名 | `妈妈` | `horosa_profile` 存过的出生信息；显式字段逐键优先 |
| `gender` | 性别 | `女` / `0` | 也认 `男/女`、`乾造/坤造`、`先生/小姐`、`male/female`；结果随性别而变的技法缺了会单独问 |
| `hsys` | 宫制 | `1` | 星阙默认 `1` = Alcabitus（不是 Placidus；`0` 整宫制、`3` Placidus）；也认宫制名（`Placidus`、`整宫制`、`whole sign`…），越表的编号被拒并列出全表 |
| `zodiacal` | 黄道体系 | `0` | 星阙默认 `0` 为回归黄道；`1` 恒星黄道配 `siderealAyanamsa`（缺省 lahiri） |
| `agent_confirmed_settings` | 已确认设置 | `true` | 用户回答设置类问题后才带；代替不了事实 |
| `clarification_notes` | 确认说明 | `用户确认出生时间、地点、Alcabitus 宫制、回归黄道。` | 用于 memory 和审计（过长会截断并告警） |

IANA 时区会在进入 runtime 前转换为后端稳定接受的固定 offset。例如 `date=2026-05-18`、`time=13:14`、`zone=America/Los_Angeles` 会归一化为 `-07:00`；冬令时日期会自动归一化为 `-08:00`；钟点落在夏令时切换的空档或重叠里时回 `tool.zone_ambiguous`，请用户在两个偏移里选。如果用户只给时区名但没有日期/时间，agent 必须先补问日期和时间，不能让后端猜。

**`zone` 与 `place` 的关系（当前行为）**：只给 `place` 时，时区按地点 + 日期推得（含夏令时，如中国 1986–1991 年的夏令时、美国夏令时），结果的 `summary` 与技法卡 `place_resolution` 写明 `zone_source`；`place` 与显式 `zone` 同时给时，显式 `zone` 照原样用、不按地点核对夏令时（`zone_source: explicit`）。用户只说了城市时，传 `place`、不要自己写偏移。给了经纬度和地名、没给时区时，按坐标与出生日期补时区。

## 逐字段校验（v0.50.0）

日期、时刻、时区、经纬度、性别对所有技法（含合盘 `inner` / `outer`、推运 `dir*`）同一套规则：读得懂的写法照收并在 `warnings` 说明怎么读的，读不懂或说不清的按字段拒绝，错误的 `details.agent_recovery.fix_fields` 每个字段一条（`field` / `got` / `expected` / `example` / `options`），只有用户能答的标 `must_ask_user: true`。

| 字段 | 读得懂（示例） | 会被拒（错误码） |
| --- | --- | --- |
| `date` | `1990-05-03`、`1990/5/3`、`1990.5.3`、`19900503`、`1990年5月3日`；公元前 `-0500-03-21` 或配 `ad: -1` | `03/05/1990`（`tool.ambiguous_date`，给两种读法）、农历日期（`tool.lunar_date_unsupported`，先用 `horosa_cn_calendar_month` 查公历日）、不存在的日期（`tool.invalid_date`） |
| `time` | `08:30`、`0830`、`8点半`、`上午8点`、`8:30 PM` | 「辰时」（`tool.time_is_shichen`，给出该时辰的钟表时段、请用户定钟点）、「不详」/ `unknown`（`tool.time_unknown`）、`25:00`（`tool.invalid_time`）；缺了是 `tool.missing_field` |
| `zone` | 见上表 | `480`（`tool.invalid_zone`，像分钟数）、`CST` / `EST` / `IST` 这类多义缩写（`tool.invalid_zone`，列出候选偏移） |
| `lat` / `lon` | `31n13`、`31.22`、`北纬31.22`、`31°13′N`、`E121.47` | `40n75`、超出范围、经纬对调（`tool.invalid_coordinate`） |
| `gender` | 见上表 | 「其他」等（`tool.invalid_gender`）；需要性别的技法没给（`tool.missing_gender` 或闸门里的事实问题） |

**没有「时间不详」模式**：钟点缺失、写「不详」或只给时辰时一律拒绝并请问用户，不会默认成 0 点或正午。设置值（流派 / 口径 / 传本 / 宫制…）认不出时回 `tool.invalid_option`，`details.accepted` 列出可选值，不再静默换成缺省。工具不认识的参数会在 `warnings` 里点名（并提示最接近的参数名）；`timezone` / `tz` / `latitude` / `longitude` / `lng` / `sex` / `house_system` 这类别名照收并说明。

结果随性别而变、缺性别会单独追问的技法（17 种）：`bazi_birth`、`bazi_direct`、`ziwei_birth`、`ziweizeri`、`liureng_runyear`、`canping`、`heluo`、`yizhangjing`、`zhengchuan`（铁算心易除外）、`shaozi`、`tieban`、`beiji`、`nanji`、`chunzi`、`xianqin`、`cetian`、`qizhengkin`（`agent_guidance/questions.py::GENDER_FACT_TOOLS`）。

## 推运、返照与时运输入

这批工具不能只看“接口是否返回 ok”。正确输出必须包含对应时间点的盘面数据。

| 工具 | 中文 | 必填输入 | 目标时间/地点字段 | 正确输出必须包含 |
| --- | --- | --- | --- | --- |
| `solarreturn` | 太阳返照 | `date`、`time`、`zone`、`lat`、`lon`（或 `place`）+ 目标年 | `datetime` 为返照目标时间（只给年份 `"2031"` 或 `year: 2031` = 那一年的生日时刻，`warnings` 写明）；`dir*` 为返照地点 | 本命盘配置、起盘信息、时段盘配置、相位 |
| `lunarreturn` | 月亮返照 | `date`、`time`、`zone`、`lat`、`lon`、`datetime`、`dirZone`、`dirLat`、`dirLon` | `datetime` 为月返目标时间；`dir*` 为月返地点 | 本命盘配置、起盘信息、时段盘配置、相位 |
| `givenyear` | 指定年推运 / 流年 | `date`、`time`、`zone`、`lat`、`lon`、`datetime`、`dirZone`、`dirLat`、`dirLon` | `datetime` 为指定年中的目标时间；`dir*` 为流年盘地点 | 本命盘配置、起盘信息、时段盘配置、相位 |
| `solararc` | 太阳弧推运 | `date`、`time`、`zone`、`lat`、`lon`、`datetime`、`dirZone` | `datetime` 为推运目标时间 | 本命盘配置、起盘信息、时段盘配置、相位 |
| `profection` | 小限 / 年运推限 | `date`、`time`、`zone`、`lat`、`lon`、`datetime`、`dirZone` | `datetime` 为目标年份/时间 | 本命盘配置、起盘信息、时段盘配置、相位 |
| `pd` | 本初方向 / 主限表 | `date`、`time`、`zone`、`lat`、`lon`、`pdtype`、`pdMethod`、`pdTimeKey`、`pdaspects` | `pdMethod` 和 `pdTimeKey` 决定表格算法 | 主限设置、真实主限表格 |
| `pdchart` | 主限法盘 | `date`、`time`、`zone`、`lat`、`lon`、`datetime`、`dirZone`、`pdtype`、`pdMethod`、`pdTimeKey` | `datetime` 为主限盘目标时间 | 本命盘星与虚点、主限法盘星体表格、主限法盘相位 |
| `zr` | 黄道释放 | `date`、`time`、`zone`、`lat`、`lon` | 可选 `startSign`、`stopLevelIdx` | 黄道释放设置、黄道释放时间轴 |
| `firdaria` | 法达星限 | `date`、`time`、`zone`、`lat`、`lon` | 按本命盘日夜与星阙默认排序 | 法达星限时间轴 |
| `decennials` | 十年星限 | `date`、`time`、`zone`、`lat`、`lon` | 可指定起算、排序、日法 | 十年星限时间层级 |

### 太阳返照示例

```json
{
  "date": "1995-06-03",
  "time": "05:30",
  "zone": "+08:00",
  "lat": "31n13",
  "lon": "121e28",
  "hsys": 0,
  "zodiacal": 0,
  "datetime": "2031-04-06 09:33:00",
  "dirZone": "+08:00",
  "dirLat": "31n13",
  "dirLon": "121e28",
  "agent_confirmed_settings": true,
  "clarification_notes": "用户确认本命信息、返照年份、返照地点与星阙默认宫制。"
}
```

### 主限表示例

```json
{
  "date": "1995-06-03",
  "time": "05:30",
  "zone": "+08:00",
  "lat": "31n13",
  "lon": "121e28",
  "pdtype": 0,
  "pdMethod": "core_alchabitius",
  "pdTimeKey": "Ptolemy",
  "pdaspects": [0, 60, 90, 120, 180],
  "agent_confirmed_settings": true,
  "clarification_notes": "用户确认主限方法、时间钥匙和相位列表。"
}
```

## 卜筮起卦类输入（geomancy / tarot / mundane）

这三个工具不走「本命出生信息」而走「起卦/定盘时刻」，字段含义与星盘类不同：

| 工具 | 中文 | 必填输入 | 关键可选字段 | 正确输出必须包含 |
| --- | --- | --- | --- | --- |
| `geomancy` | 天文地占 | `date`、`time`、`zone`、`lat`、`lon`（起卦时刻与地点，时刻派生确定性种子） | `question` 所问；`questionType` 问类；`profile` 传本流派（`european_classical`/`planetary`/`modern`/`arabic_raml`/`india_ramal`/`sikidy`/`hakata`） | 起卦信息、判定、十二宫·图形入宫、十六图形 |
| `tarot` | 塔罗 | `date`、`time`、`zone`、`lat`、`lon`（或 `place`；起卦时刻派生抽牌种子，同刻同问可复现） | `question` 所问；`spread` 牌阵（默认 `three`）；`deck` 牌系（默认 `rws` 韦特）；`seed` 显式种子（覆盖时间种子）；`usesReversals` 是否用逆位 | 起卦信息、牌阵直断、牌阵细论、综合建议 |
| `mundane` | 世俗盘 | `year`（年份；`date`/`time` 由入宫节气推得，不需要传） | `ingressTerm` 入宫节气（`春分`/`夏至`/`秋分`/`冬至`，默认春分）；`zone`/`lat`/`lon` 定盘地点 | 世俗入宫、新月图、满月图、日食图、月食图、地区盘、行星周期、定局·年主/盘主、地理分野、地区盘推运 |

起卦类同样受澄清闸管：`question` / 牌阵 / 流派 / 年份没给时返回 `agent_guidance.required`；都给了（如塔罗带 `question` + `spread`）就直接起课。塔罗的 `spread` 只收引擎键（`single` / `three` / `celtic` …），写错回 `tool.tarot_unknown_spread` 并在 `details.allowed` 列出该牌系可用的牌阵。

**经 `horosa_dispatch` / `horosa_hecan` 调起课类技法**（奇门 / 六壬 / 六爻 / 塔罗 / 黄历 / 地占…）时，起课时刻放在 `context`（`date` / `time` / `zone` 或 `place`）：这些技法只读 `context`，不用出生数据顶替，服务端也不拿自己的时钟当用户的「此刻」；缺了就在追问里点名（事实，确认标记代替不了）。只给了地点、问句里说了日期或年份（「2027年立春」）时，时区按那一天推得。每个技法用了哪个时刻写在结果的 `time_basis`。直接调技法工具时，起课时刻就是顶层的 `date` / `time`。

## Agent 必须如何追问

如果用户只说“帮我看今年运势”，Agent 不能直接调用 `solarreturn`、`givenyear` 或 `pd`。它应该先问：

```text
请确认：
1. 本命出生日期、时间、时区、地点是什么？
2. 要看哪一年或哪一个具体时间点？
3. 推运/返照地点用出生地、现居地，还是指定城市？
4. 宫制、黄道、主限方法等是否按星阙默认？
```

用户确认后再调用真实工具。若 MCP 返回 `agent_guidance.required`，AI 客户端必须把 `details.agent_recovery.prompt_to_user` 发给用户，而不是重试或自行补参。`must_ask_user: false` 的错误（字段写法、记忆 / 报告调用缺 `run_id` 之类）是 agent 自己改入参重试，不必问用户。

## 输出验收标准

推运类工具只返回 `ok=true` 还不够。验收时必须检查：

- `export_snapshot.export_text` 非空。
- `export_snapshot.sections` 包含对应的本命盘、目标盘、相位或表格章节。
- 不要只看 `export_text` 的短预览；这些工具通常先写本命盘，返照盘 / 推运盘 / 流年盘 / 主限表格可能在后续 section。
- `pd` 的表格有真实行；不能只有标题。
- `zr` 的时间轴有层级行；不能显示“无数据”。
- `memory_show` 能读回该 run（MCP 上被预算裁掉的段按 `warnings` 里的续读调用取回，别当成缺段）。
- 需要报告时，`report_render` 能生成 JSON / DOCX / PDF artifact。

完整审计建议见 [`EXPORT_AUDIT_GUIDE.md`](./EXPORT_AUDIT_GUIDE.md)。如果本地生成了 `HOROSA_IO_AUDIT_*/predictive_tools_full_export_sections.md`，优先看这份按 section 展开的文件，而不是 `all_tool_inputs_outputs_summary.md` 里的短预览。

## 常用 CLI

```bash
uv run horosa-skill tool list
uv run horosa-skill agent guidance --tool pdchart
echo '<payload.json>' | uv run horosa-skill tool run solarreturn --stdin
echo '<payload.json>' | uv run horosa-skill report from-tool solarreturn --stdin --format pdf --question "请分析这一年事业与关系走势"
```
