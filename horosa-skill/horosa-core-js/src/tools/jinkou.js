import { unwrapNamedObject } from '../shared/unpack.js';
import { buildJinKouData } from '../vendor/jinkou/JinKouCalc.js';
import { resolveJinKouDiFen } from '../vendor/jinkou/JinKouState.js';

function normalizeTimeBranch(timeValue) {
  const text = `${timeValue || ''}`;
  const match = text.match(/[子丑寅卯辰巳午未申酉戌亥]/);
  return match ? match[0] : '';
}

function buildJinkouSnapshotText(liureng, jinkouData, options) {
  const nongli = liureng && liureng.nongli ? liureng.nongli : {};
  const rows = Array.isArray(jinkouData.rows) ? jinkouData.rows : [];
  const lines = [
    '[起盘信息]',
    `日干支：${nongli.dayGanZi || ''}`,
    `时辰：${nongli.time || ''}`,
    `月干支：${nongli.monthGanZi || ''}`,
    `地分：${jinkouData.diFen || options.diFen || ''}`,
    '',
    '[金口诀速览]',
    `月将：${jinkouData.jiangName || ''}${jinkouData.jiangZi ? `(${jinkouData.jiangZi})` : ''}`,
    `贵神：${jinkouData.guiName || ''}${jinkouData.guiZi ? `(${jinkouData.guiZi})` : ''}`,
    `人元：${jinkouData.renYuanGan || ''}`,
    `旺神：${jinkouData.wangElem || ''}`,
    `四大空亡：${jinkouData.siDaKong || ''}`,
    '',
    '[金口诀四位]',
  ];
  rows.forEach((row) => {
    lines.push(`${row.label}：内容=${row.content || ''}；神将=${row.shenjiang || ''}；五行=${row.elem || ''}；状态=${row.power || ''}`);
  });
  if (Array.isArray(jinkouData.shenshaRows) && jinkouData.shenshaRows.length > 0) {
    lines.push('');
    lines.push('[四位神煞]');
    jinkouData.shenshaRows.forEach((row) => {
      lines.push(`${row.label}：${row.value || ''}`);
    });
  }
  return lines.join('\n').trim();
}

export function runJinkou(payload) {
  const liureng = unwrapNamedObject(payload.liureng, 'liureng');
  if (!liureng || typeof liureng !== 'object') {
    throw new Error('Jinkou requires a liureng calculation payload.');
  }
  const options = { ...(payload.options || {}) };
  options.diFen = resolveJinKouDiFen(
    options.diFen || payload.diFen || '',
    options.diFenAuto === true,
    normalizeTimeBranch(liureng?.nongli?.time),
    false,
  );
  if (payload.guirengType !== undefined && options.guirengType === undefined) {
    options.guirengType = payload.guirengType;
  }
  if (payload.isDiurnal !== undefined && options.isDiurnal === undefined) {
    options.isDiurnal = payload.isDiurnal;
  }
  const data = buildJinKouData(liureng, options);
  if (!data || data.ready !== true) {
    throw new Error('Jinkou calculation returned no result.');
  }
  return {
    tool: 'jinkou',
    technique: 'jinkou',
    input_normalized: { ...payload, options },
    data,
    snapshot_text: buildJinkouSnapshotText(liureng, data, options),
  };
}
