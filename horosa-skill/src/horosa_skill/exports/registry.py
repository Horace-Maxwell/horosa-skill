from __future__ import annotations

from copy import deepcopy
from typing import Any

AI_EXPORT_SETTINGS_KEY = "horosa.ai.export.settings.v1"
# v10: 星运族 22 键补 当前时点/方法说明 公共段；六壬补 七政（日月五星临支合参）段。
# v9: tarot 段结构对齐引擎直出（牌阵综览/逐牌详解/综合断语/定局/生命牌），relative 补关系量化
# 三段，qimen 补全局速览，horary 补专题深化·X，cetian 补今制 4 宫识别 → preset 内容变更须升版。
# v11 (v0.23.0): 5 个上游 v3.5.0 新技法入册（xiaoliuren/feigong/xiaochengtu/guice/zhengchuan）；
#   geomancy 升 v3.5.1 地占大改版段表、primarydirect 段名对齐 v48、sixyao [断卦结构] 富化。
# v8: 新技法 yizhangjing/acg/astrodata 入册，heluo/canping 补全生涯流年与断验段，fengshui 扩十三派。
# v7: sanshiunited 追加三独立技法富化段、mundane 追加子盘群段。
AI_EXPORT_SETTINGS_VERSION = 11
AI_EXPORT_SECTION_MIGRATION_VERSION = 11
# 镜像基线（机读）：vendored aiExport.js 的版本，也就是本注册表**对账所依据**的上游版本。
#
# ⚠️ 语义澄清（v0.23.0 的教训）：这个数字表示「对到了哪一版」，**不**表示「该版的段全都有了」。
# 段级欠账由 contracts/export_section_debt.json 逐键量化并棘轮化（只减不增），由
# scripts/verify_export_section_baseline.py 强制。v0.23.0 曾以键级对齐宣称「整版对齐 v48」，
# 实际欠 180 段——两个数字必须一起读：版本号说对账基准，欠账文件说还差多少。
# v0.23.0（2026-07）：全面重同步至上游 v3.5.1（aiExport v48），逐技法对齐（geomancy/primarydirect/
# 5 新技法段表逐字镜像；skill-extra 段如 起卦信息、UI-only 死段、收缩契约走 verify_export_contract_mirror.py
# 的 DIVERGENCE 白名单）。守卫：vendored aiExport 的 AI_EXPORT_SETTINGS_VERSION 必须 == 本常量（版本锁步）。
MIRRORED_UPSTREAM_AIEXPORT_VERSION = 50
AI_EXPORT_SECTION_MIGRATION_KEYS = [
    "liureng", "qimen", "sanshiunited", "mundane",
    "yizhangjing", "acg", "astrodata", "heluo", "canping", "fengshui",
    "geomancy", "xiaoliuren", "feigong", "xiaochengtu", "guice", "zhengchuan",
    "tarot", "relative", "horary", "cetian",
    # v10 星运族公共段升版键
    "primarydirect", "zodialrelease", "firdaria", "profection", "solararc", "solarreturn",
    "lunarreturn", "givenyear", "decennials", "agepoint", "distributions", "jaynesprog",
    "vedicprog", "planetaryarc", "planetaryages", "balbillus", "yearsystem129", "persiandirected",
    "triplicityrulers", "keypoints", "lunationphase", "extrareturns",
]
MODULE_SNAPSHOT_PREFIX = "horosa.ai.snapshot.module.v1."
AI_EXPORT_PLANET_INFO_DEFAULT = {"showHouse": 1, "showRuler": 1}
AI_EXPORT_ASTRO_MEANING_DEFAULT = {"enabled": 0}

AI_EXPORT_PLANET_INFO_TECHNIQUES = {
    "astrochart",
    "indiachart",
    "astrochart_like",
    "relative",
    "primarydirect",
    "primarydirchart",
    "zodialrelease",
    "firdaria",
    "profection",
    "solararc",
    "solarreturn",
    "lunarreturn",
    "givenyear",
    "decennials",
    "jieqi",
    "jieqi_meta",
    "jieqi_chunfen",
    "jieqi_xiazhi",
    "jieqi_qiufen",
    "jieqi_dongzhi",
    "sanshiunited",
    "guolao",
    "germany",
}

AI_EXPORT_ASTRO_MEANING_TECHNIQUES = {
    *AI_EXPORT_PLANET_INFO_TECHNIQUES,
    "otherbu",
    "qimen",
    "liureng",
}

AI_EXPORT_HOVER_MEANING_TECHNIQUES = {"qimen", "liureng", "sanshiunited"}

JIEQI_SETTING_PRESETS = {
    "jieqi_meta": ["节气盘参数"],
    "jieqi_chunfen": ["春分星盘", "春分宿盘"],
    "jieqi_xiazhi": ["夏至星盘", "夏至宿盘"],
    "jieqi_qiufen": ["秋分星盘", "秋分宿盘"],
    "jieqi_dongzhi": ["冬至星盘", "冬至宿盘"],
}

AI_EXPORT_TECHNIQUES = [
    {"key": "astrochart", "label": "星盘"},
    {"key": "indiachart", "label": "印度律盘"},
    {"key": "astrochart_like", "label": "希腊/星体地图"},
    {"key": "hellenastro", "label": "希腊占星盘"},
    {"key": "harmonic", "label": "调波盘"},
    {"key": "dwadasamsa", "label": "十二分盘"},
    {"key": "draconic", "label": "龙盘"},
    {"key": "relocation", "label": "重置盘"},
    {"key": "relative", "label": "关系盘"},
    {"key": "primarydirect", "label": "推运盘-主/界限法"},
    {"key": "primarydirchart", "label": "推运盘-主限法盘"},
    {"key": "zodialrelease", "label": "推运盘-黄道星释"},
    {"key": "firdaria", "label": "推运盘-法达星限"},
    {"key": "profection", "label": "推运盘-小限法"},
    {"key": "solararc", "label": "推运盘-太阳弧"},
    {"key": "solarreturn", "label": "推运盘-太阳返照"},
    {"key": "lunarreturn", "label": "推运盘-月亮返照"},
    {"key": "givenyear", "label": "推运盘-流年法"},
    {"key": "decennials", "label": "推运盘-十年大运"},
    {"key": "bazi", "label": "八字"},
    {"key": "ziwei", "label": "紫微斗数"},
    {"key": "suzhan", "label": "宿占"},
    {"key": "sixyao", "label": "易卦"},
    {"key": "tongshefa", "label": "统摄法"},
    {"key": "liureng", "label": "六壬"},
    {"key": "jinkou", "label": "金口诀"},
    {"key": "qimen", "label": "奇门遁甲"},
    {"key": "sanshiunited", "label": "三式合一"},
    {"key": "taiyi", "label": "太乙"},
    {"key": "guolao", "label": "七政四余"},
    {"key": "germany", "label": "量化盘"},
    {"key": "agepoint", "label": "星运-年龄推进点"},
    {"key": "distributions", "label": "星运-界推运"},
    {"key": "jaynesprog", "label": "星运-赤纬推运"},
    {"key": "vedicprog", "label": "星运-恒星推运"},
    {"key": "planetaryarc", "label": "星运-行星弧"},
    {"key": "planetaryages", "label": "星运-行星年龄"},
    {"key": "balbillus", "label": "星运-Balbillus"},
    {"key": "yearsystem129", "label": "星运-129年系统"},
    {"key": "persiandirected", "label": "星运-波斯向运"},
    {"key": "triplicityrulers", "label": "星运-三分主星"},
    {"key": "keypoints", "label": "星运-数字相位"},
    {"key": "lunationphase", "label": "星运-月相"},
    {"key": "extrareturns", "label": "星运-多重回归"},
    {"key": "horary", "label": "卜卦盘"},
    {"key": "election", "label": "择日盘"},
    {"key": "wangji", "label": "皇极经世"},
    {"key": "wuzhao", "label": "五兆"},
    {"key": "taixuan", "label": "太玄"},
    {"key": "jingjue", "label": "京氏易"},
    {"key": "shenyishu", "label": "神乙数"},
    {"key": "shaozi", "label": "邵子神数"},
    {"key": "tieban", "label": "铁板神数"},
    {"key": "fendjing", "label": "分经神数"},
    {"key": "beiji", "label": "北极神数"},
    {"key": "nanji", "label": "南极神数"},
    {"key": "chunzi", "label": "淳子神数"},
    {"key": "xianqin", "label": "演禽"},
    {"key": "cetian", "label": "策天飞星"},
    {"key": "qizhengkin", "label": "七政四余·张果"},
    {"key": "mundane", "label": "世俗盘"},
    {"key": "jieqi", "label": "节气盘"},
    {"key": "calendar", "label": "黄历"},
    {"key": "jieqi_meta", "label": "节气盘-通用参数"},
    {"key": "jieqi_chunfen", "label": "节气盘-春分"},
    {"key": "jieqi_xiazhi", "label": "节气盘-夏至"},
    {"key": "jieqi_qiufen", "label": "节气盘-秋分"},
    {"key": "jieqi_dongzhi", "label": "节气盘-冬至"},
    {"key": "otherbu", "label": "西洋游戏"},
    {"key": "geomancy", "label": "天文地占"},
    {"key": "tarot", "label": "塔罗"},
    {"key": "fengshui", "label": "风水"},
    {"key": "canping", "label": "邵子参评数"},
    {"key": "heluo", "label": "河洛理数"},
    {"key": "yizhangjing", "label": "一掌经"},
    {"key": "xiaoliuren", "label": "小六壬"},
    {"key": "feigong", "label": "飞宫小奇门"},
    {"key": "xiaochengtu", "label": "小成图"},
    {"key": "guice", "label": "皇极轨策"},
    {"key": "zhengchuan", "label": "神数正传"},
    {"key": "acg", "label": "占星地图"},
    {"key": "astrodata", "label": "名人星盘库"},
    {"key": "generic", "label": "其他页面"},
]

AI_EXPORT_PRESET_SECTIONS = {
    "astrochart": ["起盘信息", "宫位宫头", "星与虚点", "信息", "相位", "行星", "月宿", "希腊点", "12分度", "主宰星链", "古典", "古典格局", "埃及历", "寿命格局", "可能性"],
    "indiachart": ["起盘信息", "宫位宫头", "星与虚点", "信息", "相位", "行星", "月宿", "希腊点", "古典", "可能性", "大运Dasha", "星盘信息", "Panchanga 五要素", "卡拉卡（8 Chara Karakas）", "节点主照（Rasi Drishti）", "星曜状态", "分盘吉位 Vimśopaka", "八分点 SAV", "Sodhya Pinda 凝量", "Shadbala 六力", "Ishta/Kashta 吉凶果", "Vimśopaka 分盘 20 分力", "Hora 行星时", "Choghadia 民用择时", "择时 Panchaka/Abhijit", "Mūla 大运", "Sudarśana Chakra 大运", "Naisargika 自然大运", "补充上升（Supplementary Lagnas）", "Nāḍī · Bhrigu Bindu 福点", "Nāḍī · D150 纳地盘", "Āyurdāya 寿命基础", "特殊上升 Special Lagnas", "D60 六十分盘吉凶", "分盘变体对照", "功能吉凶（Functional Nature）", "宫位力（Bhava Bala）", "星曜战（Graha Yuddha）", "扩展大运（Conditional / Chara）", "Kartari 夹击格局", "Sudarshana 三盘（命/日/月起）", "KP 宫头次主星 CSL", "KP 意义者 Significators", "KP 六级细分 / 当令星", "敌友（复合五分）", "行运 Gochara（从月·八分点）", "化解（信息·非处方）", "Jaimini Argala 干涉", "Tajika Harsha Bala", "Tajika Pancha-Vargeeya", "Tajika Mudda 年运", "行运 Gochara（从命）", "座运·X", "瑜伽格局 Yogas", "副星 Upagraha", "敏感点 Sphuta", "全吉盘 SBC", "问事 Praśna", "Nāḍī · 行星组合(同座合)", "Nāḍī · 星座交换", "Nāḍī · 木星推进时间轴", "Jaimini 三对法寿命", "Tripataki 宿距三旗", "寿命判读"],
    "astrochart_like": ["起盘信息", "宫位宫头", "星与虚点", "信息", "相位", "行星", "月宿", "希腊点", "古典", "古典格局", "埃及历", "可能性", "12分度", "主宰星链", "寿命格局"],
    # 上游把 astrochart_like 这一族按「哪个页面出的盘」再拆成独立导出键（aiExport.js 的
    # ASTRO_LIKE_EXPORT_KEYS）。段单与 astrochart_like 同构，差别只在 hellenastro 无 [古典格局]
    # ——但 skill 的希腊盘走 _CLASSICAL_ANALYSIS_TOOLS，确实产得出，故按实产登记并列为可选段。
    # 「月宿」是 skill 相对上游的既有 extra（恒星黄道盘才有），不因拆键而消失。
    "hellenastro": ["起盘信息", "宫位宫头", "星与虚点", "信息", "相位", "行星", "月宿", "希腊点", "12分度", "主宰星链", "古典", "古典格局", "埃及历", "寿命格局", "可能性"],
    # 调波盘另出两段本技法专属内容（上游该键无——上游是整页导出，调波表在页面别处），按实产登记。
    # 同族的另外三个键（上游 ASTRO_LIKE_EXPORT_KEYS）：十二分盘 /chart12、龙盘 /astroextra/draconic、
    # 重置盘 /astroextra/relocation。段单与 astrochart_like 同构（月宿是 skill 相对上游的既有 extra）。
    "dwadasamsa": ["起盘信息", "宫位宫头", "星与虚点", "信息", "相位", "行星", "月宿", "希腊点", "12分度", "主宰星链", "古典", "古典格局", "埃及历", "寿命格局", "可能性"],
    "draconic": ["起盘信息", "宫位宫头", "星与虚点", "信息", "相位", "行星", "月宿", "希腊点", "12分度", "主宰星链", "古典", "古典格局", "埃及历", "寿命格局", "可能性"],
    "relocation": ["起盘信息", "宫位宫头", "星与虚点", "信息", "相位", "行星", "月宿", "希腊点", "12分度", "主宰星链", "古典", "古典格局", "埃及历", "寿命格局", "可能性"],
    "harmonic": ["起盘信息", "宫位宫头", "星与虚点", "信息", "相位", "行星", "月宿", "希腊点", "12分度", "主宰星链", "古典", "古典格局", "埃及历", "寿命格局", "可能性", "调波位置", "同频合相"],
    "relative": ["关系起盘信息", "A对B相位", "B对A相位", "A对B中点相位", "B对A中点相位", "A对B映点", "A对B反映点", "B对A映点", "B对A反映点", "合成图盘", "影响图盘-星盘A", "影响图盘-星盘B", "关系量化", "顺畅连接", "张力连接"],
    # 上游 v48 段名对齐：主/界限法设置|表格 → 主限法设置|表格（旧名走 map_legacy_section_title）。UI-only
    # 新段「主限天球·当前动画所指」(3D 动画所指)headless 不产，故意不进 preset。
    "primarydirect": ["出生时间", "本命盘星与虚点", "主限法设置", "主限法表格", "当前时点", "方法说明"],
    "primarydirchart": ["出生时间", "本命盘星与虚点", "主限法盘设置", "主限法盘星体表格", "主限法盘相位", "主限法盘说明"],
    "zodialrelease": ["起盘信息", "本命盘星与虚点", "基于X点推运", "当前时点", "方法说明"],
    "firdaria": ["出生时间", "星盘信息", "法达星限表格", "当前时点", "方法说明"],
    "profection": ["本命盘配置", "起盘信息", "时段盘配置", "相位", "当前时点", "方法说明"],
    "solararc": ["本命盘配置", "起盘信息", "时段盘配置", "相位", "当前时点", "方法说明"],
    "solarreturn": ["本命盘配置", "起盘信息", "时段盘配置", "相位", "当前时点", "方法说明"],
    "lunarreturn": ["本命盘配置", "起盘信息", "时段盘配置", "相位", "当前时点", "方法说明"],
    "givenyear": ["本命盘配置", "起盘信息", "时段盘配置", "相位", "当前时点", "方法说明"],
    "decennials": ["起盘信息", "星盘信息", "十年大运设置", "基于X起运", "当前时点", "方法说明"],
    "bazi": ["起盘信息", "四柱与三元", "神煞（四柱与三元）", "五行力量", "格局·用神", "盲派结构", "大运", "流年行运概略"],
    "ziwei": ["起盘信息", "宫位总览", "命中格局"],
    "suzhan": ["起盘信息", "宿盘宫位与二十八宿星曜"],
    "sixyao": ["起盘信息", "卦象", "六爻与动爻", "断卦结构", "卦辞与断语", "断诀命中", "占类断语", "判语库·参考诀表"],
    "tongshefa": ["本卦", "六爻", "潜藏", "亲和"],
    "liureng": ["起盘信息", "十二盘式", "十二地盘/十二天盘/十二贵神对应", "四课", "三传", "行年", "旬日", "旺衰", "基础神煞", "干煞", "月煞", "支煞", "岁煞", "十二长生", "大格", "小局", "参考", "概览", "常用神煞", "年月神煞", "课体结构", "三传旺衰", "空亡真假", "旬空落点", "陷空", "遁干特殊", "年命上神", "毕法（已命中）", "占断向导", "七政", "取象"],
    # 上游 v50 的 32 段。此前 vendored 的 JinKouCalc/JinKouDoc 是严重截断的旧快照（1690/2850 行、
    # 226/556 行），解读层大半没搬进来，快照构建器只能出 20 段。
    "jinkou": ["起盘信息", "金口诀速览", "金口诀四位", "金口诀三盘", "四位神煞", "用神强弱", "发用·五动三动", "格局", "四位生克", "应期", "太岁月建", "地支关系", "相关神煞", "四象所属", "四象五行", "方位神煞", "合占扣题与内外", "二遁与次客", "阴盘·六亲六神旺衰", "专题起式", "贵神月将象意", "分类用神", "行年", "旬日", "旺衰", "基础神煞", "干煞", "月煞", "支煞", "岁煞", "十二长生", "数理"],
    "taiyi": ["起盘信息", "太乙盘", "太乙诸神", "风游", "主客定算", "十二神", "八门与宿曜", "断法", "七大兵法", "博弈", "命法", "命宫行限", "十六宫标记", "起盘"],
    "qimen": ["起盘信息", "盘型", "全局速览", "盘面要素", "奇门演卦", "八宫详解", "九宫方盘", "旺相休囚死·月令能量", "六害总览", "化解方案", "八门化气大阵", "用神分论", "财富七要", "事业七要", "恋爱姻缘", "孤辰寡宿", "八宫克应"],
    # 三式合一对齐独立页：在原有聚合段后，复用三独立技法富化段——太乙 pan.sections（加「太乙」前缀）、
    # 六壬断卦层 12 段（原名）、奇门派生 10 段（加「奇门」前缀）。缺段降级为简短占位仍算命中，故非 optional。
    "sanshiunited": [
        "起盘信息", "概览", "太乙", "太乙十六宫", "神煞", "大六壬", "六壬大格", "六壬小局",
        "六壬参考", "六壬概览", "八宫详解", "正北坎宫", "东北艮宫", "正东震宫", "东南巽宫",
        "正南离宫", "西南坤宫", "正西兑宫", "西北乾宫",
        "太乙主客定算", "太乙八门与宿曜", "太乙断法", "太乙七大兵法", "太乙博弈", "太乙命法", "太乙命宫行限",
        "十二盘式", "常用神煞", "年月神煞", "课体结构", "三传旺衰", "空亡真假", "旬空落点",
        "陷空", "遁干特殊", "年命上神", "毕法（已命中）", "占断向导",
        "奇门九宫方盘", "奇门旺相休囚死·月令能量", "奇门六害总览", "奇门化解方案", "奇门八门化气大阵",
        "奇门用神分论", "奇门财富七要", "奇门事业七要", "奇门恋爱姻缘", "奇门孤辰寡宿",
    ],
    "guolao": ["起盘信息", "七政四余宫位与二十八宿星曜", "神煞", "大限", "政余格局", "相位"],
    "germany": ["起盘信息", "宫位宫头", "行星", "中点", "TNP星体", "中点相位", "90°中点盘", "行星图", "映点", "中点列表", "汉堡学派要素", "组合盘", "戴维森盘", "虚星参考"],
    "agepoint": ["起盘信息", "年龄推进点（Age Point / Huber）", "当前时点", "方法说明"],
    "distributions": ["起盘信息", "界推运（分配法 / Distributions）", "当前时点", "方法说明"],
    "jaynesprog": ["赤纬推运（Declination）", "本命盘配置", "时段盘 赤纬平行/反平行", "当前时点", "方法说明"],
    "vedicprog": ["恒星推运（Vedic Sidereal）", "当前时点", "方法说明"],
    "planetaryarc": ["行星弧（Planetary Arc）", "本命盘配置", "时段盘配置", "相位", "当前时点", "方法说明"],
    "planetaryages": ["起盘信息", "行星年龄（Ages of Man）", "当前时点", "方法说明"],
    "balbillus": ["起盘信息", "Balbillus", "当前时点", "方法说明"],
    "yearsystem129": ["起盘信息", "129年系统表格", "当前时点", "方法说明"],
    "persiandirected": ["起盘信息", "波斯向运（Persian Directed）", "当前时点", "方法说明"],
    "triplicityrulers": ["起盘信息", "三分主星推运", "当前时点", "方法说明"],
    "keypoints": ["起盘信息", "数字相位推运", "当前时点", "方法说明"],
    "lunationphase": ["起盘信息", "月相推运", "当前时点", "方法说明"],
    "extrareturns": ["起盘信息", "多重回归", "当前时点", "方法说明"],
    # 上游 v50 的 19 段。此前 vendored 的 divination/ 闭包缺 27 个文件、另有 33 个内容陈旧，
    # 解读层的 9 段整体缺席（其中 2 段还需 renaissance 档口径才产）。
    "horary": ["起卦信息", "根本性", "征象星指派", "完成分析", "月亮的故事", "相位全览", "裁决", "应期方位", "描述", "专题深化·X", "古典接纳", "征象力量", "定盘考量", "Almuten", "映点对映点", "行星时", "尊贵明细", "偶然尊贵满分表", "阿拉伯点全集"],
    # 上游 v50 的 14 段。危象日参照/本命合参/时势合参 需额外入参（病始时刻 / 本命出生资料 /
    # 四张世运附加盘），当前工具尚未提供 → 列 optional，缺席不误报。
    "election": ["起盘信息", "流派口径", "总评", "红线", "分项", "尊贵强弱", "阿拉伯点", "择前考量", "用事专属", "危象日参照", "应期", "本命合参", "时势合参", "建议"],
    "wangji": ["起盘", "元会运世", "天道卦", "人事卦", "历史年表", "心易发微", "经典原文"],
    "wuzhao": ["起盘", "揲筮", "兆", "木乡", "火乡", "土乡", "金乡", "水乡", "特殊标记"],
    "taixuan": ["起盘", "玄首", "方州部家", "表", "太玄经全文"],
    "jingjue": ["起课", "卦辞", "三分", "十六卦"],
    "shenyishu": ["起盘", "干支与五行", "神卦", "五行法则", "兵占", "主客判断", "神煞", "长生", "吉凶"],
    "shaozi": ["起盘", "四柱", "四位起数", "河洛纳音", "完整结构", "64钥匙", "元会运世", "条文"],
    "tieban": ["起盘", "四柱", "算盘定部", "条文", "计算摘要", "命身刻分", "神数号码", "十二宫", "十二宫条文", "紫微安星", "条文库", "大运", "六亲佐证", "框架·流派刻制", "框架·考刻六亲", "框架·八卦滚", "框架·批断顺序", "框架·借用子系统"],
    "fendjing": ["起盘", "四柱", "两头钳", "命格", "判断", "六段断语"],
    "beiji": ["起盘", "年时", "条文索引", "完整条文", "条文检索", "家亲", "财官性情", "大运"],
    "nanji": ["起盘", "四柱", "宫部条文", "条文查询", "大运", "密码", "星图推演"],
    "chunzi": ["起盘", "四柱", "代码来源", "结构解析", "候选条文", "代码查询", "批量代码查询", "关键词检索", "多标签检索", "宿名检索", "时辰检索"],
    "xianqin": ["起盘", "三宫", "衍生星", "十二宫", "吞啖合战", "情性与格局", "二十八宿禽", "十二宫顺序", "三元起宿", "合宿表", "科名月宿", "四季得时", "情性赋全表", "二十八宿正像", "吞啖合战规则", "贵贱赋摘要", "三星·元辰", "大限", "流年小限", "神煞·待校", "演法·流派", "演法·起禽", "演法·择日", "演法·占卜", "演法·投胎"],
    # 策天飞星渲染十二宫用古制宫名（男女/奴僕/妻妾/相貌），preset 与引擎实产对齐（今制宫名 子女/交友/夫妻/父母
    # 不出现于快照，会误报 missing+unknown）。四化/飞星/格局/宫干四化表/飞化规则/古法格局规则 见 optional 说明。
    # 策天飞星宫名两制：skill 引擎产古制（男女/奴僕/妻妾/相貌），另登记今制 4 宫（夫妻/子女/交友/父母）
    # 供解析外部今制导出识别；今制 4 宫列 optional，故 skill 古制输出不误报 missing。
    "cetian": ["起盘", "农历与命身", "四化", "飞星", "格局", "命宮", "兄弟宮", "妻妾宮", "男女宮", "財帛宮", "疾厄宮", "遷移宮", "奴僕宮", "官祿宮", "田宅宮", "福德宮", "相貌宮", "夫妻宮", "子女宮", "交友宮", "父母宮", "星曜属性", "正曜副曜", "宫干四化表", "飞化规则", "古法格局规则", "三合组"],
    "qizhengkin": ["起盘", "四柱", "星曜", "十二宫", "神煞", "年限", "流时", "择日", "今制宿度", "古制宿度", "张果断语", "命宫解读"],
    # 世俗盘：入宫盘 + 子盘群（新月/满月/日月食/地区盘/行星周期 + 世俗宫义/定局/入境骨架/地理分野/
    # 地区盘推运，均由后端精算端点无头编排，缺数据降级为说明仍算命中）+ 入宫盘标准段。
    "mundane": [
        "世俗入宫", "新月图", "满月图", "日食图", "月食图", "地区盘", "行星周期",
        "世俗宫义", "定局·年主/盘主", "入境骨架", "地理分野", "地区盘推运",
        "起盘信息", "宫位宫头", "星与虚点", "信息", "相位", "行星", "希腊点",
        "12分度", "主宰星链", "古典", "埃及历", "寿命格局", "可能性",
    ],
    "jieqi": ["节气盘参数", "春分星盘", "春分宿盘", "夏至星盘", "夏至宿盘", "秋分星盘", "秋分宿盘", "冬至星盘", "冬至宿盘"],
    "calendar": ["起盘信息", "当月月历", "选中日详情", "方法说明"],
    **JIEQI_SETTING_PRESETS,
    "otherbu": ["起盘信息", "骰子结果", "骰子盘宫位与星体", "天象盘宫位与星体"],
    # 天文地占（上游 v3.5.1 地占大改版；builder 段序照 GeomancyMain.buildGeomancySnapshotText）+ 起卦信息
    # (问题/问类/上升图形)，与 skill 惯例一致。判定/入宫/十六图形每盘必出；解读技法随 technique、转宫派生随
    # turnTo、定局落星随 house_projection、边界声明随 structuralOnly 条件出 → 见 optional。图形释义为上游默认关
    # doctrine 段，skill 不产出，仅在 preset 保留作 export_parse 识别面（同 fengshui 策略）。
    "geomancy": ["起卦信息", "判定", "解读技法", "转宫派生", "定局落星·甲", "定局落星·乙", "十二宫·图形入宫", "十六图形", "图形释义", "边界声明"],
    # 塔罗：reportText 直接产出独占段头 —— 牌阵综览(牌组/牌阵/种子/设置/所问/指示牌) / 逐牌详解(逐位
    # 占象·含义·尊位) / 综合断语(花色元素合读) / 定局(Yes-No+精华牌) / 生命牌(人格·灵魂·流年，需生日)。
    # 综合断语随 summary、生命牌随 birth 条件产出 → 见 optional。
    "tarot": ["牌阵综览", "逐牌详解", "综合断语", "定局", "生命牌", "开钥", "组合读法"],
    # 风水无可调用 tool（交互 canvas/点位标注不可无头，既有排除项）；本段表仅作契约识别面 ——
    # export_parse 解析外部粘贴的风水导出文本时按十三派全段识别（理气六派 + 辅星水法/净阴净阳/
    # 玄空大卦/形势峦头/择日选择 五新派），不再对新段误报 unknown。
    "fengshui": [
        "起盘信息", "标记判定", "冲突清单", "未定位标注", "破局危害", "龙虎灶台", "移动盘",
        "吉凶评分", "缓解建议", "使用要点", "建议汇总", "纳气建议", "八卦定位", "成員卦象",
        "四类象格局", "应期成格", "改运建议", "风水·纳气盘", "风水·八卦阳宅", "风水·八宅大游年",
        "风水·玄空飞星", "风水·三合水法", "风水·金锁玉关", "风水·乾坤国宝", "风水·紫白飞星",
        "风水·辅星水法", "风水·净阴净阳", "风水·玄空大卦", "风水·形势峦头", "风水·择日选择",
    ],
    # 邵子参评数：起盘/本命/大运·歲運 + 全生涯流年表（liunianSeries 逐岁行喂入 buildSnapshotText
    # 的 liunianRows → [流年·歲運]，即星阙 aiExport 宣称的完整四段；歲運后缀段名归一见下方映射）。
    "canping": ["起盘", "本命", "大运·歲運", "流年·歲運"],
    # 河洛理数：快照段 起命/先天卦·元堂爻辞/后天卦·元堂爻辞/命运篇/大限·岁运/流年·岁运/断验（十吉）。
    # 元堂爻辞与岁运段名（含老版动态卦名段）legacy-map 到 先天卦/后天卦/大限/流年，见下方映射。
    "heluo": ["起命", "先天卦·元堂爻辞", "后天卦·元堂爻辞", "命运篇", "大限·岁运", "流年·岁运", "断验"],
    # 一掌经：十二支十二星（六道四柱四宫）+ 命宫/人事十二宫 + 格局 + 大限/小限流年十二神；
    # 重犯/交互格/职业适性/流年总论随盘面条件产出、神煞合参随开关（默认开）产出 → 见 optional。
    "yizhangjing": ["起盘信息", "四柱四宫断语", "命宫与人事十二宫", "格局判定", "重犯", "交互格", "职业适性", "大限", "小限与流年十二神", "流年总论", "神煞合参", "四世与权重", "人事十二宫寓意", "九品定格", "年上运程", "位置速断", "童限", "流月流日流时", "叠断", "诗文", "逐日值星", "时辰细断", "四柱文献"],
    # 小六壬（上游 v3.5.0）：三数起三传，6 段无条件恒出（主流六宫无五行生克，[生克] 段如实标注）→ 严格技法，空 optional。
    "xiaoliuren": ["问事", "起课", "三传", "生克", "九神", "化解"],
    # 飞宫小奇门（上游 v3.5.0）：时上起青龙飞九宫，7 段无条件恒出（缺项段内如实标注）→ 严格技法，空 optional。
    "feigong": ["问事", "起局", "干支", "命宫", "宫位", "运气", "应期"],
    # 小成图（上游 v3.5.0）：洛书九宫佈局，6 段恒出 + [股市] 仅 stock 模式出（条件段，见 optional）。
    "xiaochengtu": ["问事", "起卦", "佈局", "推导", "四象", "应期", "股市"],
    # 皇极轨策（上游 v3.5.0）：占事直断/演数/四位 恒出；起卦/卦变/断法/时方/三要十应/元会运世/大定起数
    # 随盘面·十开关·四柱条件出（时方默认关，大定需九畴数或大定流派）→ 条件段全列 optional（照 liureng 先例）。
    "guice": ["占事直断", "起卦", "演数", "四位", "卦变", "断法", "时方", "三要十应", "元会运世", "大定起数"],
    # 神数正传（上游 v3.5.0）：五流派各产 17 段之子集，唯一恒出段 = 起盘信息。preset 全 17 段、其余 16 段全列
    # optional（tieban 起数/本命条文/流年条文；shaozi 五基础数据/装卦/断本命；dading 策数/起数/死月；
    # liuqin 十二宫与六亲宫/六亲属相/妻室姓氏/玄机卦动爻/古籍未载之格；xinyi 八刻分命/条文秘数查询/性情项查询）。
    "zhengchuan": ["起盘信息", "起数", "本命条文", "流年条文", "五基础数据", "装卦", "断本命", "策数", "死月", "十二宫与六亲宫", "六亲属相", "妻室姓氏", "玄机卦动爻", "八刻分命", "条文秘数查询", "性情项查询", "古籍未载之格"],
    # 占星地图（AstroCartoGraphy）：行星地理投影线表；偕升/交点随数据条件产出 → optional。
    # 上游 locastro 是辅盘 tab：导出 = astrochart 同一套本命盘段 + 尾部地图段（aiExport.js 的
    # ASTRO_LIKE_EXPORT_KEYS 含 locastro）。偕升纬度带/线交点是本仓比上游多出的明细段。
    "acg": ["起盘信息", "宫位宫头", "星与虚点", "信息", "相位", "行星", "月宿", "希腊点", "12分度", "主宰星链", "古典", "古典格局", "埃及历", "寿命格局", "可能性", "占星地图", "偕升纬度带", "线交点"],
    # 名人星盘库（离线只读检索）：列表态出 检索条件/命中列表；单人态出 检索条件/名人详情/
    # 维基摘要/数据来源 → 两态互斥，非「检索条件」外全列 optional。
    "astrodata": ["检索条件", "命中列表", "名人详情", "维基摘要", "数据来源"],
    "generic": ["起盘信息"],
}

AI_EXPORT_FORBIDDEN_SECTIONS = {
    "liureng": ["右侧栏目"],
    "qimen": ["右侧栏目"],
    "sanshiunited": ["右侧栏目"],
}

# Sections that a preset lists (mirrored verbatim from 星阙's aiExport.js) but that the HEADLESS snapshot
# does not reliably emit — either 星阙-UI-only interactive panels (检索/查询 search boxes) or mode/data-
# conditional sections. They are still valid export targets when present, but their ABSENCE must not mark
# the export "dirty" (i.e. they are excluded from `missing_selected_sections`).
# 默认关段（上游 AI_EXPORT_DEFAULT_OFF_SECTIONS，v50）：判语库 / 象意 / 古籍全文这类 **doctrine 型**
# 段——体量大、且不是逐盘事实。上游的语义是「登记进 preset（设置面可勾、勾了就永久尊重），但用户
# 未自定义时默认不纳入导出」。
#
# 这是 preset / optional 之外的**第三态**：preset 说「这个技法有这个段」，optional 说「缺席不算漏」，
# 默认关说「除非明确要，否则不默认给」。skill 侧把它当作 optional 的超集使用——段照常登记、缺席不
# 报 missing，同时在导出契约里如实标注 default_off，供调用方决定是否请求。
AI_EXPORT_DEFAULT_OFF_SECTIONS = {
    "sixyao": ["判语库·参考诀表"],
    "taixuan": ["太玄经全文"],
    "wangji": ["经典原文", "历史年表"],   # skill 键 wangji ↔ 上游键 huangji
    "geomancy": ["图形释义"],
    "yizhangjing": ["诗文", "四柱文献", "逐日值星", "时辰细断", "叠断"],
    "qimen": ["八宫克应"],
    "liureng": ["取象"],
}

AI_EXPORT_OPTIONAL_SECTIONS = {
    # 月宿 (星阙 v2.6.4 西洋月宿)：仅恒星黄道(zodiacal=1)盘的 perchart 响应带 nakshatras，
    # 回归黄道盘不产出 → 列为可选段，避免 tropical 盘误报 missing。
    # 古典占星 (星阙 v2.6.7): [古典](逐曜状态/围攻/围绕) 仅本盘有 besiegement/古典字段时出;
    # [古典格局] 仅 /astroextra/analysis 成功(astrochart/astrochart_like)时出 → 列可选段, 优雅降级不误报 missing。
    # [埃及历] 与 [古典格局] 同源同命：都挂在 /astroextra/analysis 成功之后（天狼偕日升由后端算），
    # 该 fetch 失败即整段不出 → 同列可选段。
    "astrochart": ["月宿", "古典", "古典格局", "埃及历", "可能性"],
    "astrochart_like": ["月宿", "古典", "古典格局", "埃及历", "可能性"],
    "hellenastro": ["月宿", "古典", "古典格局", "埃及历", "可能性"],
    "dwadasamsa": ["月宿", "古典", "古典格局", "埃及历", "可能性"],
    "draconic": ["月宿", "古典", "古典格局", "埃及历", "可能性"],
    "relocation": ["月宿", "古典", "古典格局", "埃及历", "可能性"],
    "harmonic": ["月宿", "古典", "古典格局", "埃及历", "可能性"],
    "indiachart": ["月宿", "古典", "大运Dasha", "可能性", "星盘信息", "星曜战（Graha Yuddha）", "Kartari 夹击格局", "Tajika Mudda 年运", "问事 Praśna", "Nāḍī · 星座交换"],
    # 世俗盘为非推运入宫盘（predictive=0），[可能性] 依赖 predict.PlanetSign 故恒不产出 → 可选段。
    "mundane": ["古典", "埃及历", "可能性"],
    # 六壬 Phase4 (星阙 v2.5.x)：毕法（已命中）只在 refContext 成功且有命中时出；占断向导只在指定占类
    # (zhanCategory ≠ general) 时出。断卦层（年月神煞/课体结构/三传旺衰/空亡真假/旬空落点/陷空/遁干特殊/年命上神）
    # 各段按盘面数据条件产出（每盘几乎必出但非保证；如三传不空则无空亡段）→ 全列可选段，避免误报 missing。
    # 七政（日月五星临支合参）依赖随盘星历对象；chart 上下文获取失败时优雅缺段 → 可选。
    # 阴盘·六亲六神旺衰 仅 panShi='yin' 出；专题起式 仅传 topicKey/shiJianKind/birthGanZi+age 时出；
    # 数理 依赖 taixuan 非空 → 三段列可选，缺席不误报。
    "jinkou": ["阴盘·六亲六神旺衰", "专题起式", "数理"],
    "liureng": ["毕法（已命中）", "占断向导", "年月神煞", "课体结构", "三传旺衰", "空亡真假", "旬空落点", "陷空", "遁干特殊", "年命上神", "七政"],
    # 紫微 P2 (星阙 v2.6.x)：命中格局随 jar 返回的 patterns；本盘未命中所收录格局时为空 → 可选段。
    "ziwei": ["命中格局"],
    # 六爻 [断卦结构]（纳甲/世应/用神/旺衰/飞伏/六神/动变）由 core-js analyzeLiuyao 引擎派生，
    # 需 node 运行时；无 node/引擎失败则优雅降级不出该段 → 列可选段，缺失不误报。
    "sixyao": ["断卦结构", "断诀命中", "占类断语"],
    # 合盘关系量化（v3.3.1）：/astroextra/relative 打分成功才出；顺畅/张力连接随命中相位条件产出。
    "relative": ["关系量化", "顺畅连接", "张力连接"],
    # 塔罗条件段：综合断语（有 summary 才出）/定局（try 内，罕见异常才缺）/生命牌（仅传 birth 时出）。
    "tarot": ["综合断语", "定局", "生命牌", "开钥", "组合读法"],
    # 小成图条件段：[股市] 仅 qiguaFa='stock' 起卦时出（研判开收盘涨跌/幅度/K线），其余模式不出 → 缺失不误报。
    "xiaochengtu": ["股市"],
    # 皇极轨策条件段：起卦（有 steps）/卦变（有互卦）/断法（有 duan）/时方（settings.shiFang 且非梅花，默认关）/
    # 三要十应（有 ying）/元会运世（有 ctx.year+monthZhi）/大定起数（九畴数或大定流派+四柱齐）→ 随式缺席不误报。
    "guice": ["起卦", "卦变", "断法", "时方", "三要十应", "元会运世", "大定起数"],
    # 神数正传条件段：五流派各产 17 段之子集，唯一恒出段=起盘信息，其余 16 段随流派缺席不误报 missing。
    "zhengchuan": ["起数", "本命条文", "流年条文", "五基础数据", "装卦", "断本命", "策数", "死月", "十二宫与六亲宫", "六亲属相", "妻室姓氏", "玄机卦动爻", "八刻分命", "条文秘数查询", "性情项查询", "古籍未载之格"],
    # 天文地占条件段：解读技法（随后端 technique）/转宫派生（turnTo）/定局落星·甲乙（house_projection=占星法）/
    # 图形释义（上游默认关 doctrine 段，skill 不产，仅识别面）/边界声明（结构对照模式，skill 挡 ifa 故不产）。
    # 判定/十二宫·图形入宫/十六图形每盘必出、起卦信息恒出，保持严格。
    "geomancy": ["解读技法", "转宫派生", "定局落星·甲", "定局落星·乙", "图形释义", "边界声明"],
    # 一掌经条件段：重犯（有星重现才出）/交互格（日×时有断语才出）/职业适性（月柱星有断语才出）/
    # 流年总论（主星有断语才出）/神煞合参（开关开且有落宫才出）→ 缺失不误报 missing。
    "yizhangjing": ["重犯", "交互格", "职业适性", "流年总论", "神煞合参", "童限"],
    # 占星地图：偕升/交点仅在计算产出非空时入快照。
    # 盘面富化失败时这批段优雅缺席（同 astrochart 口径）；偕升纬度带/线交点按后端有无数据条件产出。
    "acg": ["月宿", "古典", "古典格局", "埃及历", "可能性", "偕升纬度带", "线交点"],
    # 名人星盘库：列表态/单人态互斥，各态专属段全列可选（检索条件恒出）。
    "astrodata": ["命中列表", "名人详情", "维基摘要", "数据来源"],
    # 卜卦专题深化（诉讼/买房/怀孕）：仅在起卦命中 3 类专题之一时产出 [专题深化·<title>]（归一为专题深化·X）。
    # 专题深化·X 仅特定 category 出；后两段仅 renaissance/medieval 档（accidentalMode=lilly /
    # lotsSet=core15）出 —— 默认 classical 档不产，属口径差异不是缺陷。
    "horary": ["专题深化·X", "偶然尊贵满分表", "阿拉伯点全集"],
    # 黄历: 选中日详情仅在请求指定 day（选中某日）时产出 → 可选段。
    "calendar": ["选中日详情"],
    # 择日: 用事专属 only when the topic rule-pack produced items; 应期 is never emitted by 星阙's builder.
    "election": ["用事专属", "应期", "危象日参照", "本命合参", "时势合参"],
    # 七政四余: 政余格局 = Moira 格局 DSL（~280 行子系统），headless 版未移植 → 可选段（如实标出）。
    "guolao": ["政余格局"],
    # 多重回归: 单段技法；某体若无返照数据则该体行不出，三体皆空时整段不出 → 列为可选段，避免误报 missing。
    "extrareturns": ["多重回归"],
    # 赤纬推运 (jaynesprog): [本命盘配置](本命星与虚点/宫位宫头) 需另取本命盘，headless 工具仅 fetch
    # /astroextra/jaynesprog（平行表）→ 不挂该段 → 列可选段，缺失不误报。
    "jaynesprog": ["本命盘配置"],
    # 量化盘 (germany): [汉堡学派要素]（流派/六宫框/差值表/医学四液/赤纬）是门控 opt-in 段——仅用户介入
    # 非默认汉堡功能（非 classic 流派/差值表/赤纬等）时附加；headless 默认 classic 零回归不产 → 列可选段。
    "germany": ["汉堡学派要素", "组合盘", "戴维森盘"],
    # 八字: 大运段仅在 direction 计算成功(起运/性别齐备)时出 → 可选；多运限·指定时段是前端「指定时间窗」
    # 功能，后端 /bazi 响应不带该数据、skill 无该输入入口 → 未接入，列可选段(如实标出，不伪造)。
    # 八字格局（五行力量/格局·用神/盲派结构）由 core-js baziGeju 引擎从 fourColumns 派生，需 node → 可选段；
    # 月令司令（分野）另需 fenYe 数据(后端未带) → 未接入，不进 preset/optional（如实不伪造）。
    "bazi": ["大运", "多运限·指定时段", "五行力量", "格局·用神", "盲派结构"],
    # 太乙 (星阙 v2.6.x): kintaiyi 后端返回的 太乙解读段（起盘信息/太乙盘/十六宫标记为 builder 恒出，
    # 进 preset）。其余按起局式/选项条件出（命法/博弈/某些式不出）→ 列为可选段，避免随式误报 missing。
    "taiyi": ["太乙诸神", "风游", "主客定算", "八门与宿曜", "十二神", "断法", "七大兵法", "博弈", "命法", "命宫行限"],
    # 神数 kinastro-* — UI search panels + mode/data-conditional sections.
    "tieban": ["算盘定部", "计算摘要", "六亲佐证"],
    "beiji": ["条文检索"],
    "chunzi": ["代码查询", "批量代码查询", "关键词检索", "多标签检索"],
    "qizhengkin": ["流时", "命宫解读"],
    # 策天飞星 顶层分析段：四化/飞星/格局/宫干四化表/飞化规则/古法格局规则。快照按「逐宫重排盘」嵌套输出，
    # 这些段头夹在各宫 re-dump 之间，段解析按首个连续块计数 → 检测不到（内容仍在导出文本内）→ 列可选段，缺失不误报。
    "cetian": ["四化", "飞星", "格局", "宫干四化表", "飞化规则", "古法格局规则", "夫妻宮", "子女宮", "交友宮", "父母宮"],
}


def normalize_planet_info_setting(raw: dict[str, Any] | None) -> dict[str, int]:
    value = raw or {}
    return {
        "showHouse": 1 if value.get("showHouse") in {1, True} else 0,
        "showRuler": 1 if value.get("showRuler") in {1, True} else 0,
    }


def normalize_astro_meaning_setting(raw: dict[str, Any] | None) -> dict[str, int]:
    value = raw or {}
    return {"enabled": 1 if value.get("enabled") in {1, True} else 0}


def normalize_section_title(title: str | None) -> str:
    text = f"{title or ''}".strip()
    if not text:
        return ""
    if text.startswith("基于") and text.endswith("推运"):
        return "基于X点推运"
    if text.startswith("基于") and text.endswith("起运"):
        return "基于X起运"
    return text


def map_legacy_section_title(key: str, title: str | None) -> str:
    normalized = normalize_section_title(title)
    if key == "horary":
        # 卜卦专题深化：诉讼/买房/怀孕 3 变体段头 [专题深化·<title>] 折叠为单占位 [专题深化·X]
        # （与 preset 两侧归一，一个纳入开关控 3 类专题）。
        if normalized.startswith("专题深化·"):
            return "专题深化·X"
    if key == "xianqin":
        # 上游 v50 把 三星 改名为 三星·元辰（元辰 = 该星的元辰位）；旧导出/旧 skill 输出仍要能解析。
        if normalized == "三星":
            return "三星·元辰"
    if key == "indiachart":
        # 座运（Rāśi daśā）有 11 个变体（Narayana/Sudasa/Drig/Kalachakra…），上游 preset 以单个占位
        # 段名 `座运·X` 登记整族（同 horary 专题深化·X 的做法），实际段头是 [座运·<变体>]。
        if normalized.startswith("座运·"):
            return "座运·X"
    if key == "primarydirect":
        # 上游 v48 段名对齐：旧名 主/界限法设置|表格 → 新 canonical 主限法设置|表格（外部旧导出/旧 skill 输出兼容）。
        if normalized == "主/界限法设置":
            return "主限法设置"
        if normalized == "主/界限法表格":
            return "主限法表格"
    # acg：本仓旧段名 行星线经度 已并入上游的单段 占星地图（口径 + 线表同段）。老用户自定义勾选里
    # 的旧名要能映射过来，否则会被当成 unknown 段静默丢弃。独立 if：下面 tongshefa 起是一条 elif 链。
    # jinkou：本仓旧版 JinKouDoc 的 JINKOU_CATEGORY_RULES 只有「求财」一条，段头被写死成
    # 分类用神·求财；重 vendor 后是上游的 13 类，段名回归 分类用神。
    # 推运族 5 键：上游 v50 的段结构是 [本命盘配置]/[起盘信息]/[时段盘配置]/[相位]，本仓旧名带
    # 「本命盘/推运盘/返照盘/流年盘」前缀。严格限定这 5 键——primarydirect / primarydirchart /
    # zodialrelease 的 preset 也含「本命盘星与虚点」，它们各有独立欠账，不能被误映射。
    if key in {"profection", "solararc", "solarreturn", "lunarreturn", "givenyear"}:
        _PREDICTIVE_LEGACY = {
            "本命盘起盘信息": "本命盘配置",
            "本命盘星与虚点": "本命盘配置",
            "推运盘起盘信息": "起盘信息",
            "返照盘起盘信息": "起盘信息",
            "流年盘起盘信息": "起盘信息",
            "推运盘星与虚点": "时段盘配置",
            "返照盘星与虚点": "时段盘配置",
            "流年盘星与虚点": "时段盘配置",
            "推运盘相位": "相位",
            "返照盘相位": "相位",
            "流年盘相位": "相位",
        }
        if title in _PREDICTIVE_LEGACY:
            return _PREDICTIVE_LEGACY[title]
    if key == "jinkou" and title == "分类用神·求财":
        return "分类用神"
    if key == "acg" and title == "行星线经度":
        return "占星地图"
    if key == "tongshefa":
        if normalized == "互潜":
            return "潜藏"
        if normalized == "错亲":
            return "亲和"
        if normalized == "统摄法起盘":
            return "本卦"
    elif key == "qimen":
        if normalized == "八宫":
            return "八宫详解"
        if normalized == "演卦":
            return "奇门演卦"
        if normalized == "九宫":
            return "九宫方盘"
        if normalized in {"右侧栏目", "概览"}:
            return "盘面要素"
    elif key == "liureng":
        if normalized.startswith("三传("):
            return "三传"
    elif key == "sanshiunited":
        if normalized == "状态":
            return "概览"
        if normalized == "八宫":
            return "八宫详解"
        if normalized == "大格":
            return "六壬大格"
        if normalized == "小局":
            return "六壬小局"
        if normalized == "参考":
            return "六壬参考"
        if normalized == "六壬格局概览":
            return "六壬概览"
    elif key == "sixyao":
        if normalized == "起卦方式":
            return "卦象"
        if normalized == "卦辞":
            return "卦辞与断语"
    elif key == "canping":
        # canonical 名 = 上游 aiExport 现在声明的、也是 canpingLocal.buildSnapshotText 实际吐出的
        # 歲運 后缀名。skill 早期把它们折叠成短名 大运/流年，方向反了——现在以上游为准，短名保留
        # 为向后兼容（旧 skill 版本导出的文本仍能解析）。
        if normalized == "大运":
            return "大运·歲運"
        if normalized == "流年":
            return "流年·歲運"
    elif key == "heluo":
        # 同上：canonical = 上游长名。老版动态卦名段 [先天·<卦> 元堂爻辞] 与 skill 早期短名一并归一。
        if normalized.startswith("先天·") or normalized == "先天卦":
            return "先天卦·元堂爻辞"
        if normalized.startswith("后天·") or normalized == "后天卦":
            return "后天卦·元堂爻辞"
        if normalized == "大限":
            return "大限·岁运"
        if normalized == "流年":
            return "流年·岁运"
    return normalized


def unique_list(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        value = f"{item or ''}".strip()
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output


def get_meaning_setting_meta(key: str) -> dict[str, str]:
    if key in AI_EXPORT_HOVER_MEANING_TECHNIQUES:
        return {
            "title": "悬浮注释（仅AI导出）：",
            "checkbox": "在对应分段输出六壬/遁甲/占星悬浮注释",
        }
    if key in AI_EXPORT_ASTRO_MEANING_TECHNIQUES:
        return {
            "title": "占星注释（仅AI导出）：",
            "checkbox": "在对应分段输出星/宫/座/相/希腊点释义",
        }
    return {"title": "", "checkbox": ""}


def get_technique_info(key: str) -> dict[str, Any] | None:
    base = next((item for item in AI_EXPORT_TECHNIQUES if item["key"] == key), None)
    if base is None:
        return None
    meaning_meta = get_meaning_setting_meta(key)
    supports_planet_info = key in AI_EXPORT_PLANET_INFO_TECHNIQUES
    supports_astro_meaning = key in AI_EXPORT_ASTRO_MEANING_TECHNIQUES
    supports_hover_meaning = key in AI_EXPORT_HOVER_MEANING_TECHNIQUES
    return {
        "key": base["key"],
        "label": base["label"],
        "preset_sections": deepcopy(AI_EXPORT_PRESET_SECTIONS.get(key, [])),
        "forbidden_sections": deepcopy(AI_EXPORT_FORBIDDEN_SECTIONS.get(key, [])),
        # 默认关段并入 optional：二者对解析器的意思相同（缺席不算漏）；default_off_sections 单列，
        # 让调用方能区分「本盘没这段」与「这段体量大、默认不给，要就明说」。
        "optional_sections": deepcopy(
            unique_list(
                list(AI_EXPORT_OPTIONAL_SECTIONS.get(key, []))
                + list(AI_EXPORT_DEFAULT_OFF_SECTIONS.get(key, []))
            )
        ),
        "default_off_sections": deepcopy(AI_EXPORT_DEFAULT_OFF_SECTIONS.get(key, [])),
        "supports_planet_info": supports_planet_info,
        "planet_info_default": deepcopy(AI_EXPORT_PLANET_INFO_DEFAULT) if supports_planet_info else None,
        "supports_astro_meaning": supports_astro_meaning,
        "supports_hover_meaning": supports_hover_meaning,
        "astro_meaning_default": deepcopy(AI_EXPORT_ASTRO_MEANING_DEFAULT) if (supports_astro_meaning or supports_hover_meaning) else None,
        "astro_meaning_title": meaning_meta["title"],
        "astro_meaning_checkbox": meaning_meta["checkbox"],
        "settings_template": {
            "sections": deepcopy(AI_EXPORT_PRESET_SECTIONS.get(key, [])),
            "planetInfo": deepcopy(AI_EXPORT_PLANET_INFO_DEFAULT) if supports_planet_info else None,
            "astroMeaning": deepcopy(AI_EXPORT_ASTRO_MEANING_DEFAULT) if (supports_astro_meaning or supports_hover_meaning) else None,
        },
    }


def build_export_registry(*, technique: str | None = None) -> dict[str, Any]:
    techniques = [get_technique_info(item["key"]) for item in AI_EXPORT_TECHNIQUES]
    techniques = [item for item in techniques if item is not None]
    selected = get_technique_info(technique) if technique else None
    return {
        "source_of_truth": "Horosa-Web/astrostudyui/src/utils/aiExport.js",
        "settings_key": AI_EXPORT_SETTINGS_KEY,
        "settings_version": AI_EXPORT_SETTINGS_VERSION,
        "section_migration_version": AI_EXPORT_SECTION_MIGRATION_VERSION,
        "section_migration_keys": deepcopy(AI_EXPORT_SECTION_MIGRATION_KEYS),
        "module_snapshot_prefix": MODULE_SNAPSHOT_PREFIX,
        "jieqi_split_keys": list(JIEQI_SETTING_PRESETS.keys()),
        "planet_info_default": deepcopy(AI_EXPORT_PLANET_INFO_DEFAULT),
        "astro_meaning_default": deepcopy(AI_EXPORT_ASTRO_MEANING_DEFAULT),
        "default_normalized_settings": {
            "version": AI_EXPORT_SETTINGS_VERSION,
            "sections": {},
            "planetInfo": {},
            "astroMeaning": {},
        },
        "techniques": techniques,
        "selected_technique": selected,
    }
