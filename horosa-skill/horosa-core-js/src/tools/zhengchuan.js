// 神数正传 formatter —— 铁板/邵子/大定/六亲/铁算心易 五流派，纯函数进程内计算。
// 四柱由 service.py 前置 /nongli/time 取权威柱后作 pillars 传入（JS 不发 HTTP，AGENTS §4）。
// 条文正文库（铁板/邵子）体积大、按需异步载入（loadTiebanVerses/loadShaoziVerses）→ runner async。
// 大定流派需 bazi 推运表（小运/大运/岁君·年粒度）：取自 vendored bazi 链，四柱仍以权威柱为准。
import { calcTieban, loadTiebanVerses } from '../vendor/zhengchuan/zhengchuanTiebanLocal.js';
import { calcShaozi, loadShaoziVerses } from '../vendor/zhengchuan/zhengchuanShaoziLocal.js';
import { calcLiuqin } from '../vendor/zhengchuan/zhengchuanLiuqinLocal.js';
import { calcXinyi } from '../vendor/zhengchuan/zhengchuanXinyiLocal.js';
// deriveDadingYearPillars = 上游 utils/zhengchuanDadingLocal.js（[挂载自检 F-47] 页面与 AI 无头同源），vendored 直调；
// 此前本文件留着一份自 ZhengChuanMain 抽出的手抄件（第二份真值源）。
import { dadingDeathYear, dadingDeathMonth, deriveDadingYearPillars } from '../vendor/zhengchuan/zhengchuanDadingLocal.js';
import { buildZhengChuanSnapshotText } from '../vendor/zhengchuan/zhengchuanSnapshot.js';
import { buildLocalBaziResult } from '../vendor/bazi/baziLunarLocal.js';

function insufficient(normalized, reason, message) {
  return {
    tool: 'zhengchuan',
    technique: 'zhengchuan',
    input_normalized: normalized,
    data: { ok: false, reason, message: message || '' },
    snapshot_text: '',
  };
}

export async function runZhengChuan(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const school = input.school || 'tieban';
  const normalized = { school };

  // 铁算心易（心易法微·查询层）：不需生辰四柱，先于四柱检查。
  if (school === 'xinyi') {
    const model = calcXinyi({ item: input.item, sound: input.sound, ke: input.ke, gong: input.gong, xqZhi: input.xqZhi, xqYushu: input.xqYushu, gender: input.gender });
    if (!model) { return insufficient(normalized, 'xinyi_no_query', 'zhengchuan 铁算心易 needs at least one query field (item/sound/ke/gong/xqZhi/xqYushu).'); }
    const snapshot_text = buildZhengChuanSnapshotText(model);
    return { tool: 'zhengchuan', technique: 'zhengchuan', input_normalized: normalized, data: { school: 'xinyi' }, snapshot_text };
  }

  const pillars = Array.isArray(input.pillars) ? input.pillars.filter((p) => `${p}`.length >= 2) : [];
  if (pillars.length !== 4) {
    return insufficient(normalized, 'pillars_unavailable', 'zhengchuan requires four authoritative 四柱 (pillars=[年,月,日,时]).');
  }
  const gender = input.gender;
  // 性别归一：铁板/邵子引擎吃「男/女」中文，六壬吃 1/0 位。skill 入参可为 1/0/"男"/"女"/"male"/"female"。
  const isFemale = gender === 0 || gender === '女' || gender === 'female' || gender === 'Female' || gender === false;
  const genderZh = isFemale ? '女' : '男';
  const lunarMonth = input.lunarMonth;
  const lunarDay = input.lunarDay;
  const isLeapMonth = !!input.isLeapMonth;
  let model = null;
  let verses = {};
  if (school === 'tieban') {
    model = calcTieban({ yearGz: pillars[0], monthGz: pillars[1], dayGz: pillars[2], hourGz: pillars[3], gender: genderZh, lunarMonth, lunarDay, isLeapMonth, askGz: input.askGz || pillars[3] });
    verses = await loadTiebanVerses();
  } else if (school === 'shaozi') {
    model = calcShaozi({ pillars, gender: genderZh, lunarMonth, lunarDay, isLeapMonth, fatherAge: Number(input.fatherAge) || 27, motherAge: Number(input.motherAge) || 26, yuan: input.yuan || 'zhong' });
    verses = await loadShaoziVerses();
  } else if (school === 'liuqin') {
    const genderBit = isFemale ? 0 : 1;
    const askHourZhi = input.askHourZhi || pillars[3][1];
    model = calcLiuqin({
      pillars, gender: genderBit, lunarMonth, lunarDay, isLeapMonth,
      yearZhi: pillars[0][1], hourZhi: pillars[3][1],
      yangYear: '甲丙戊庚壬'.indexOf(pillars[0][0]) >= 0,
      askHourZhi,
      env: input.env || ('卯辰巳午未申'.indexOf(askHourZhi) >= 0 ? '晴' : '明'),
    });
  } else if (school === 'dading') {
    // 大定：四柱=权威柱；小运/大运/岁君（年粒度）取自 vendored bazi 链的推运表（同八字盘一源）。
    let bazi = null;
    try {
      // 🔴 gender 必须传 0/1：baziLunarLocal.js:1079 做 `Number(params.gender) === 0 ? 0 : 1`，
      // 而本文件上游收到的可能是 '女' —— Number('女') = NaN ≠ 0 → 判男 → 大运顺行方向错 →
      // deriveDadingYearPillars 取到错的 小运/岁君/大运 → 大定死限年错，且照常自信输出。
      // 本文件顶部已有 isFemale（:63）做同样的归一（genderBit 是 liuqin 分支的块内变量，此处不可见）。
      // 🔴 sync311 wave 3：推运表的时间算法必须与四柱同口径。上游页面与无头挂载都是**一次**
      // buildLocalBaziResult 同出四柱 + 农历月日 + 推运表（ZhengChuanMain.getModel:145-189 /
      // aiAnalysisContext.buildChartShusuanBazi:1948-1979），不可能两套 timeAlg；无头缺省 timeAlg =
      // record.timeAlg ?? 0（buildFieldObject:603，真太阳时）。skill 的四柱来自 /nongli/time（Python 缺省
      // 同为 0），此前这里缺省 1（钟表时）→ 真太阳时跨时辰的生辰，小运起点（时柱）与四柱时柱不是同一柱。
      const b = buildLocalBaziResult({ date: input.date, time: input.time, zone: input.zone, lon: input.lon, gender: isFemale ? 0 : 1, timeAlg: input.timeAlg == null ? 0 : input.timeAlg, after23NewDay: input.after23NewDay, lateZiHourUseNextDay: input.lateZiHourUseNextDay });
      bazi = (b && b.bazi) || b;
    } catch (e) { bazi = null; }  // 无推运表 → deriveDadingYearPillars 回落月柱（古法「未行大运」）
    const derived = deriveDadingYearPillars(bazi, input.dadingYear);
    const dInput = {
      pillars,
      dayun: input.dayun || derived.dayun || pillars[1],
      xiaoyun: input.xiaoyun || derived.xiaoyun || pillars[3],
      suijun: input.suijun || derived.suijun || pillars[0],
      age: Number(input.age) || derived.age || 40,
    };
    const year = dadingDeathYear(dInput);
    const month = year ? dadingDeathMonth(pillars[1], pillars[0][0]) : null;
    if (year) {
      model = { school: 'dading', input: dInput, year, month, derived };
      model.pillar_source_note = '四柱取后端权威柱；大定推运表（虚岁/小运/大运/岁君·年粒度）取自本地 bazi 链，与八字盘同源。';
    }
  } else {
    return insufficient(normalized, 'unknown_school', `unknown zhengchuan school: ${school} (tieban/shaozi/dading/liuqin/xinyi).`);
  }
  if (!model) {
    return insufficient(normalized, 'calc_failed', `zhengchuan ${school} 排盘失败（起数/装卦/推运未足）。`);
  }
  const snapshot_text = buildZhengChuanSnapshotText(model, verses);
  return {
    tool: 'zhengchuan',
    technique: 'zhengchuan',
    input_normalized: normalized,
    data: {
      school: model.school,
      pillars,
      pillar_source_note: model.pillar_source_note || null,
    },
    snapshot_text,
  };
}
