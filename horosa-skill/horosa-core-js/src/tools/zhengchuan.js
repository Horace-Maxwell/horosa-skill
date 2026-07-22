// 神数正传 formatter —— 铁板/邵子/大定/六亲/铁算心易 五流派，纯函数进程内计算。
// 四柱由 service.py 前置 /nongli/time 取权威柱后作 pillars 传入（JS 不发 HTTP，AGENTS §4）。
// 条文正文库（铁板/邵子）体积大、按需异步载入（loadTiebanVerses/loadShaoziVerses）→ runner async。
// 大定流派需 bazi 推运表（小运/大运/岁君·年粒度）：取自 vendored bazi 链，四柱仍以权威柱为准。
import { calcTieban, loadTiebanVerses } from '../vendor/zhengchuan/zhengchuanTiebanLocal.js';
import { calcShaozi, loadShaoziVerses } from '../vendor/zhengchuan/zhengchuanShaoziLocal.js';
import { calcLiuqin } from '../vendor/zhengchuan/zhengchuanLiuqinLocal.js';
import { calcXinyi } from '../vendor/zhengchuan/zhengchuanXinyiLocal.js';
import { dadingDeathYear, dadingDeathMonth } from '../vendor/zhengchuan/zhengchuanDadingLocal.js';
import { buildZhengChuanSnapshotText } from '../vendor/zhengchuan/zhengchuanSnapshot.js';
import { buildLocalBaziResult } from '../vendor/bazi/baziLunarLocal.js';

// 自 星阙 ZhengChuanMain.deriveDadingYearPillars 逐字提取（纯函数，仅读 bazi 推运表；闭包提取进 tool）：
// 取所推流年在 smallDirection（虚岁/小运/岁君）+ mainDirection（大运·按年区间）的派生值；表外/未起运返空。
function deriveDadingYearPillars(bazi, yearInput) {
  const Y = parseInt(yearInput, 10);
  if (!bazi || !Number.isFinite(Y) || Y <= 0) return {};
  const sd = Array.isArray(bazi.smallDirection) ? bazi.smallDirection : [];
  const md = Array.isArray(bazi.mainDirection) ? bazi.mainDirection : [];
  const s = sd.find((x) => Number(x.year) === Y);
  if (!s) return {};
  const d = md.filter((x) => Number.isFinite(Number(x.startYear)) && Number(x.startYear) <= Y).pop();
  const dayun = (d && `${d.ganzi || ''}`.trim()) || '';
  return {
    year: Y,
    age: Number(s.age) || undefined,
    xiaoyun: `${s.ganzi || ''}`.trim() || undefined,
    suijun: `${(s.yearGanzi && s.yearGanzi.ganzi) || ''}`.trim() || undefined,
    dayun: dayun || undefined,
    beforeQiYun: !dayun,
  };
}

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
      const b = buildLocalBaziResult({ date: input.date, time: input.time, zone: input.zone, lon: input.lon, gender, timeAlg: input.timeAlg == null ? 1 : input.timeAlg, after23NewDay: input.after23NewDay, lateZiHourUseNextDay: input.lateZiHourUseNextDay });
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
