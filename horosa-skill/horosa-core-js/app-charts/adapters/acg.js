// 天文地图 ACG — the app's own map (components/acg/AcgD3Map.js: d3 geo projection into an <svg>, land / ocean / graticule,
// planet lines with labels, geographic reference lines). AstroAcg feeds it the /location/acg response (the run's acg) with
// the page's factory settings (ACG_PAGE_SETTINGS: all planet lines of getAllLines(), equirect, classic style, labels and
// geo lines on, every other layer off). We instantiate it with those props, give it a 960 × 480 host and a mounted <svg>,
// and call its own rebuild() (projection + base map + drawAll) — the same path componentDidMount takes. Light theme.
import AcgD3Map from '@horosa-app/components/acg/AcgD3Map.js';
import { getAllLines } from '@horosa-app/components/acg/AcgHelper.js';
import { mountSvg, unmount } from '../dom.js';

export function renderAcg(data) {
  const value = data && data.acg;
  if (!value || !value.planets) throw new Error('acg: needs acg.planets');
  document.documentElement.setAttribute('data-horosa-appearance', 'light');
  const props = {
    value, lines: new Set(getAllLines()), projection: 'equirect', mapStyle: 'classic', height: 480,
    showGeo: true, showLS: false, showAspects: false, showPoints: false, showMidpoints: false, showLots: false,
    showVibration: false, showRelCross: false, showZones: false, zoneWidth: 600, showCrossings: false, showCuspLines: false,
    showStars: false, showStarParans: false, showTreasure: false, showGeodetic: false, showParans: false, paranAll: false,
    showLabels: true, clickMarker: null, onMapClick: () => {},
  };
  const map = new AcgD3Map(props);
  map.props = props;
  map.theme = map.computeTheme();
  const W = 960;
  const H = 480;
  const { svg } = mountSvg(W, H);
  // d3-zoom (wired in rebuild for panning) reads the SVG DOM's viewBox / width / height baseVal, which linkedom lacks —
  // give the mounted element those read-only values; zoom is interaction-only and draws nothing
  Object.defineProperty(svg, 'viewBox', { value: { baseVal: { x: 0, y: 0, width: W, height: H } }, configurable: true });
  Object.defineProperty(svg, 'width', { value: { baseVal: { value: W } }, configurable: true });
  Object.defineProperty(svg, 'height', { value: { baseVal: { value: H } }, configurable: true });
  map.svgRef.current = svg;
  map.hostRef.current = { clientWidth: W, clientHeight: H };
  try {
    map.rebuild();
    return { svg: svg.outerHTML, width: W, height: H };
  } finally {
    unmount(svg);
  }
}
