// 六爻断卦结构：喂 lines(自下而上 value/change) + nongli，跑 analyzeLiuyao 引擎，
// 输出 [断卦结构] 段（流派/卦序·世应/卦象/成局/用神·原忌仇/卦身/逐爻纳甲六神旺衰状态神煞/动变）。
// 单一真值源 = analyzeLiuyao；任一步失败回空（不连累既有 sixyao 段）。
import { analyzeLiuyao, guaFromLines } from '../vendor/gua/liuyaoFacade.js';
import { normalizeLiuyaoSettings, applyPreset, LIUYAO_PRESETS } from '../vendor/gua/liuyaoSchools.js';
import { YONGSHEN_CATEGORIES } from '../vendor/gua/liuyaoYongShen.js';

function gz(v) {
  return `${v || ''}`.trim();
}

// ── 六爻判读口径（liuyaoSettings）────────────────────────────────────────────────────
// 键表 = 上游 AI 挂载齿轮 SIXYAO_FIELDS 的 24 个 name 与控件类型（techniqueMountSettings.js:614-676，
// 上游 HEAD 9b74714b），逐键移植。上游 mergeLiuyaoGearSettings 就是按这张 schema 机械求白名单的；
// skill 不 vendor 那份 2798 行的 schema 文件（它 import 了半棵 UI 常量树），故只移植「键名 + 是否开关」——
// 值域与缺省仍由 vendored liuyaoSchools / 各判读引擎自己的词表决定。键表漂移由
// tests/test_sync311_divination.py 在有上游 checkout 时对拍上游源看守。
export const LIUYAO_GEAR_FIELDS = Object.freeze({
  school: 'select', askType: 'select', yongOverride: 'select', benming: 'select',
  tuChangsheng: 'select', bianyaoScope: 'select', fushen: 'select', yuepoMode: 'select',
  shishen: 'select', jinTuiTu: 'select', tianshiSchool: 'select', yearBoundary: 'select',
  guashen: 'switch', sixGods: 'switch', yuqi: 'switch', yingqi: 'switch', doctrine: 'switch',
  gufa: 'switch', yueLiushen: 'switch', guirenFa: 'select',
  shenshaOn: 'switch', shenshaBase: 'select', shenshaSet: 'multiselect', shenshaExOn: 'switch',
});
// 这六键只改上游 [断诀命中]/[占类断语] 两段的内容（liuyaoSnapshotEx.duanJueLines/zhanleiLines 读
// a.shiShen/a.shenShaEx/a.yueLiuShenAnn/a.gufa/a.tianshi/yuqiStrong）；skill 的 sixyao 快照尚不产这两段，
// 所以它们虽进判读引擎、却不改本工具的任何输出行 —— 如实回执为 unsurfaced，不装作生效。
const LIUYAO_UNSURFACED_KEYS = ['shishen', 'tianshiSchool', 'yuqi', 'gufa', 'yueLiushen', 'shenshaExOn'];
const LY_STRUCTURAL = ['shenshaOn', 'shenshaBase', 'shenshaSet', 'shenshaExOn'];
const lyBool = (v) => v === true || v === 1 || v === '1';

// 上游 mergeLiuyaoGearSettings（aiAnalysisContext.js:1684-1731）逐行同构。saved = 存档卦的
// liuyaoSettings；skill 每次现起卦、无存档层，恒传 {}。
export function mergeLiuyaoGearSettings(saved, flat) {
  const f = flat && typeof flat === 'object' ? flat : {};
  let base = saved && typeof saved === 'object' ? { ...saved } : {};
  // [Q-206/T-151] 选中的预设与存档流派不同 → 以 applyPreset(该派) 为底，其余齿轮键再叠上。
  if (f.school && f.school !== base.school && LIUYAO_PRESETS[f.school]) {
    base = applyPreset(f.school, base);
  }
  Object.keys(LIUYAO_GEAR_FIELDS).forEach((k) => {
    if (LY_STRUCTURAL.indexOf(k) >= 0 || f[k] === undefined) {
      return;
    }
    base[k] = LIUYAO_GEAR_FIELDS[k] === 'switch' ? lyBool(f[k]) : f[k];
  });
  if (f.shenshaOn !== undefined || f.shenshaBase !== undefined || f.shenshaSet !== undefined) {
    const prev = (saved && saved.shensha && typeof saved.shensha === 'object') ? saved.shensha : {};
    base.shensha = {
      ...prev,
      ...(f.shenshaOn !== undefined ? { on: lyBool(f.shenshaOn) } : {}),
      ...(f.shenshaBase !== undefined ? { base: f.shenshaBase } : {}),
      ...(f.shenshaSet !== undefined && Array.isArray(f.shenshaSet) ? { set: f.shenshaSet.slice() } : {}),
    };
  }
  if (f.shenshaExOn !== undefined) {
    base.shenshaEx = {
      ...((saved && saved.shenshaEx && typeof saved.shenshaEx === 'object') ? saved.shenshaEx : { set: null }),
      on: lyBool(f.shenshaExOn),
    };
  }
  return base;
}

// 回执：认不出的键 / 值不在 vendored 词表里的键 / 只改 skill 尚不产之段的键，三类各自如实列出。
function liuyaoSettingsReport(flat) {
  const f = flat && typeof flat === 'object' ? flat : {};
  const ignored = Object.keys(f).filter((k) => !Object.prototype.hasOwnProperty.call(LIUYAO_GEAR_FIELDS, k)).sort();
  const invalid = [];
  if (f.school !== undefined && !LIUYAO_PRESETS[f.school] && f.school !== 'custom') {
    invalid.push(`school=${f.school}`);
  }
  if (f.askType !== undefined && !YONGSHEN_CATEGORIES.some((c) => c.key === f.askType)) {
    invalid.push(`askType=${f.askType}`);
  }
  const unsurfaced = LIUYAO_UNSURFACED_KEYS.filter((k) => f[k] !== undefined);
  return { ignored, invalid, unsurfaced };
}

export function runLiuyao(payload) {
  try {
    const lines = Array.isArray(payload?.lines) ? payload.lines : [];
    if (lines.length !== 6 || !lines.every((y) => y && (y.value === 0 || y.value === 1))) {
      return { snapshot_text: '' };
    }
    const gua = guaFromLines(lines.map((y) => y.value));
    if (!gua) {
      return { snapshot_text: '' };
    }
    const nongli = payload?.nongli || {};
    const gear = payload?.liuyaoSettings && typeof payload.liuyaoSettings === 'object' ? payload.liuyaoSettings : null;
    const settings = normalizeLiuyaoSettings(gear ? mergeLiuyaoGearSettings({}, gear) : null);
    // ctx 与上游 liuyaoStructLines / liuyaoSnapshotEx.buildSnapshotAnalysis 三处同口径
    // （GuaZhanMain.js:118-144）：年界线吃 settings.yearBoundary（正月初一派取 yearGZByLunar），
    // 并补 monthNum/hourZhi/jieqiName —— 缺则月建六神/扩展神煞/八节卦气在判读层空转。
    const yearGz = gz((settings.yearBoundary === 'lunar'
      ? (nongli.yearGZByLunar || nongli.yearGanZi || nongli.yearJieqi)
      : (nongli.yearJieqi || nongli.yearGanZi || nongli.yearGZByLunar)) || nongli.year);
    const monthGz = gz(nongli.monthGanZi);
    const dayGz = gz(nongli.dayGanZi);
    const hourGz = gz(nongli.timeGanZi || nongli.hourGanZi);
    const ctx = {
      dayGan: dayGz.length >= 2 ? dayGz[0] : null, dayZhi: dayGz.length >= 2 ? dayGz[1] : null,
      monthGan: monthGz.length >= 2 ? monthGz[0] : null, monthZhi: monthGz.length >= 2 ? monthGz[1] : null,
      monthNum: (['寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥', '子', '丑'].indexOf(monthGz.length >= 2 ? monthGz[1] : '') + 1) || null,
      yearGan: yearGz.length >= 2 ? yearGz[0] : null, yearZhi: yearGz.length >= 2 ? yearGz[1] : null,
      hourZhi: hourGz.length >= 2 ? hourGz[1] : null,
      jieqiName: gz(nongli.jieqi || nongli.jieqiName) || null,
    };
    const moving = [];
    lines.forEach((y, i) => { if (y.change) { moving.push(i + 1); } });
    const a = analyzeLiuyao(gua, moving, ctx, settings);
    if (!a) {
      return { snapshot_text: '' };
    }
    const out = [];
    const presetLabel = (LIUYAO_PRESETS[settings.school] && LIUYAO_PRESETS[settings.school].label)
      || (settings.school === 'custom' ? '自定义' : settings.school);
    out.push('[断卦结构]');
    out.push(`流派：${presetLabel}`);
    if (a.palaceType) { out.push(`卦序：${a.palaceType.palace}宫·${a.palaceType.type}(世${a.palaceType.shi}应${a.palaceType.ying})`); }
    if (a.guaXing && a.guaXing.ben) { out.push(`卦象：${a.guaXing.ben}${a.guaXing.bian ? '→' + a.guaXing.bian + '(卦变)' : ''}`); }
    if (a.heHui && a.heHui.length) { out.push(`成局：${a.heHui.map((h) => `${h.type}${h.zhis}${h.wuxing}${h.hasMoving ? '(有动)' : ''}`).join('、')}`); }
    if (a.yongShen) {
      const ys = a.yongShen;
      const loc = (l) => { if (!l || !l.candidates || !l.candidates.length) { return '不上卦'; } return l.candidates.map((c) => `${c.pos}爻`).join('/'); };
      out.push(`占测：${ys.label}　用神：${ys.yong}(${loc(ys.located.yong)})`);
      if (ys.roles) { out.push(`原神：${ys.roles.yuan}(${loc(ys.located.yuan)})　忌神：${ys.roles.ji}(${loc(ys.located.ji)})　仇神：${ys.roles.chou}(${loc(ys.located.chou)})`); }
    }
    if (a.guaShen) { out.push(`卦身：${a.guaShen.body}${a.guaShen.onChart ? '(上卦)' : '(不上卦)'}`); }
    out.push('逐爻(初→上)：六神│伏神│本爻│世应│旺衰│状态│神煞');
    a.yaos.forEach((y, i) => {
      const liu = a.liuShen && a.liuShen[i] ? a.liuShen[i].liushen : '';
      const fu = (a.fushenAll && a.fushenAll[i]) || y.fushen;
      const fuTxt = fu && fu.liuqin ? `伏${fu.liuqin}${fu.zhi}${fu.wuxing}` : '';
      const sha = a.shenSha && a.shenSha.perYao && a.shenSha.perYao[i] ? (a.shenSha.perYao[i].shensha || []).join(',') : '';
      const stat = [
        y.yuePo ? '月破' : '',
        y.xunKong ? (y.voidKind || '旬空') : '',
        y.ruMu ? '入墓' : '',
        (y.changsheng === '长生' || y.changsheng === '帝旺' || y.changsheng === '绝') ? y.changsheng : '',
      ].filter(Boolean).join(',');
      out.push(`第${y.pos}爻：${liu ? liu + ' ' : ''}${y.zhi}${y.wuxing}${y.liuqin}${y.shiYing ? '(' + y.shiYing + ')' : ''} ${y.wangShuai}${stat ? ' ' + stat : ''}${fuTxt ? ' ' + fuTxt : ''}${sha ? ' 神煞:' + sha : ''}`);
    });
    if (a.dongBian && a.dongBian.movingCount > 0) {
      out.push(`变卦：${a.dongBian.bianGua ? a.dongBian.bianGua.name : ''}${a.dongBian.guaFuYin ? '(卦伏吟)' : ''}${a.dongBian.guaFanYin ? '(卦反吟)' : ''}`);
      a.dongBian.moves.forEach((m) => {
        const tags = [
          m.jinShen ? '进神' : '', m.tuiShen ? '退神' : '', m.fanYin ? '反吟' : '', m.fuYin ? '伏吟' : '',
          m.huiTou && m.huiTou.sheng ? '回头生' : '', m.huiTou && m.huiTou.ke ? '回头克' : '',
          m.huiTou && m.huiTou.chong ? '回头冲' : '', m.huiTou && m.huiTou.he ? '回头合' : '',
          m.huaKong ? '化空' : '', m.huaPo ? '化破' : '', m.huaMu ? '化墓' : '', m.huaJue ? '化绝' : '',
        ].filter(Boolean).join('·');
        out.push(`第${m.pos}爻动：${m.ben.liuqin}${m.ben.zhi}${m.ben.wuxing} → ${m.bian.liuqin}${m.bian.zhi}${m.bian.wuxing}${tags ? ' ' + tags : ''}`);
      });
      // [Q-201/T-144] 变爻范围=盲派(作用他爻)：上游 liuyaoStructLines 在动变之后出这一行
      // （GuaZhanMain.js:188-190，行文逐字同）；缺省 traditional 不出行，字节不变。
      if (Array.isArray(a.dongBian.blindEffects) && a.dongBian.blindEffects.length) {
        out.push(`盲派作用：${a.dongBian.blindEffects.map((e) => `第${e.from}爻→第${e.to}爻(${e.toLiuqin || ''})${e.rel}`).join('、')}`);
      }
    }
    // 断诀命中（v3.5.1 六爻扩充 liuyaoDuanJue）：本盘命中的经典口诀（暗动/随官入墓/金锁玉关十例…）。
    const dj = a.duanJue;
    if (dj) {
      const hits = [];
      const arrNamed = { anDong: '暗动', chongSan: '冲散', jueSheng: '绝处逢生', heChong: '合处逢冲', chengGang: '乘刚', feiFu: '飞伏', xieQi: '泄气', suiJinFu: '随金伏' };
      Object.keys(arrNamed).forEach((k) => {
        const arr = dj[k];
        if (Array.isArray(arr) && arr.length) {
          const parts = arr
            .map((x) => `${x.liuqin || ''}${x.zhi || ''}${x.kind ? '·' + x.kind : ''}${typeof x.from === 'number' ? '(第' + x.from + '爻)' : ''}`.trim())
            .filter(Boolean);
          if (parts.length) { hits.push(`${arrNamed[k]}：${parts.join('、')}`); }
        }
      });
      const objNamed = { suiGuan: '随官入墓', zhuGui: '助鬼伤身', wuGui: '五鬼', mieMo: '灭没' };
      Object.keys(objNamed).forEach((k) => { if (dj[k]) { hits.push(`${objNamed[k]}：命中`); } });
      if (Array.isArray(dj.jinSuoShi)) {
        const on = dj.jinSuoShi.filter((x) => x && x.on).map((x) => `${x.k}(${x.note})`);
        if (on.length) { hits.push(`金锁玉关：${on.join('；')}`); }
      }
      if (hits.length) { out.push('断诀命中：'); hits.forEach((h) => out.push('  ' + h)); }
    }
    // 应期（v3.5.1 六爻扩充 liuyaoYingQi）：以用神旺衰/生克逢值定何时应事。
    if (a.yingqi && Array.isArray(a.yingqi.rules) && a.yingqi.rules.length) {
      out.push('应期：');
      a.yingqi.rules.forEach((r) => {
        out.push(`  ${r.rule}${r.targets && r.targets.length ? '→' + r.targets.join('/') : ''}${r.scope ? '(' + r.scope + ')' : ''}`);
      });
    }
    const report = liuyaoSettingsReport(gear);
    return {
      snapshot_text: out.join('\n'),
      data: {
        // 实际生效的判读口径（归一后），供 Python 如实回执；settings_* 三类回执见 liuyaoSettingsReport。
        settings: {
          school: settings.school, askType: settings.askType, yongOverride: settings.yongOverride,
          benming: settings.benming, tuChangsheng: settings.tuChangsheng, bianyaoScope: settings.bianyaoScope,
          fushen: settings.fushen, yuepoMode: settings.yuepoMode, jinTuiTu: settings.jinTuiTu,
          yearBoundary: settings.yearBoundary, guashen: settings.guashen, sixGods: settings.sixGods,
          yingqi: settings.yingqi, doctrine: settings.doctrine, guirenFa: settings.guirenFa,
          shensha: settings.shensha,
        },
        settings_ignored: report.ignored,
        settings_invalid: report.invalid,
        settings_unsurfaced: report.unsurfaced,
      },
    };
  } catch (e) {
    return { snapshot_text: '' };
  }
}
