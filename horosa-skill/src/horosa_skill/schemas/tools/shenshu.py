"""神数族输入：十四种神数的公共输入，以及策天 / 七政神数 / 皇极经世的专属开关。"""
from __future__ import annotations

from pydantic import Field

from horosa_skill.schemas.tools.base import FlexibleModel


class ShenShuInput(FlexibleModel):
    # 神数 family (wangji 皇极经世 / wuzhao 五兆 / taixuan 太玄筮法 / jingjue 荆诀 / shenyishu 神易数 + 9 kinastro):
    # ganzhi-based, so date (+ time) + the 晚子时 switches drive the cast; kinastro 族另读 gender/zone（四柱按时区
    # 定气/立春界）。`options` = 技法旋钮，**逐技法键表**在 shenshu_options.SHENSHU_OPTION_KNOBS（类型校验；
    # horosa_agent_guidance(tool_name=…).options_keys 可查）；认不出的键不转发、回执 data.params_ignored。
    # 不在 tools/list 写键表：14 个工具共享本模型，逐工具描述会把广告层撑爆（预算见 verify_mcp_list_budget）。
    date: str
    # v0.36.0：神数五支的性别/地点此前未声明——`_run_shenshu_tool` 原样转发，CLI 有效而 MCP 扁平面静默丢弃
    # （PR #17 同型）。gender 五支皆用；zone/lat/lon（或 gpsLat/gpsLon）xianqin/qizhengkin/cetian 起盘需要。
    gender: int | str | None = None
    zone: str | None = None
    lat: str | None = None
    lon: str | None = None
    gpsLat: float | None = None
    gpsLon: float | None = None
    time: str | None = "00:00:00"
    after23NewDay: int | None = 1
    lateZiHourUseNextDay: int | None = 1
    options: dict | None = None


class CetianInput(ShenShuInput):
    # 策天飞星（v0.33.0 批 I-5）：+判词库原文（/cetian/texts，13 篇古籍判词）。
    textKey: str | None = Field(
        default=None,
        description="判词原文：list=目录 | all=全库（约 9 千字）| zhaodan/taiyuan/wuxing/qili/feixing/liming/yunxian/shengsi/keying/xianglun/jinjing/shenming/ruyuan 单篇。给了才产 [判词原文] 段。",
    )
    # v0.36.0：神数五支的性别/地点此前未声明——`_run_shenshu_tool` 原样转发，CLI 有效而 MCP 扁平面静默丢弃
    # （PR #17 同型）。gender 五支皆用；zone/lat/lon（或 gpsLat/gpsLon）xianqin/qizhengkin/cetian 起盘需要。
    gender: int | str | None = None
    zone: str | None = None
    lat: str | None = None
    lon: str | None = None
    gpsLat: float | None = None
    gpsLon: float | None = None
    # 地点显示名（sync311 F16）：上游 kinastro 挂载恒带 fields.pos（kinAstroFieldsSync.js:81），策天 [起盘]
    # 「地点」行只认它（webcetiansrv.py:398，缺名不出该行）；此前扁平面未声明 → 静默丢弃。
    pos: str | None = None


class QizhengKinInput(ShenShuInput):
    # 七政四余·张果星宗：地点显示名进 [起盘]（webqizhengkinsrv.py:484；缺名后端落占位「星阙地点」）。
    pos: str | None = None


class WangjiInput(ShenShuInput):
    # 皇极经世（v0.33.0 批 I-5）：+心易三法独立起卦（/wangji/xinyi；时刻法已内嵌于盘面 [心易发微]）。
    # sync311 F15：所选之法的卦面进 [心易发微]（上游 HuangJiMain.buildSnapshotText），缺省 datetime（上游挂载缺省）。
    xinyiMethod: str | None = Field(
        default=None,
        description="心易起卦法：datetime（缺省）/number/direction/character/none。结果进 [心易发微]。",
    )
    upperNum: int | None = Field(default=None, description="报数法上卦数")
    lowerNum: int | None = Field(default=None, description="报数法下卦数")
    objectGua: str | None = Field(default=None, description="方位法物象卦（缺省離，简繁皆可）")
    xinyiDirection: str | None = Field(default=None, description="方位法方位（缺省南，简繁皆可）")
    xinyiHour: int | None = Field(default=None, description="方位法时辰 0-23（缺省盘面时辰）")
    upperStrokes: int | None = Field(default=None, description="字画法上字笔画数")
    lowerStrokes: int | None = Field(default=None, description="字画法下字笔画数")
