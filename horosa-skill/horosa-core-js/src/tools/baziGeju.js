// 八字格局：喂后端 fourColumns（四柱·含 stem/stemInBranch），跑五行力量/格局用神/盲派 纯函数引擎，
// 输出 [五行力量]/[格局·用神]/[盲派结构]（+ [月令司令（分野）] 当传入 fenYe）。四柱同源后端故与 [四柱与三元] 一致。
// 任一步失败回空（不连累既有 bazi 段）。
import { computeWuxingStrength } from '../vendor/bazi/baziWuxing.js';
import { computeMangPai } from '../vendor/bazi/baziMangPai.js';
import { computeGejuYongShen } from '../vendor/bazi/baziGejuYongShen.js';

export function runBaziGeju(payload) {
  try {
    const fc = payload?.fourColumns;
    if (!fc || !fc.year || !fc.month || !fc.day || !fc.time) {
      return { snapshot_text: '' };
    }
    const four = { year: fc.year, month: fc.month, day: fc.day, hour: fc.time };
    const st = computeWuxingStrength(four, {});
    const gy = st ? computeGejuYongShen(four, st) : null;
    const mp = computeMangPai(four);
    const out = [];

    if (st && Array.isArray(st.scores) && st.scores.length) {
      out.push('[五行力量]');
      out.push(st.cangVersion === 'fenye'
        ? '（分野加权：天干100/本气100/中气60/余气30；月柱仅当令司令吃月令×1.5，余月支藏干不加月乘）'
        : '（通行示例权重：天干100/本气100/中气60/余气30/月令×1.5）');
      out.push(`分布：${st.scores.map((s) => `${s.label}${s.percent}%`).join('　')}`);
      out.push(`最旺：${st.dominant}　最弱：${st.weakest}`);
      if (st.dayMaster) {
        out.push(`日主${st.dayMaster.element}：${st.dayMaster.verdict}（同党印比 ${st.dayMaster.samePercent}% · 异党 ${Math.round((100 - st.dayMaster.samePercent) * 10) / 10}%）`);
      }
    }

    if (gy && (gy.geju || gy.yongshen)) {
      out.push('');
      out.push('[格局·用神]');
      out.push('当前主用流派：传统综合（各派取用可异，下列多派对照）');
      if (gy.geju) { out.push(`格局：${gy.geju.name}（月令${gy.geju.tenGod || '—'}·${gy.geju.via}）`); }
      if (Array.isArray(gy.schools) && gy.schools.length) {
        out.push('多派用神对照：');
        gy.schools.forEach((s) => {
          out.push(`· ${s.school}${s.verdict ? `·${s.verdict}` : ''}：喜用 ${(s.xi && s.xi.join('·')) || '—'}　忌 ${(s.ji && s.ji.length ? s.ji.join('·') : '—')}；${s.note}`);
        });
      } else if (gy.yongshen) {
        const yo = gy.yongshen;
        out.push(`用神（${yo.school}·${yo.verdict}）：喜用 ${yo.xi.join('·') || '—'}　忌 ${yo.ji.join('·') || '—'}`);
        out.push(`说明：${yo.note}`);
      }
      if (Array.isArray(gy.bianGe) && gy.bianGe.length) {
        out.push('疑似变格（需复核）：');
        gy.bianGe.forEach((b) => out.push(`· ${b.type}·${b.name}（${b.cond}）→ 若成立用${b.yong}、忌${b.bei}；${b.note}`));
      }
      if (Array.isArray(gy.zaGe) && gy.zaGe.length) {
        out.push('杂格（正格优先，需复核填实刑冲）：');
        gy.zaGe.forEach((b) => out.push(`· ${b.name}（${b.cond}）：${b.note}`));
      }
    }

    if (mp && Array.isArray(mp.cells)) {
      out.push('');
      out.push('[盲派结构]');
      out.push('（象法·参考，与扶抑/格局体系不同）');
      out.push(`宾主：${mp.cells.map((c) => `${c.label}${c.role}(${c.gan}${c.zhi})`).join(' ')}`);
      if (mp.zuogong && mp.zuogong.length) {
        out.push('做功路线：');
        mp.zuogong.forEach((z) => out.push(`· ${z.text}`));
      } else {
        out.push('做功：主位之体未直接取宾位之用（多看刑冲合害引动）。');
      }
      if (mp.feishen && mp.feishen.length) { out.push(`废神：${mp.feishen.join('、')}`); }
    }

    const fy = payload?.fenYe;
    if (fy && fy.ruler) {
      out.push('');
      out.push('[月令司令（分野）]');
      out.push(`版本：${fy.versionLabel}`);
      out.push(`节后 ${fy.daysAfterJie} 日，当令：${fy.ruler.gan}（${fy.ruler.pos}）`);
      if (Array.isArray(fy.segments)) {
        out.push(`轮值：${fy.segments.map((s) => `${s.gan}${s.pos}${s.days}日`).join(' → ')}`);
      }
    }

    return { snapshot_text: out.join('\n') };
  } catch (e) {
    return { snapshot_text: '' };
  }
}
