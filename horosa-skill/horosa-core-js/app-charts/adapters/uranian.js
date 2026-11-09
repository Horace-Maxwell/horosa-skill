// 汉堡学派 90° 盘 — the app's own UranianDial (components/germany/UranianDial.js). It is a React class whose render() is an
// empty <svg>; the picture is drawn by its draw() into that svg by id (componentDidMount). We instantiate it with the
// props UranianDialMain.renderDial passes, mount the <svg id>, and call draw() — no React rendering needed.
//   rings  = [{ natal }]: chartToPoints(result) + the 8 TNP from result.raw.tnp + 白羊点 (UranianDialMain.natalPoints),
//            filtered by the stored TNP switch (filterByTnp)
//   others = getStoredUranianDisplay() defaults (no saved preference) and the school's personal set
import UranianDial from '@horosa-app/components/germany/UranianDial.js';
import { chartToPoints } from '@horosa-app/components/germany/UranianDialMain.js';
import { getStoredUranianDisplay } from '@horosa-app/components/germany/UranianDialStyle.js';
import { personalSetForSchool } from '@horosa-app/components/germany/UranianSchools.js';
import * as AstroConst from '@horosa-app/constants/AstroConst.js';
import * as AstroText from '@horosa-app/constants/AstroText.js';
import { mountSvg, unmount } from '../dom.js';

function filterByTnp(points, showTnp) { // UranianDialMain.filterByTnp (module-private there)
  if (showTnp) return points;
  return (points || []).filter((p) => !AstroText.isUranian(p.id) || p.id === AstroConst.ARIES_POINT);
}

export function renderUranianDial(data, options = {}) {
  if (!data || !data.chart) throw new Error('uranian dial: engine result has no chart');
  const tnp = (data.raw && Array.isArray(data.raw.tnp)) ? data.raw.tnp : (Array.isArray(data.tnp) ? data.tnp : []);
  AstroConst.setColorTheme(AstroConst.DefaultColorTheme);
  const disp = getStoredUranianDisplay();
  const points = chartToPoints(data);
  tnp.forEach((t) => points.push({ id: t.id, lon: t.lon, speed: Number.isFinite(Number(t.lonspeed)) ? Number(t.lonspeed) : null }));
  points.push({ id: AstroConst.ARIES_POINT, lon: 0 });
  const size = Number(options.size) || 720;
  const props = {
    rings: [{ key: 'natal', label: '本命', points: filterByTnp(points, disp.showTnp) }],
    base: disp.dialBase, orb: disp.orb, showTnp: disp.showTnp, size,
    onCursorChange: () => {}, onSaArc: () => {},
    personal: personalSetForSchool(disp.school), onlyPersonal: disp.onlyPersonal, orbPersonal: disp.orbPersonal,
    showAntiscia: disp.showAntiscia, crossPointer: disp.crossPointer, showHouseFrames: disp.showHouseFrames,
    showSumPoints: disp.showSumPoints, showArcOpenings: disp.showArcOpenings,
  };
  const dial = new UranianDial(props);
  dial.props = props;
  const { svg } = mountSvg(size, size);
  svg.setAttribute('id', dial.svgid);
  try {
    dial.draw();
    return { svg: svg.outerHTML, width: size, height: size };
  } finally {
    unmount(svg);
  }
}
