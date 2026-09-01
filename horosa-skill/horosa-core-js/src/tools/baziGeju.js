// 八字格局：喂后端 fourColumns（四柱·含 stem/stemInBranch），跑五行力量/格局用神/盲派 纯函数引擎，
// 输出 [五行力量]/[格局·用神]/[盲派结构]（+ [月令司令（分野）] 当传入 fenYe）。四柱同源后端故与 [四柱与三元] 一致。
// 任一步失败回空（不连累既有 bazi 段）。
import { computeWuxingStrength } from '../vendor/bazi/baziWuxing.js';
import { computeMangPai } from '../vendor/bazi/baziMangPai.js';
import { computeGejuYongShen } from '../vendor/bazi/baziGejuYongShen.js';
import { buildLocalBaziResult } from '../vendor/bazi/baziLunarLocal.js';

export function runBaziGeju(payload) {
  try {
    const fc = payload?.fourColumns;
    // 🔴 守卫要查引擎**真读的**字段，不是柱对象在不在：baziWuxing 取 `p.stem.element` 与
    // `p.stemInBranch[].element`（baziWuxing.js:112/115）。柱在、藏干缺时旧守卫放行，
    // 强度照算却按缺项打折 —— 又一个「结构完整 ≠ 值可用」。
    const PILLAR_KEYS = ['year', 'month', 'day', 'time'];
    const missing = fc
      ? PILLAR_KEYS.filter((k) => !fc[k] || !fc[k].stem || !Array.isArray(fc[k].stemInBranch))
      : PILLAR_KEYS;
    if (missing.length) {
      // 空段不再无声：Python 侧 _attach_bazi_geju 据此把降级写进 envelope.warnings。
      return {
        snapshot_text: '',
        data: {
          ok: false,
          reason: 'incomplete_four_pillars',
          message: `四柱缺 ${missing.join('/')}（需 stem + stemInBranch），格局段未产出。`,
        },
      };
    }
    // 时柱键名必须是 time：三个引擎（baziWuxing/baziMangPai/baziGejuYongShen）一律按
    // ['year','month','day','time'] 取柱，写成 hour 会让时柱静默缺席（取格/五行力量/盲派全错）。
    const four = { year: fc.year, month: fc.month, day: fc.day, time: fc.time };
    // [月令司令（分野）]：上游在 baziLunarLocal.js:1048 用 computeFenYe(monthZhi, daysAfterJie, version)
    // 本地算出来挂在 bazi.fenYe 上。Python 侧只传 fourColumns（后端响应里没有节后日数），所以给了
    // birth 就用 vendored 的同一个本地引擎补算 —— 与上游同函数同版本，不是另起一套。
    let fy = payload?.fenYe;
    if (!fy && payload?.birth) {
      try {
        const local = buildLocalBaziResult({ ...payload.birth, fenyeVersion: payload?.fenyeVersion });
        fy = local && local.bazi ? local.bazi.fenYe : null;
      } catch (error) {
        fy = null;
      }
    }
    // 🔴 分野必须在强度计算**之前**算出来并喂进去：上游 baziLunarLocal.js:1141-1145 就是
    // `computeWuxingStrength(fourColumns, { cangVersion, siLingGan: fenYe?.ruler?.gan })`。
    // 此前本文件先算 st（空 opt）后算 fy，于是 [五行力量] 段恒按通行版加权，而 :25 那条
    // 「分野加权」说明行结构上永不可达 —— 同一份输出里 [月令司令（分野）] 报着司令干、
    // [五行力量] 却没用它。cangVersion 缺省 'common'，与上游默认逐字一致（零回归）。
    const cangVersion = payload?.cangVersion === 'fenye' ? 'fenye' : 'common';
    const st = computeWuxingStrength(four, {
      cangVersion,
      siLingGan: (fy && fy.ruler) ? fy.ruler.gan : '',
    });
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
      if (gy.chengBai) { out.push(`成败：${gy.chengBai.verdict}——${gy.chengBai.reason}（${gy.chengBai.note}）`); }
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
        out.push('杂格（正格优先，需复核填实刑冲；虚邀暗冲类附真/假判定）：');
        gy.zaGe.forEach((b) => {
          const tag = b.quality ? `【${b.quality}${b.broken && b.broken.length ? `·${b.broken.join('、')}` : ''}】` : '';
          out.push(`· ${b.name}${tag}（${b.cond}）：${b.note}`);
        });
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
