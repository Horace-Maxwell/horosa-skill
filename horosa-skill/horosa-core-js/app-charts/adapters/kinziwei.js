// 测天紫微 / 演禽 — the app shows both on its 紫微 board (KinAstroMain.renderZiWeiCopiedCenter: the kentang pan →
// buildKinAstroZiWeiChart(pan, serviceKey) → <ZiWeiChart value={chart}/>). The builder is module-private in KinAstroMain, so
// we call the page method itself on a bare object ({ config.serviceKey, props.fields }: all it reads) and take the chart
// off the element it returns — the app's own conversion, verbatim — then draw it exactly as the 紫微 adapter does.
import KinAstroMain from '@horosa-app/components/kinastro/KinAstroMain.js';
import { renderZiwei } from './ziwei.js';

function findChartProps(element) {
  let node = element;
  for (let depth = 0; node && depth < 8; depth += 1) {
    if (node.props && node.props.value && Array.isArray(node.props.value.houses)) return node.props;
    const kids = node.props && node.props.children;
    node = Array.isArray(kids) ? kids.find((k) => k && k.props) : kids;
  }
  return null;
}

export function makeKinZiwei(serviceKey) {
  return function renderKinZiwei(data, options = {}) {
    const pan = data && data.raw;
    if (!pan) throw new Error(`${serviceKey}: needs the kentang pan (raw)`);
    const element = KinAstroMain.prototype.renderZiWeiCopiedCenter.call({ config: { serviceKey }, props: { fields: {} } }, pan);
    const props = findChartProps(element);
    if (!props) throw new Error(`${serviceKey}: the page built no 12-house chart`);
    return renderZiwei({ chart: props.value }, options);
  };
}
