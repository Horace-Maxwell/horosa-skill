// 上游 utils/zhufangRemote.js（v3.14.0）的纯映射抽出件：该文件是网络件（import request + ServerRoot，fetchZhufangRemote 发
// POST /astroextra/zhufang），headless 由 Python 发请求，不 vendor。这里只逐字抽出它的两处纯逻辑——
//   ① 请求体：`{ ...(params || {}), hdTrueNode: …, spiritQuadrant: … }`
//   ② 回包判据：`res && (res.humanDesign || res.spiritNames) ? res : null`
// 源文件的 sha 记在 contracts/vendor_manifest.json（derived_sha256）：上游一动即红，逐字核对后 --restamp。

// = fetchZhufangRemote 的 body（JSON.stringify 之前的对象）。
export function zhufangRequestBody(params, settings){
	const s = settings || {};
	return { ...(params || {}), hdTrueNode: s.hdTrueNode === false || `${s.hdTrueNode}` === '0' || s.hdTrueNode === 'mean' ? 0 : 1, spiritQuadrant: Number(s.spiritQuadrant) || 1 };
}

// = fetchZhufangRemote 拿到回包后的判据：两块都没有就当没取到（调用方照出本地两段）。
export function zhufangRemoteAccepted(data){
	const res = data && (data.Result || data);
	return res && (res.humanDesign || res.spiritNames) ? res : null;
}
