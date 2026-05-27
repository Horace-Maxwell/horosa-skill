# Algorithm Coverage

This document is the shipping coverage matrix for the offline GitHub distribution.

It answers one question only:

Can this method be called locally after `horosa-skill install`, without depending on an external Horosa service?

## Shipping Rule

- `Included` means the method is available through the offline runtime and the skill layer.
- `Excluded` means it is intentionally not part of this release.
- This release explicitly excludes `fengshui`.

## Coverage Matrix

| Domain | Method / Tool | Runtime Layer | Status | Notes |
| --- | --- | --- | --- | --- |
| Export | `export_registry` | local Python | Included | Machines can inspect the full Xingque AI export registry. |
| Export | `export_parse` | local Python | Included | Machines can parse export text into structured JSON. |
| Astro | `chart` | local Java + Python | Included | Uses local backend and local chart runtime. |
| Astro | `chart13` | local Java + Python | Included | Included in the offline runtime payload. |
| Astro | `relative` | local Java + Python | Included | Runs through the local runtime services. |
| Astro | `india_chart` | local Java + Python | Included | Runs through the local runtime services. |
| Predictive | `solarreturn` | local Java + Python | Included | Runs through the local runtime services. |
| Predictive | `lunarreturn` | local Java + Python | Included | Runs through the local runtime services. |
| Predictive | `solararc` | local Java + Python | Included | Runs through the local runtime services. |
| Predictive | `givenyear` | local Java + Python | Included | Runs through the local runtime services. |
| Predictive | `profection` | local Java + Python | Included | Runs through the local runtime services. |
| Predictive | `pd` | local Java + Python | Included | Runs through the local runtime services. |
| Predictive | `pdchart` | local Java + Python | Included | Runs through the local runtime services. |
| Predictive | `zr` | local Java + Python | Included | Runs through the local runtime services. |
| Predictive | `decennials` | local Python (headless port) | Included | 十年大运 — headless Python port of 星阙 `utils/decennials.js`; value-aligned (`Math.round`/`Math.ceil` parity), cross-checked against 星阙's `decennials.test.js`. No backend / no ken. |
| Chinese Metaphysics | `ziwei_birth` | local Java + Python | Included | Runs through the local runtime services. |
| Chinese Metaphysics | `ziwei_rules` | local Java + Python | Included | Runs through the local runtime services. |
| Chinese Metaphysics | `bazi_birth` | local Java + Python | Included | Runs through the local runtime services. |
| Chinese Metaphysics | `bazi_direct` | local Java + Python | Included | Runs through the local runtime services. |
| Chinese Metaphysics | `liureng_gods` | local Java + Python | Included | Runs through the local runtime services. |
| Chinese Metaphysics | `liureng_runyear` | local Java + Python | Included | Runs through the local runtime services. |
| Chinese Metaphysics | `jieqi_year` | local Java + Python | Included | Uses local backend plus bundled ephemeris data. |
| Chinese Metaphysics | `nongli_time` | local Java + Python | Included | Uses local backend plus bundled calendar logic. |
| Chinese Metaphysics | `gua_desc` | local Java + Python | Included | Runs through the local runtime services. |
| Chinese Metaphysics | `gua_meiyi` | local Java + Python | Included | Runs through the local runtime services. |
| Chinese Metaphysics | `qimen` | local Python ken (kinqimen) + Node formatter | Included | Computed by the `kinqimen` ken engine on the chart service (`/qimen/pan`); `horosa-core-js` reformats the ken response into 星阙 aiExport.js sections. |
| Chinese Metaphysics | `taiyi` | local Python ken (kintaiyi) + Node formatter | Included | Computed by the `kintaiyi` ken engine (`/taiyi/pan`); reformatted by `horosa-core-js`. |
| Chinese Metaphysics | `jinkou` | local Python ken (kinjinkou) + Node formatter | Included | Computed by the `kinjinkou` ken engine (`/jinkou/pan`); reformatted by `horosa-core-js`. |
| Chinese Metaphysics | `sanshiunited` | local Python ken + Java + Node | Included | 三式合一 composes the ken 奇门 + 太乙 with the 大六壬 leg. |
| Chinese Metaphysics | `tongshefa` | local Node headless JS | Included | Pure headless 统摄法 engine in `horosa-core-js` (no ken backend); aligned with 星阙 `TongSheFaMain.js` — hexagram element from the 京房本宫 palace; aiExport contract 本卦/六爻/潜藏/亲和. |
| Chinese Metaphysics (数算) | `canping` | local Node headless JS + lunar-javascript | Included | 邵子参评数 / 金锁银匙. Pure in-process: pillars from the vendored bazi chain (`src/vendor/bazi/` → `lunar-javascript`), then 金锁银匙 起数 + 条文 (`src/vendor/canping/`). Aligned with 星阙 `CanPingMain.js`/`canpingLocal.js`; aiExport contract 起盘/本命/大运 (full 流年 table in `data.canping.series`). |
| Chinese Metaphysics (数算) | `heluo` | local Node headless JS + lunar-javascript | Included | 河洛理数. In-process: pillars → 天地数 → 先天/后天卦与元堂 → 命运篇 + 大限·岁运 (`src/vendor/heluo/`); 命运篇 uses real 节气 via `lunar-javascript`. Aligned with 星阙 `HeLuoMain.js`/`heluoLocal.js`; aiExport contract 起命/先天卦/后天卦/命运篇/大限. |
| Western (chart-extra) | `harmonic` | local Python chart-extra + Node summary | Included | 调波盘. Backend computation (`/astroextra/harmonic` on the chart service): 本命黄经×调波数 → 调波位置 + 同频(合相). 星阙 has no aiExport contract for 调波盘 (UI/lab-only); the skill returns structured `positions`/`conjunctions`/`chart` + a readable snapshot. |
| Chinese Metaphysics | `fengshui` | n/a | Excluded | Explicitly excluded from this shipping scope. |

## Runtime Layers

- Local Java aggregation layer: `astrostudyboot.jar`
- Local Python calculation layer: `astropy`, `flatlib`, Swiss Ephemeris files, embedded Python deps
- Local Python ken layer: `kinqimen` / `kintaiyi` / `kinjinkou` mounted on the chart service (`/qimen/pan`, `/taiyi/pan`, `/jinkou/pan`)
- Local JS layer: `horosa-core-js` (统摄法 + 数算 canping/heluo engines + ken-response → aiExport.js formatting) executed via bundled Node runtime. The 数算 tools compute four pillars in-process via the vendored bazi chain (`src/vendor/bazi/`), which depends on the bundled `lunar-javascript` npm package (`horosa-core-js/node_modules/lunar-javascript`, shipped in the runtime payload).

## Acceptance Notes

- `qimen`, `taiyi`, `jinkou`, and `sanshiunited` have been verified end-to-end against the ken chart service on macOS (the skill produces the same charts as 星阙, with clean aiExport.js export contracts).
- The macOS and Windows runtime archives are both generated by the release build scripts.
- Windows archive verification is currently structural in this repository environment; native Windows process validation must be done on a Windows machine.
