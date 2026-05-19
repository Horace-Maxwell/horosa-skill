# Horosa Skill 输入契约

本页说明 AI、CLI、MCP 客户端调用 Horosa Skill 时必须提供哪些输入，以及输出应该长什么样。它的目标是防止 Agent 自己猜参数、绕过 MCP 手算，或把可用工具误判成不可用。

## 通用硬规则

- 所有会改变结果的技法在调用前都必须确认参数；未确认时会返回 `agent_guidance.required`。
- 用户确认后，payload 必须包含 `agent_confirmed_settings: true` 和 `clarification_notes`。
- 如果用户明确说“按星阙默认”，payload 可以包含 `defaults_accepted: true`，但仍建议写明 `clarification_notes`。
- 任何 AI 客户端都应该先调用 `horosa_agent_guidance` 或 CLI `agent guidance`，再调用真实技法。
- 计算结果必须以 `export_snapshot.export_text`、`export_format.sections` 和 `summary` 为准，不能用 Shell/Python/Web Search 手写算法替代。

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
| `time` | 本命/事件时间 | `05:30` | 不知道精确时间必须先问用户 |
| `zone` | 本命/事件时区 | `+08:00` | 也接受 `8` 或 IANA 名称如 `America/Los_Angeles`，会按起盘日期时间规范化 |
| `lat` | 本命/事件纬度 | `31n13` | 也可用 `gpsLat` 输入小数 |
| `lon` | 本命/事件经度 | `121e28` | 也可用 `gpsLon` 输入小数 |
| `hsys` | 宫制 | `0` | 星阙默认 `0` 为整宫制 |
| `zodiacal` | 黄道体系 | `0` | 星阙默认 `0` 为回归黄道 |
| `agent_confirmed_settings` | 已确认参数 | `true` | Agent 问完用户后必须带 |
| `clarification_notes` | 确认说明 | `用户确认出生时间、地点、整宫制、回归黄道。` | 用于 memory 和审计 |

IANA 时区会在进入 runtime 前转换为后端稳定接受的固定 offset。例如 `date=2026-05-18`、`time=13:14`、`zone=America/Los_Angeles` 会归一化为 `-07:00`；冬令时日期会自动归一化为 `-08:00`。如果用户只给时区名但没有日期/时间，agent 必须先补问日期和时间，不能让后端猜。

## 推运、返照与时运输入

这批工具不能只看“接口是否返回 ok”。正确输出必须包含对应时间点的盘面数据。

| 工具 | 中文 | 必填输入 | 目标时间/地点字段 | 正确输出必须包含 |
| --- | --- | --- | --- | --- |
| `solarreturn` | 太阳返照 | `date`、`time`、`zone`、`lat`、`lon`、`datetime`、`dirZone`、`dirLat`、`dirLon` | `datetime` 为返照目标时间；`dir*` 为返照地点 | 本命盘起盘信息、本命盘星与虚点、返照盘起盘信息、返照盘星与虚点、返照盘相位 |
| `lunarreturn` | 月亮返照 | `date`、`time`、`zone`、`lat`、`lon`、`datetime`、`dirZone`、`dirLat`、`dirLon` | `datetime` 为月返目标时间；`dir*` 为月返地点 | 本命盘起盘信息、本命盘星与虚点、返照盘起盘信息、返照盘星与虚点、返照盘相位 |
| `givenyear` | 指定年推运 / 流年 | `date`、`time`、`zone`、`lat`、`lon`、`datetime`、`dirZone`、`dirLat`、`dirLon` | `datetime` 为指定年中的目标时间；`dir*` 为流年盘地点 | 本命盘起盘信息、本命盘星与虚点、流年盘起盘信息、流年盘星与虚点、流年盘相位 |
| `solararc` | 太阳弧推运 | `date`、`time`、`zone`、`lat`、`lon`、`datetime`、`dirZone` | `datetime` 为推运目标时间 | 本命盘起盘信息、本命盘星与虚点、推运盘起盘信息、推运盘星与虚点、推运盘相位 |
| `profection` | 小限 / 年运推限 | `date`、`time`、`zone`、`lat`、`lon`、`datetime`、`dirZone` | `datetime` 为目标年份/时间 | 本命盘起盘信息、本命盘星与虚点、推运盘起盘信息、推运盘星与虚点、推运盘相位 |
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
  "pdMethod": "astroapp_alchabitius",
  "pdTimeKey": "Ptolemy",
  "pdaspects": [0, 60, 90, 120, 180],
  "agent_confirmed_settings": true,
  "clarification_notes": "用户确认主限方法、时间钥匙和相位列表。"
}
```

## Agent 必须如何追问

如果用户只说“帮我看今年运势”，Agent 不能直接调用 `solarreturn`、`givenyear` 或 `pd`。它应该先问：

```text
请确认：
1. 本命出生日期、时间、时区、地点是什么？
2. 要看哪一年或哪一个具体时间点？
3. 推运/返照地点用出生地、现居地，还是指定城市？
4. 宫制、黄道、主限方法等是否按星阙默认？
```

用户确认后再调用真实工具。若 MCP 返回 `agent_guidance.required`，AI 客户端必须把 `details.agent_recovery.prompt_to_user` 发给用户，而不是重试或自行补参。

## 输出验收标准

推运类工具只返回 `ok=true` 还不够。验收时必须检查：

- `export_snapshot.export_text` 非空。
- `export_format.sections` 包含对应的本命盘、目标盘、相位或表格章节。
- 不要只看 `export_text` 的短预览；这些工具通常先写本命盘，返照盘 / 推运盘 / 流年盘 / 主限表格可能在后续 section。
- `pd` 的表格有真实行；不能只有标题。
- `zr` 的时间轴有层级行；不能显示“无数据”。
- `memory_show` 能读回该 run。
- 需要报告时，`report_render` 能生成 JSON / DOCX / PDF artifact。

完整审计建议见 [`EXPORT_AUDIT_GUIDE.md`](./EXPORT_AUDIT_GUIDE.md)。如果本地生成了 `HOROSA_IO_AUDIT_*/predictive_tools_full_export_sections.md`，优先看这份按 section 展开的文件，而不是 `all_tool_inputs_outputs_summary.md` 里的短预览。

## 常用 CLI

```bash
uv run horosa-skill tool list
uv run horosa-skill agent guidance --tool pdchart
echo '<payload.json>' | uv run horosa-skill tool run solarreturn --stdin
echo '<payload.json>' | uv run horosa-skill report from-tool solarreturn --stdin --format pdf --question "请分析这一年事业与关系走势"
```
