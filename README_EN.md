[简体中文](./README.md) | **English**

<div align="center">
  <h1>Horosa Skill</h1>
  <p><strong>Turn Xingque / Horosa into an offline metaphysics capability layer any AI can call locally.</strong></p>
  <p>Clone the repo, install the offline runtime once, and let Claude, Codex, Open WebUI, OpenClaw, etc. call <strong>106</strong> real techniques on your own machine — Western natal / predictive / horary / electional, BaZi / Zi Wei / Da Liu Ren / the Three Styles, and all <strong>14 Shen Shu</strong> systems — read the full Xingque AI-export protocol, return stable structured output, and persist every analysis as a retrievable local record. Every answer ships with a deterministic provenance card, a cited methodology knowledge base, a chart-fact faithfulness evaluator, and a multi-technique synthesis contract. Works offline, value-for-value identical to the Xingque desktop app.</p>

  <p><a href="https://github.com/Horace-Maxwell/horosa-skill"><img src="https://img.shields.io/badge/GitHub-Repository-111827?style=for-the-badge&logo=github" alt="Repository" /></a>&nbsp;<a href="https://github.com/Horace-Maxwell/horosa-skill/releases"><img src="https://img.shields.io/badge/GitHub-Releases-1d4ed8?style=for-the-badge&logo=github" alt="Releases" /></a>&nbsp;<a href="./README.md"><img src="https://img.shields.io/badge/阅读-简体中文-0f766e?style=for-the-badge" alt="Read in Chinese" /></a></p>

  <p>
    <img src="https://img.shields.io/github/stars/Horace-Maxwell/horosa-skill?style=flat-square" alt="GitHub stars" />
    <img src="https://img.shields.io/github/v/release/Horace-Maxwell/horosa-skill?display_name=tag&style=flat-square" alt="Release" />
    <img src="https://img.shields.io/badge/tools-106-1d4ed8?style=flat-square" alt="106 tools" />
    <img src="https://img.shields.io/badge/platform-macOS%20(arm64)%20%7C%20Windows%20(x64)-0f766e?style=flat-square" alt="Platforms" />
    <img src="https://img.shields.io/badge/runtime-offline%20first-111827?style=flat-square" alt="Offline runtime" />
    <img src="https://img.shields.io/badge/MCP-ready-111827?style=flat-square" alt="MCP ready" />
    <img src="https://img.shields.io/badge/knowledge-30%20domains%2C%20cited-111827?style=flat-square" alt="Cited knowledge base" />
    <img src="https://img.shields.io/badge/storage-SQLite%20%2B%20JSON-111827?style=flat-square" alt="SQLite and JSON" />
  </p>

  <p><a href="./LICENSE"><img src="https://img.shields.io/badge/License-AGPL--3.0-374151?style=flat-square" alt="License" /></a>&nbsp;<a href="./CONTRIBUTING.md"><img src="https://img.shields.io/badge/Contributing-Guide-0f766e?style=flat-square" alt="Contributing" /></a>&nbsp;<a href="./SECURITY.md"><img src="https://img.shields.io/badge/Security-Policy-991b1b?style=flat-square" alt="Security" /></a>&nbsp;<a href="./SUPPORT.md"><img src="https://img.shields.io/badge/Support-Paths-1d4ed8?style=flat-square" alt="Support" /></a>&nbsp;<a href="./CITATION.cff"><img src="https://img.shields.io/badge/Citation-CFF-7c3aed?style=flat-square" alt="Citation" /></a></p>
</div>

---

## In one sentence

Xingque already has a complete local engine, ephemeris, export settings, and a multi-technique system. **Horosa Skill does not rebuild a simplified calculator** — it packages those capabilities into a product-grade interface layer made for GitHub distribution, AI invocation, and long-term local management: the engine runs on your machine, the output is stable JSON + Xingque-style export snapshots, and every call is automatically written as a retrievable local knowledge record.

It solves six things:

- **Get it and use it** — clone from GitHub, install the full offline runtime from GitHub Releases, then run offline.
- **A real AI interface** — call genuine Xingque methods over `MCP` or a `JSON-first CLI`, not a loose prompt layer.
- **Stable & consumable** — every technique returns a uniform envelope + Xingque-style `export_snapshot` / `export_format`; neither machine nor human has to guess fields.
- **Auditable** — every response carries a technique provenance card; doctrine quotes carry sources; AI readings can be verified claim-by-claim against machine-read chart facts.
- **Manageable long-term** — one call = one traceable record (run / artifact / manifest / final AI answer).
- **Light repo** — code, docs, CLI, MCP, tests in Git; the heavy runtime in Releases.

License: the repo is published under `GNU AGPL-3.0-only` (root [LICENSE](./LICENSE)). The three bundled third-party `ken` engines are used under their own MIT licenses (see [Credits](#credits-the-bundled-open-source-ken-engines)).

## Documentation map

| Doc | Content |
| --- | --- |
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | Architecture |
| [`docs/INPUT_CONTRACTS.md`](./docs/INPUT_CONTRACTS.md) | Per-tool input contracts (required fields) |
| [`docs/DATA_CONTRACTS.md`](./docs/DATA_CONTRACTS.md) | Output / envelope / export data contracts |
| [`docs/EXPORT_AUDIT_GUIDE.md`](./docs/EXPORT_AUDIT_GUIDE.md) | Section-by-section audit method for predictive exports |
| [`docs/OPERATIONS.md`](./docs/OPERATIONS.md) · [`docs/EVALUATION.md`](./docs/EVALUATION.md) | Operations · evaluation (HorosaBench / faithfulness) |
| [`docs/OFFLINE_RUNTIME_RELEASES.md`](./docs/OFFLINE_RUNTIME_RELEASES.md) | Offline runtime packaging & release |
| [`docs/LESSONS.md`](./docs/LESSONS.md) · [`docs/GLOSSARY.md`](./docs/GLOSSARY.md) | Append-only lessons ledger · domain glossary |
| [`server.json`](./server.json) · [`skills/horosa-agent/SKILL.md`](./skills/horosa-agent/SKILL.md) · [`AGENTS.md`](./AGENTS.md) | MCP metadata · the single policy source for AI clients (with references/ sheets) · agent rules-of-record (iron laws / compute model / packaging & release law / symptom table) |

## Current stable baseline

**Current public version: `Horosa Skill 0.35.0` (106 callable tools).**

This release line brings the capability surface roughly to parity with the desktop app — and adds a trust stack no other metaphysics tool ships:

- **Trust stack (v0.27.0–v0.35.0)** — every response carries a deterministic **technique provenance card** (`data.technique_card`); `horosa_technique_report` renders methods reports and detects cross-technique setting conflicts; a **31-domain knowledge base** (408 cited entries) returns every doctrine entry with a file-and-version citation; a **chart-fact faithfulness evaluator** verifies AI readings claim-by-claim against machine-read chart truth; and **`horosa_hecan`** runs multi-technique synthesis under a divergence-disclosure contract.
- **Upstream parity (v0.28.0)** — export contract v14 mirrors the desktop app's aiExport v56 (Xingque v3.9.3): four classical-derived sections, BaZi stem/branch combination-clash lines, Zi Wei body palace + BaZi major periods, almanac sub-source labels, derived-chart dedicated sections, and the 天星择日 selected-moment chart.
- **Full Western astrology** — natal and derived charts, 10 classic return/progression/timeline tools, 3 v2.4.0 Western additions (Age Point / Distributions / mundane ingress), 7 v2.5.0 progressions (Jayne declination / Vedic sidereal / Planetary Arc / Ages of Man / Balbillus / 129-year system / Persian Directed), plus full **horary** and **electional** judgment engines.
- **Primary Direction v12, verified methods (v2.6.6)** — the directions table converges on the **5 per-row-verified methods** (Alcabitius / Meridian / Porphyry / Equal-ecliptic / Equal-hour-circle; unverified values fall back to Alcabitius inside the engine), In Zodiaco/In Mundo frames, direct+converse, **22 time keys** (incl. per-chart Simmonite/Kepler/Brahe and dynamic True/Symbolic Solar Arc), antiscia/terms as promissors, **Vertex significator rows**, and **pdYears up to 3000** with per-revolution recurrence rows; the **midpoint chart** is a Hamburg/Uranian 90° dial (8 TNP + planetary pictures / antiscia / midpoint list).
- **Sidereal zodiac & full India (v2.6.4)** — every Western technique chart supports **47 ayanāṃśa** sidereal modes (default Lahiri, tropical charts unchanged) + a **nakshatra (西洋月宿)** row; Vedic India charts go from 4→**24 house systems** and 6→**47 ayanāṃśa**.
- **Classical astrology completion (v2.6.7)** — the chart family gains **[古典] (Classical)** and **[古典格局] (Classical patterns)** sections (per-planet classical status, besiegement, doryphory, translation/collection of light, Almuten figuris, temperament, extended Arabic lots, …), derived value-for-value by vendored formulas; v0.28.0 adds the four **classical-derived** sections (derived houses / dispositor chains / almuten table / planetary-hours ruler). 
- **Chinese metaphysics core** — BaZi, Zi Wei, Da Liu Ren, Qi Men, Tai Yi, Jin Kou Jue, the Three Styles unified, Tong She Fa, He Luo Li Shu, Shao Zi Can Ping Shu, harmonic charts, Su Zhan, Liu Yao.
- **Interpretation layers (v0.10.0 / v0.11.0)** — Qi Zheng Si Yu gains **major-period + aspects + Zheng-Yu patterns** (Moira DSL), Jin Kou Jue a **20-section reading layer**, Da Liu Ren **common shen-sha + the 100 Bi-Fa rules + divination guide**, Qi Men the **Fa Qi Men overlay**, and Zi Wei **matched patterns / secondary stars / school-specific si-hua** (incl. Tian-Shang/Tian-Shi placement).
- **All 14 Shen Shu** — 5 standalone (Huang Ji Jing Shi / Wu Zhao / Tai Xuan / Jing Fang Yi / Shen Yi Shu) + 9 (Shao Zi / Tie Ban / Fen Jing / Bei Ji / Nan Ji / Chun Zi / Yan Qin / Ce Tian / Qi Zheng·Zhang Guo).
- **Same backend** — Qi Men / Tai Yi / Jin Kou Jue (and the Qi Men + Tai Yi inside the Three Styles) run on Xingque's `ken` backend (`kinqimen` / `kintaiyi` / `kinjinkou`); the 14 Shen Shu run on kentang engines mounted on the Xingque chart service; results are reformatted by the headless JS layer into `aiExport.js` sections. **The Skill and the Xingque desktop app share one backend, value-for-value identical.**

A hard protocol runs throughout: **the AI may not invent parameters**. Whenever a technique is affected by time, place, timezone, gender, topic, house system, calendar, or casting method, the agent cannot proceed until the user confirms — the tool returns a structured block with a question you can forward verbatim.

Local end-to-end signals:

| Check | Result |
| --- | --- |
| Callable tools | `106 / 106 ok=true` |
| Engineering tests | `599 / 599 pass` (offline CI shape: contract + export fixtures + node JS golden; a further 67 live integration tests need a local runtime and auto-skip when services are down) |
| Forced clarification when params unconfirmed | `84` technique tools trigger `must_ask_user=true` |
| Safe-exempt tools | `8` registry / knowledge / parser tools are directly readable |
| Xingque-style export structure | every business technique carries `export_snapshot` / `export_format` (`103` export techniques modeled; contract v14 mirrors desktop aiExport v56) |
| Technique provenance | every technique response carries `data.technique_card`; a declared-vs-measured compute mismatch is flagged explicitly |
| Knowledge base | 30 domains; 235 manual entries, each returned with a file-and-version citation |
| HorosaBench | 105 registry-locked benchmark cases + chart-fact faithfulness evaluation (wrong-chart and sycophancy adversarial cases go red) |
| Local memory / report | every technique call writes 1 local run record + 1 JSON artifact |
| Qi Men / Tai Yi / Jin Kou / Three Styles | unified on `ken`, same as the desktop app |
| Tong She Fa / Decennials | headless, value-for-value with Xingque (`decennials.test.js` golden) |
| GitHub CI | Linux unit tests + horosa-core-js JS golden self-check + Windows OpenClaw smoke (**does not cover the cross-tree upstream checks** — those need an upstream checkout and only run via `preflight_release.py` on the maintenance box) |
| Release runtime | macOS (arm64) + Windows (x64) assets (ken + 14 Shen Shu engines bundled) packaged and verified on every release; other platforms/arches fail install with an explicit unsupported error |

> About `solarreturn` / `lunarreturn` / `solararc` / `givenyear` / `profection` / `pd` / `pdchart` / `zr`: these predictive tools are verified working in this version and should not be flagged by an agent as "Java `/predict/*` unavailable". If a client still says so, check whether it is on an old runtime, bypassing MCP to hand-compute, or hasn't run `doctor` / `openclaw-check --full`.

## Capability map (106 tools)

> Every business technique returns a uniform envelope plus a Xingque-style `export_snapshot` / `export_format` and a `data.technique_card` provenance card. Tools marked ⓟ are setting-sensitive and require parameter confirmation before calling.

### Western astrology · natal & derived charts (11)

| Tool ID | Name | Notes |
| --- | --- | --- |
| `chart` ⓟ | Standard chart | Western natal chart + full AI export (Dodekatemoria / dispositor chain / hyleg lifespan / classical + classical-derived / classical patterns) |
| `chart13` ⓟ | 13-house variant | `chart13` form |
| `chart12` ⓟ | Dwadasamsa (12th-harmonic) | lon×12 mod 360, same shape as chart13 |
| `babylon` | Babylonian astrology | Aldebaran-anchored sidereal list, arithmetic calendar, bīt niṣirti, numina, microzodiac |
| `draconic` | Draconic chart | all longitudes measured from the North Node + a node-baseline dedicated section |
| `relocation` | Relocation chart | same birth moment, houses/angles recomputed for a new place + an angle-comparison section |
| `hellen_chart` ⓟ | Hellenistic chart | Hellenistic-oriented chart |
| `india_chart` ⓟ | Indian chart | Vedic chart |
| `guolao_chart` ⓟ | Seven Governors (Guolao) | Seven Governors / Guo Lao chart |
| `relative` ⓟ | Synastry / relationship | Two-person relationship, composite, relative output |
| `germany` ⓟ | Cosmobiology / midpoints | Hamburg 90° dial, 8 TNP, midpoint structures and quantitative analysis |

### Western astrology · returns / progressions / timelines (28)

| Tool ID | Name | Notes |
| --- | --- | --- |
| `solarreturn` ⓟ | Solar return | natal + return chart + aspects |
| `lunarreturn` ⓟ | Lunar return | natal + lunar return + aspects |
| `solararc` ⓟ | Solar arc | natal + directed chart + aspects |
| `givenyear` ⓟ | Given-year | natal + given-year chart + aspects |
| `profection` ⓟ | Profection | profection timeline |
| `pd` ⓟ | Primary directions | real primary-direction table |
| `pdchart` ⓟ | Primary-direction chart | readable PD chart + aspects |
| `zr` ⓟ | Zodiacal release | ZR timeline |
| `firdaria` ⓟ | Firdaria | Firdaria structure & timeline |
| `decennials` ⓟ | Decennials | decennials timeline (headless, Xingque golden) |
| `agepoint` ⓟ | Age Point / Huber | Koch-house age-point cycle (6 yrs/house) |
| `distributions` ⓟ | Distributions | Asc through the Egyptian bounds |
| `mundane` ⓟ | Mundane astrology | yearly ingress chart + sub-charts (lunations / eclipses / world chart / planetary cycles / chart validity / rulership geography) |
| `jaynesprog` ⓟ | Jayne declination | secondary progression + declination parallels |
| `vedicprog` ⓟ | Vedic sidereal progression | progressions under the sidereal zodiac |
| `planetaryarc` ⓟ | Planetary Arc | whole chart directed by arcSource's secondary arc |
| `planetaryages` ⓟ | Ages of Man | Ptolemy seven ages + current band |
| `yearsystem129` ⓟ | 129-year system | seven-planet succession, 129-year cycle |
| `persiandirected` ⓟ | Persian Directed | symbolic 1°/year direction hit-list + directed chart cast at any date |
| `balbillus` ⓟ | Balbillus 129-year | exaltation-distance reduction + recursive sub-periods (vendored JS, identical to Xingque) |
| `triplicityrulers` ⓟ | Triplicity rulers | sect light's triplicity rulers split life into stages |
| `keypoints` ⓟ | Numeric keypoints | period-numbers + release-point sign distances activate planets by year |
| `lunationphase` ⓟ | Progressed lunation phase | natal Sun-Moon elongation advanced by the secondary rate (8 phases) |
| `extrareturns` ⓟ | Multiple returns | Saturn / Jupiter / lunar-node return dates + yearly solar/lunar-return timeline |
| `acg` ⓟ | AstroCartoGraphy | planetary geographic lines (MC/IC longitudes, zenith points, parans, crossings) + click-point analysis / mundane event moments |
| `india_rectify` ⓟ | KP birth-time rectification | scan ±window around the anchor: RP / Pranapada / gandanta-boundary scored candidates |
| `planet_cycles` | Planet cycles | exact conjunction/opposition timeline for any planet pair (geo/helio/topo) |
| `astrodata` ⓟ | Celebrity chart catalog | offline celebrity birth-data search (FTS/category/Rodden, chart-ready detail) |
| `xuanshi` | Esoteric-history KB | 7900+ sourced events (original text / reading / citations), 27000+ celestial records, figure graph, dynasty & timeline views (read-only) |

### Western divination · horary / electional (5)

| Tool ID | Name | Notes |
| --- | --- | --- |
| `horary` ⓟ | Horary | radicality / significators (14 categories) / perfection / moon story / verdict / timing |
| `election` ⓟ | Electional | hard flags / 28 topic rule packs / scoring / cast moment / recommendations |
| `tianxing` ⓟ | 天星择日 omen search | scan a window for a Western-astrology omen condition tree / matched intervals + per-moment leaf verdicts + the selected-moment chart |
| `qizhengelection` ⓟ | Qizheng electional wheel | 11-body compass-mountain positions / altitudes / eclipse search / azimuth-arrival search |
| `qimenzeri` ⓟ | 奇门择日 window search | scan a window for a 奇门 condition tree / matched 时辰 + the full 17-section 奇门 chart |
| `huanglizeri` ⓟ | 黄历 almanac election | scan a date range for a 通书 condition tree (26 types) / matched days + the full 10-section almanac |
| `bazizeri` ⓟ | BaZi election | scan a window for a BaZi condition tree (26 types: ten gods by pillar, clashes/harms, nayin phases…) + the full chart |
| `taiyizeri` ⓟ | 太乙 election | scan a window for a 太乙 condition tree (24 types: the ten essences, the nine provinces…) + the full chart |
| `ziweizeri` ⓟ | Zi Wei election | scan a window for a 紫微 condition tree (28 types: patterns incl. broken ones, palace-stem sihua, origin palace…) + the full chart |
| `liurengzeri` ⓟ | 六壬 election | scan a window for a 六壬 condition tree (27 types: minor/major patterns, hidden stems, vitality…) + the full chart |
| `sanshizeri` ⓟ | Three-Styles election | conditions spanning 六壬 / 奇门 / 太乙 at once (70 types, the largest set) + the united chart |
| `qizhengzeri` | 七政 election | minute-level interval search (7-state dignities etc., 11 types; adjudicated by the backend swisseph) + the 果老 chart |
| `indiazeri` | Muhurta election | minute-level interval search (Panchanga limbs, Lagna, the 30 muhurtas, Choghadia, the five doshas — 18 types; backend-adjudicated) |

### Chinese metaphysics core · Three Styles (10)

| Tool ID | Name | Notes |
| --- | --- | --- |
| `bazi_birth` ⓟ / `bazi_direct` ⓟ / `bazi_inverse` | BaZi chart / direct reading / reverse lookup | Four Pillars + major periods + shen-sha + stem/branch combination-clash lines + strength / patterns / blind-school structures; reverse lookup = four ganzhi pillars → candidate birth moments (Java year-by-year search, no confirmation gate) |
| `ziwei_birth` ⓟ | Zi Wei Dou Shu | custom si-hua / schools / body palace / BaZi major periods / matched patterns |
| `ziwei_rules` | Zi Wei rule base | returns the full Zi Wei pattern rule base (readable without confirmation) |
| `liureng_gods` ⓟ / `liureng_runyear` ⓟ | Da Liu Ren / yearly | four lessons & three transmissions / 100 Bi-Fa rules / divination guide / runyear |
| `qimen` ⓟ | Qi Men Dun Jia | cast by ken (`kinqimen`), palace detail + Fa Qi Men overlay + gua |
| `taiyi` ⓟ | Tai Yi Shen Shu | cast by ken (`kintaiyi`), 16-palace marks |
| `jinkou` ⓟ | Jin Kou Jue | cast by ken (`kinjinkou`), 20-section reading layer |
| `sanshiunited` ⓟ | Three Styles unified | aggregates ken Qi Men + Tai Yi with Da Liu Ren (incl. all three engines' enriched sections) |

### Local metaphysics · numerology · divination (16)

| Tool ID | Name | Notes |
| --- | --- | --- |
| `tongshefa` ⓟ | Tong She Fa | gua, six lines, hidden, affinity (headless, Xingque parity) |
| `canping` ⓟ | Shao Zi Can Ping Shu | four-pillar numbers, verses (in-process, bundled `lunar-javascript`) |
| `heluo` ⓟ | He Luo Li Shu | pre/post-heaven gua, fate chapter, decade + yearly fortunes with verdict (in-process) |
| `yizhangjing` ⓟ | Yi Zhang Jing | palm-chart four palaces, life palace / twelve mansions, decade + annual cycles, shensha overlay (in-process) |
| `zhengchuan` ⓟ | Shen Shu Zheng Chuan | five schools (铁板/邵子/大定/六亲/铁算心易): four-pillar casting, verse lookup, decade + death-month (in-process) |
| `xiaoliuren` ⓟ | Xiao Liu Ren | three-number 三传 · mainstream six-palace / Daoist nine-palace + 生克 + nine spirits + remedies |
| `feigong` ⓟ | Fei Gong Xiao Qi Men | 青龙 flies the nine palaces + host/guest & life palace + eight gates/nine stars + annual/monthly + timing |
| `xiaochengtu` ⓟ | Xiao Cheng Tu | Luoshu nine-palace layout + forward/side derivation + four images + timing + stock (five casting methods) |
| `guice` ⓟ | Huang Ji Gui Ce | 12 casting methods + 演数四位 + gua-change judgment + 三要十应 + 元会运世 + 大定 |
| `harmonic` ⓟ | Harmonic chart | natal longitude × harmonic number, same-frequency conjunctions + an H-number dedicated section |
| `suzhan` ⓟ | Su Zhan | mansion-divination structure |
| `sixyao` ⓟ | Liu Yao / I Ching | hexagram, changing lines, question-oriented output |
| `geomancy` ⓟ | Astronomical geomancy | 4 mothers → 16 figures, figures into 12 houses + judge/witnesses, deterministic cast from the query moment |
| `tarot` ⓟ | Tarot | Waite 78-card deck, deterministic seeded shuffle from the query moment + spread verdict / detail / synthesis |
| `lingqi` ⓟ | 灵棋经 / Numinous Chess | Twelve pieces cast at once (4 upper / 4 middle / 4 lower) → one of 64 figures, with 三才 layer reading, oracle verse, commentator notes, verdict and poem |
| `otherbu` ⓟ | Astro dice | astrological dice + reading |

### Shen Shu (all 14)

> kentang engines mounted on the Xingque chart service; the backend emits the `snapshot` directly, with section headers matching the aiExport preset. `shaozi` / `tieban` / `cetian` / `qizhengkin` / `xianqin` also take gender (+ place).

| Tool ID | Name | Engine |
| --- | --- | --- |
| `wangji` ⓟ | Huang Ji Jing Shi · Xin Yi Fa Wei | standalone |
| `wuzhao` ⓟ | Wu Zhao | standalone |
| `taixuan` ⓟ | Tai Xuan · milfoil | standalone |
| `jingjue` ⓟ | Jing Fang Yi · Jing Jue | standalone |
| `shenyishu` ⓟ | Shen Yi Shu | standalone |
| `shaozi` ⓟ | Shao Zi Shen Shu | kinastro |
| `tieban` ⓟ | Tie Ban Shen Shu | kinastro |
| `fendjing` ⓟ | Fen Jing Shen Shu · Liang Tou Qian | kinastro |
| `beiji` ⓟ | Bei Ji Shen Shu | kinastro |
| `nanji` ⓟ | Nan Ji Shen Shu | kinastro |
| `chunzi` ⓟ | Chun Zi Shen Shu | kinastro |
| `xianqin` ⓟ | Yan Qin | kinastro |
| `cetian` ⓟ | Ce Tian Fei Xing · Zi Wei | kinastro |
| `qizhengkin` ⓟ | Seven Governors · Zhang Guo | kinastro |

### Solar terms / lunar calendar / almanac (6)

| Tool ID | Name | Notes |
| --- | --- | --- |
| `jieqi_year` ⓟ / `nongli_time` ⓟ | Year solar terms / lunar time | solar-term nodes / lunar ganzhi |
| `jieqi_birth` ⓟ | Birth solar-term window | exact term moments around a birth + the bracketing interval (same window BaZi luck-counting uses) |
| `calendar_month` ⓟ | Chinese almanac / month calendar | whole-month lunar / ganzhi / solar terms / lunations + selected-day detail (lunar / old-almanac / date-selection sub-sources) |
| `huangli` | Chinese day almanac | daily do/avoid, duty spirits, Peng Zu taboos, clash-sha & fetal-god directions, hourly luck |
| `tongshu` | Tongshu date selection | verdict across the five classical schools |

### Protocol / knowledge (6) + MCP facades (11)

| Tool ID | Name | Notes |
| --- | --- | --- |
| `gua_desc` / `gua_meiyi` | Gua meaning / Mei Yi gua | hexagram names & texts / Plum-Blossom gua |
| `export_registry` / `export_parse` | Export registry / parser | machine-readable export table / parse Xingque export text back to JSON |
| `knowledge_registry` / `knowledge_read` | Knowledge catalog / reader | list / read / full-text search (`query`) across 30 domains (hover knowledge + technique manuals), every entry cited |

Beyond the calculation tools, the MCP surface adds 11 facades (`HOROSA_MCP_COMPACT=1` exposes only this layer):

| Facade | Role |
| --- | --- |
| `horosa_dispatch` | routes natural-language intent to the right technique; the aggregation layer carries each sub-result's export contract |
| `horosa_hecan` | multi-technique synthesis: casts several techniques in parallel on one question (default 5, up to 8) and returns a synthesis template with evidence pointers and conclusion slots |
| `horosa_tool_run` | call any of the 106 tools by name + payload |
| `horosa_agent_guidance` | which fields must be asked first, which Xingque defaults may be used after the user accepts |
| `horosa_technique_report` | the deterministic "which techniques, which settings, computed by what" methods report (per run or per conversation) |
| `horosa_report_template` / `horosa_report_render` / `horosa_report_from_tool` | consulting reports: AI final text → JSON / DOCX / PDF, auto-written back to memory |
| `horosa_memory_query` / `horosa_memory_show` / `horosa_memory_record_answer` | local memory: search / replay a full record / write back the final answer |

> **Explicitly excluded:** `fengshui` (not yet headless; we don't disguise unfinished capability as shippable).

## Hard rules for agents

This is the **most important** rule when wiring into Cursor, OpenClaw, Claude, Codex, Open WebUI.

If an agent is unsure of the user's settings before calling a technique, it should first query `horosa_agent_guidance` (CLI: `uv run horosa-skill agent guidance --tool <tool> --intent "..."`) — it tells the AI which fields must be asked first and which Xingque defaults may be used once the user accepts.

Calculation tools and `horosa_dispatch` are gated: if the agent didn't confirm settings it gets `agent_guidance.required`, and must pass `agent_confirmed_settings: true` after the user confirms, or `defaults_accepted: true` after the user explicitly accepts defaults. If the response has `details.agent_recovery.prompt_to_user`, the AI client must stop and forward that question to the user — it may not bypass or self-fill.

Standard flow: ① user states a need → ② agent checks if params suffice; if not, call `horosa_agent_guidance` or ask the user → ③ user confirms time/place/topic/whether to accept defaults → ④ agent calls the real tool with `agent_confirmed_settings: true` + `clarification_notes` → ⑤ explain from `export_snapshot` / `export_format`, not from a hand calculation.

❌ Blocked (missing confirmation, place, timezone, topic):

```json
{ "date": "2026-05-18", "time": "13:14:00" }
```

✅ Correct (user confirmation + full context):

```json
{
  "agent_confirmed_settings": true,
  "clarification_notes": "User confirmed: 2026-05-18 13:14:00, America/Los_Angeles, San Francisco, topic = current work decision.",
  "date": "2026-05-18", "time": "13:14:00", "zone": "-07:00",
  "lat": "37n46", "lon": "122w25", "gpsLat": 37.7667, "gpsLon": -122.4167,
  "after23NewDay": false
}
```

When the user says "use Xingque defaults", switch to `{ "defaults_accepted": true, "clarification_notes": "User explicitly accepted Xingque defaults." }` — but the agent **must not** set `defaults_accepted: true` on the user's behalf.

> Timezone accepts both fixed offsets (`+08:00` / `-07:00`) and IANA names (`America/Los_Angeles` / `Asia/Shanghai`); Horosa Skill normalizes to a backend-stable offset using the chart's date and time.

## Trust stack: provenance · knowledge · evaluation · synthesis

The biggest risk in metaphysics output is not a miscalculation — it is the AI improvising beyond the chart. Horosa Skill turns "where did this conclusion come from" into machine contracts, enforced by deterministic code rather than model goodwill:

- **Technique provenance card** — every technique response carries `data.technique_card`: technique + school settings (incl. the late-Zi midnight switches), **declared vs. measured compute source** (`compute.matches_declaration=false` must be surfaced as "treat with caution"), section completeness, version chain. `horosa_technique_report` renders a methods report (markdown / json / docx / pdf) for one run (`run_id`) or a whole conversation (`group_id`) and detects **cross-technique setting conflicts** (two techniques on different late-Zi switches cannot corroborate each other). Disable with `HOROSA_TECHNIQUE_CARD=0`.
- **Cited knowledge base** — 31 domains = 3 in-app hover domains + 27 technique operation manuals + the 21-category bazi pithy corpus (408 entries: per-setting values and differences, school splits, algorithms and conventions), harvested from the desktop app's help panels. `knowledge_read` returns each entry with a "manual · domain · entry (file @ upstream version)" citation. Policy (in [SKILL.md](./skills/horosa-agent/SKILL.md)): doctrine quotes must carry a source; uncited readings must be labeled as general inference — the first anti-Barnum mechanism.
- **Chart-fact faithfulness evaluation** — `horosa-skill benchmark faithfulness` runs a **deterministic verifier** (no LLM judge) over an AI reading: factual claims (pillar ganzhi, planet-in-sign, Zi Wei major-star palaces and body palace, Liu Ren three transmissions, Liu Yao hexagram names and moving lines, tarot card names and orientations, …) are checked one by one against machine-read chart truth and classified **supported / invented / contradicted**. Wrong-chart answers and sycophantic echoes ("my Moon is in Scorpio, right?" when it isn't) go red. HorosaBench: 106 benchmark cases generated from the tool registry and locked to it — a new tool without a case fails.
- **Multi-technique synthesis (合参)** — `horosa_hecan` (CLI: `horosa-skill hecan`) casts several techniques in parallel on one question (same `group_id`; default 5, up to 8; `tools` may be explicit) and returns a synthesis **template**, not a verdict: per-technique conclusion slots must bind to that technique's real exported sections (responses carry evidence pointers; full text via `memory_show(run_id)`); `convergence` only when independently agreed; **`divergence` disclosed item by item — never averaged away, never one-sided**; setting conflicts (`consistency.setting_conflicts`) must be declared first.

## Output protocol: the point is "stably consumable", not just "compute"

Every tool call returns a uniform envelope:

```json
{
  "ok": true, "tool": "qimen", "version": "0.35.0",
  "input_normalized": {}, "data": {}, "summary": [],
  "warnings": [], "memory_ref": {}, "error": null
}
```

Techniques wired into the Xingque export protocol also carry `data.export_snapshot` (with `.snapshot_text` / `.sections` / `.selected_sections`), `data.export_format`, and `data.technique_card`. So: the AI doesn't guess structure from free text; repeated calls of one technique return the same contract; `horosa_dispatch`'s aggregation layer carries each sub-result's export contract; and the structure survives into the JSON artifact. Full field tables: [`docs/DATA_CONTRACTS.md`](./docs/DATA_CONTRACTS.md) and [`docs/INPUT_CONTRACTS.md`](./docs/INPUT_CONTRACTS.md).

## Data management: a full local record system

Local data defaults to `~/.horosa-skill/` (Windows: `%APPDATA%/HorosaSkill/`). Each run persists: run metadata, tool-call records, an entity index, JSON artifacts, a `run manifest`, the raw `query_text`, the user's `user_question`, the final `ai_answer_text`, and optional `ai_answer_structured`.

```bash
uv run horosa-skill memory query                 # query history by tool / entity / run_id
uv run horosa-skill memory show <run_id>          # replay one full call
echo '{"run_id":"<run_id>","user_question":"...","ai_answer":"...","ai_answer_structured":{}}' \
  | uv run horosa-skill memory answer --stdin     # write the final AI answer back to a record
```

This makes it not just a "tool layer" but a "tool layer + traceable knowledge base".

## Quick start

Prerequisites: [uv](https://docs.astral.sh/uv/) (one-liner: `curl -LsSf https://astral.sh/uv/install.sh | sh`); Python ≥3.12 is provisioned by uv; keep ~5GB disk free (runtime download ~730MB, ~2GB unpacked).

```bash
git clone https://github.com/Horace-Maxwell/horosa-skill.git
cd horosa-skill/horosa-skill
uv sync
uv run horosa-skill install      # install the offline runtime (~730MB, progress + resumable; no-op when up to date)
uv run horosa-skill doctor       # environment checkup (disk / ports / node probe; expect issues: [])
uv run horosa-skill selfcheck    # live check: cast one chart -> store -> read back
uv run horosa-skill serve        # start local MCP (default http://127.0.0.1:8765/mcp)
```

Troubleshooting install: `uv: command not found` -> install uv first (one-liner above); slow/broken network -> re-run `install` (resumes from the partial download) or set `HOROSA_RUNTIME_MIRROR=<mirror-prefix>`; low disk / busy ports -> `doctor` reports each check with a next_action; upgrade -> `uv run horosa-skill upgrade` (skips the download when already current); uninstall -> `uv run horosa-skill uninstall` (dry-run by default).

More troubleshooting: if `github.com:443` is unreachable but `api.github.com` works, download the runtime via the assets API (`curl -s https://api.github.com/repos/Horace-Maxwell/horosa-skill/releases/latest` to find your platform archive's `assets[].id`, then `curl -L -H "Accept: application/octet-stream" -o runtime.zip https://api.github.com/repos/Horace-Maxwell/horosa-skill/releases/assets/<id>`) and run `uv run horosa-skill install --archive runtime.zip`. If the Java backend (:9999) will not come up — `doctor` reports `services:java_backend_not_running` — the runtime now degrades to **chart-only** instead of locking everything: 三式 ken (qimen/taiyi/jinkou), 神数, geomancy, tarot and the western chart family keep working while nongli/bazi/ziwei/liureng and time-cast flows error until it recovers; `doctor` attaches the captured Java boot error under `java_diagnostics` and `selfcheck` falls back to a chart-side probe. A known Windows cause is proxy/VPN/security software whose WFP filters block `java.exe` loopback (JDK 17's internal pipes prefer AF_UNIX with no TCP fallback on connect — see issue #14); stopping the service is usually not enough, disable it and reboot.

For stdio clients like Claude Desktop: `uv run horosa-skill serve --transport stdio`. Context-constrained clients can set `HOROSA_MCP_COMPACT=1` to expose only the 11 facades, or `HOROSA_TOOLSETS=astro,cn` to flatten just those domains (domains astro/predict/chart/cn/shenshu/other, aliases western/chinese/all/none; unknown tokens are warned about and ignored, an empty result falls back to the full surface; any effective filter also registers `horosa_tool_run`; facades always register). The clarification gate still applies.

### Let the dispatcher pick the technique

```bash
echo '{
  "agent_confirmed_settings": true,
  "clarification_notes": "User confirmed: sample birth data, Shanghai, +08:00, Xingque defaults.",
  "query":"Analyze my current situation across Qi Men, Liu Ren, and the chart",
  "birth":{"date":"1990-01-01","time":"12:00","zone":"+08:00","lat":"31n14","lon":"121e28"},
  "save_result": true
}' | uv run horosa-skill ask --stdin
```

### Call a single tool / read cited knowledge / parse export text

```bash
echo '{"agent_confirmed_settings":true,"clarification_notes":"sample chart, Shanghai defaults","date":"1990-01-01","time":"12:00","zone":"+08:00","lat":"31n14","lon":"121e28","gpsLat":31.2333,"gpsLon":121.4667}' \
  | uv run horosa-skill tool run chart --stdin
echo '{"domain":"qimen","category":"door","key":"休门"}' | uv run horosa-skill knowledge read --stdin
echo '{"technique":"qimen","content":"[起盘信息]\n参数\n\n[八宫]\n八宫内容"}' | uv run horosa-skill export parse --stdin
uv run horosa-skill export registry
```

> If an agent calls Qi Men / Tai Yi / Liu Yao with too few params and `/nongli/time` returns `200001 param error`, have it use `horosa_agent_guidance` to ask for date / time / timezone / lat-lon and defaults first; Horosa Skill also retries Xingque-compatible date formats against the Java endpoint so a backend format error isn't mistaken for an unavailable algorithm.

## Supported AI clients

- **Claude Code** (one-command registration): `uv run horosa-skill client config --format claude-code` prints a ready-to-run `claude mcp add ...` with real absolute paths; see the [guide](./horosa-skill/examples/clients/claude-code.md)
- [Claude Desktop config example](./horosa-skill/examples/clients/claude_desktop_config.json) (or `client config --format claude-desktop` to generate one, no placeholder editing)
- **Cursor** (one-click): `uv run horosa-skill client config --format cursor` prints the official install deep link + an `mcpServers` snippet
- **VS Code** (one-click): `uv run horosa-skill client config --format vscode` prints a `vscode:mcp/install` link + the `code --add-mcp` command
- **Claude Code Plugin**: `/plugin marketplace add Horace-Maxwell/horosa-skill` → `/plugin install horosa@horosa-skill` (skill + MCP in one step; the offline runtime still needs a one-time `install` inside the plugin's `horosa-skill/` directory)
- [Codex config example](./horosa-skill/examples/clients/codex-config.toml) (or `client config --format codex`)
- [Open WebUI guide](./horosa-skill/examples/clients/openwebui-streamable-http.md)
- [OpenClaw guide](./horosa-skill/examples/clients/openclaw-mcp.md)

> `server.json` at the repo root is MCP Registry metadata — regular users never edit it; use the generator or the examples above.

For OpenClaw / mcporter, prefer the generator to avoid hand-editing JSON and paths:

```bash
cd horosa-skill
uv run horosa-skill client openclaw-setup --workspace ~/.openclaw/workspace
uv run horosa-skill client openclaw-check --workspace ~/.openclaw/workspace
```

> If `openclaw-check` passes and `horosa__...` tools appear in a real session but the agent trace still shows `clientToolCount: 0`, that's stale trajectory-stat noise — restart OpenClaw or open a new session; don't let the agent fall back to Shell / Python hand-computation.

## Credits: the bundled open-source ken engines

Qi Men Dun Jia / Tai Yi Shen Shu / Jin Kou Jue (and the Qi Men + Tai Yi inside the Three Styles) are computed by three open-source Python engines from **[kentang2017](https://github.com/kentang2017)**. Xingque wired them into its backend; Horosa Skill reuses the same compute path and ships them with the offline runtime:

- **kinqimen** (Qi Men Dun Jia) — MIT — <https://github.com/kentang2017/kinqimen>
- **kintaiyi** (Tai Yi Shen Shu) — MIT — <https://github.com/kentang2017/kintaiyi>
- **kinjinkou** (Jin Kou Jue) — MIT — <https://github.com/kentang2017/kinjinkou>

Full copyright and license text ships in `Horosa-Web/vendor/{kinqimen,kintaiyi,kinjinkou}/LICENSE` and is preserved on distribution.

**License attribution:** the three `ken` engines above are third-party MIT components (by kentang2017). Every other metaphysics implementation here — Tong She Fa, Decennials, and the `aiExport.js` formatting + headless adapters for Qi Men / Tai Yi / Jin Kou / Da Liu Ren / charts / progressions / horary / electional / Shen Shu — is **Xingque's own algorithm**, licensed under the root `GNU AGPL-3.0-only`. The traditional systems themselves (Jing Fang's eight palaces, Hellenistic decennials, etc.) are public knowledge and constitute no third-party copyright.

## Release & runtime strategy

The repo is intentionally split into three layers:

| Layer | Where | Role |
| --- | --- | --- |
| Public repo | GitHub repo | code, docs, CLI, MCP, tests, examples, packaging scripts |
| Maintainer packaging inputs | `vendor/runtime-source/` | large inputs to build the offline runtime (not in Git history) |
| End-user runtime | `~/.horosa/runtime/current` / `%LOCALAPPDATA%/Horosa/runtime/current` | the local runtime users actually execute after install |

This keeps the GitHub page clean, the Release assets complete, local execution offline, and the maintainer packaging flow independent of sibling directories. Further reading: [Offline Runtime Releases](./docs/OFFLINE_RUNTIME_RELEASES.md) · [Runtime Manifest Spec](./docs/RUNTIME_MANIFEST_SPEC.md) · [Repo Layout](./docs/REPO_LAYOUT.md).

## Repository layout

| Path | Description |
| --- | --- |
| [`horosa-skill/`](./horosa-skill) | Core Python package, CLI, MCP server, `horosa-core-js` (headless JS engines), tests, examples, release scripts |
| [`docs/`](./docs) | runtime spec, algorithm coverage, release docs, maintainer docs |
| [`vendor/`](./vendor) | local runtime packaging inputs |

## Verification checklist

After a fresh clone, to confirm "this isn't an empty shell", run this minimal set:

```bash
cd horosa-skill
uv sync
uv run horosa-skill install
uv run horosa-skill doctor                              # expect issues: []
uv run pytest -q                                        # 599 passed; live integration tests auto-skip when services are down
uv run python scripts/run_benchmark.py                  # HorosaBench: registry-locked cases + dispatch / export parity / knowledge
uv run python scripts/run_full_self_check.py --rounds 1 # all-tool call / export / persist / retrieve / dispatch
```

The full self-check covers: each tool is callable → returns a uniform envelope → business techniques carry `export_snapshot` / `export_format` + `technique_card` → export text re-parses → the run is written to memory → `memory show/query` retrieves it → report JSON/DOCX/PDF generate and register artifacts → `horosa_dispatch`'s aggregation layer keeps sub-tool export contracts → OpenClaw / mcporter see the MCP tools and complete smoke/full check.

> **When auditing predictive / Shen Shu tools, don't read only the short preview.** Their Xingque-style body usually writes the natal chart first, then the return / progressed / annual / primary-direction / Shen Shu tables; a 1200-char prefix may show only the natal chart. Open the full artifact and check each `export_format.sections`. See [`docs/EXPORT_AUDIT_GUIDE.md`](./docs/EXPORT_AUDIT_GUIDE.md).

## Is the output identical to Xingque?

"Identical to Xingque" means two things:

1. **Identical export structure** — business techniques generate a Xingque-style `export_snapshot.export_text`, parsed by `snapshot_parser` into `export_format`; the full self-check confirms no missing or unknown sections. The export contract (v14) mirrors the desktop app's aiExport v56 section-for-section.
2. **Identical compute path** — the Skill forbids agents from hand-computing charts with shell / Python / web search. Qi Men / Tai Yi / Jin Kou and the Qi Men+Tai Yi in the Three Styles are computed exclusively by the ken backend; the 14 Shen Shu by the kentang engines on the chart service; horary / electional / Balbillus by the vendored Xingque frontend engines — all same-source. The per-response `technique_card` reports the measured compute source and flags any mismatch with the declaration.

> Content fidelity was byte-checked: running Xingque's actual frontend builder on the same chart, the ages / aspects / promittors / significators are identical; only Persian Directed's hit dates differ by ≤1 day (moment's fractional-day truncation + JS↔Python float), which is astrologically negligible and documented (see [`horosa-skill/docs/v091-fidelity-spotcheck.md`](./horosa-skill/docs/v091-fidelity-spotcheck.md)). To prove a specific input matches the Xingque desktop UI field-for-field, put Xingque's golden snapshot for that input into fixtures and diff.

## FAQ / boundaries

**Why isn't the release a pure cloud build?** Because the full runtime depends on locally maintained runtime sources and platform runtimes. Keeping the repo light is a goal, but the full runtime still needs reliable local packaging inputs — hence "light repo + heavy release + explicit verification".

**Why keep stressing `export_snapshot` / `export_format`?** Because one of the project's core values is "let the AI stably consume Xingque output". Without this contract the AI can only read loose text, and retrieval / comparison / write-back / evaluation all become brittle.

**Why keep both SQLite and JSON?** SQLite handles structured indexing and queries; JSON artifacts handle long-term archival — portable, diffable, reviewable.

**Why isn't `fengshui` in the surface yet?** The current goal is the "complete, headless, offline-verifiable" surface. `fengshui` stays excluded; we don't disguise an un-headless capability as shippable.

**What's the most important quality signal?** Not badges or screenshots, but whether these five hold at once: tools really call · exports are really stable structured · every answer is really traceable to its technique and settings · results really persist and write back · benchmark / self-check / faithfulness evaluation really keep passing.
