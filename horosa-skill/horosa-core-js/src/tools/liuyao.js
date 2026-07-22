// 六爻断卦结构：喂 lines(自下而上 value/change) + nongli，跑 analyzeLiuyao 引擎，
// 输出 [断卦结构] 段（流派/卦序·世应/卦象/成局/用神·原忌仇/卦身/逐爻纳甲六神旺衰状态神煞/动变）。
// 单一真值源 = analyzeLiuyao；任一步失败回空（不连累既有 sixyao 段）。
import { analyzeLiuyao, guaFromLines } from '../vendor/gua/liuyaoFacade.js';
import { normalizeLiuyaoSettings, LIUYAO_PRESETS } from '../vendor/gua/liuyaoSchools.js';

function gz(v) {
  return `${v || ''}`.trim();
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
    const yearGz = gz(nongli.yearJieqi || nongli.yearGanZi || nongli.year);
    const monthGz = gz(nongli.monthGanZi);
    const dayGz = gz(nongli.dayGanZi);
    const ctx = {
      dayGan: dayGz.length >= 2 ? dayGz[0] : null, dayZhi: dayGz.length >= 2 ? dayGz[1] : null,
      monthGan: monthGz.length >= 2 ? monthGz[0] : null, monthZhi: monthGz.length >= 2 ? monthGz[1] : null,
      yearGan: yearGz.length >= 2 ? yearGz[0] : null, yearZhi: yearGz.length >= 2 ? yearGz[1] : null,
    };
    const moving = [];
    lines.forEach((y, i) => { if (y.change) { moving.push(i + 1); } });
    const settings = normalizeLiuyaoSettings(payload?.liuyaoSettings);
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
    return { snapshot_text: out.join('\n') };
  } catch (e) {
    return { snapshot_text: '' };
  }
}
