// divination/engine/reception.js
// 读后端 receptions {normal[],abnormal[]} 与 mutuals {normal[],abnormal[]}。
// reception 项：{beneficiary, beneficiaryDignity[], supplier, supplierRulerShip[]}
//   = supplier 守护 beneficiary 所落之处（supplier 接纳 beneficiary）。
import { keyOfChartId } from './utils.js';

const STRONG = ['ruler', 'exalt'];

function dignList(arr){ return Array.isArray(arr) ? arr : []; }

// 强接纳（庙/旺）能化解凶相位
export function hasStrongReception(dignTokens){
	return dignList(dignTokens).some((d) => STRONG.indexOf(d) >= 0);
}

// 列出与某星相关的接纳（其作为受纳方或供给方）
export function receptionsOf(facts, key){
	const rec = (facts.result && facts.result.receptions) || {};
	const out = [];
	['normal', 'abnormal'].forEach((band) => {
		(rec[band] || []).forEach((it) => {
			const ben = keyOfChartId(it.beneficiary);
			const sup = keyOfChartId(it.supplier);
			if(ben === key || sup === key){
				out.push({
					beneficiary: ben, supplier: sup,
					supplierRulership: dignList(it.supplierRulerShip),
					beneficiaryDignity: dignList(it.beneficiaryDignity),
					band, strong: hasStrongReception(it.supplierRulerShip),
				});
			}
		});
	});
	return out;
}

// 两星互溶？(mutuals.normal/abnormal)
export function mutualReceptionBetween(facts, a, b){
	const mu = (facts.result && facts.result.mutuals) || {};
	const bands = [];
	['normal', 'abnormal'].forEach((band) => {
		(mu[band] || []).forEach((it) => {
			// it 可能形如 {mutual:[p1,p2], dignity:[..]} 或含 beneficiary/supplier 对
			const pair = it.mutual || it.pair || [it.beneficiary, it.supplier];
			if(!pair) return;
			const k0 = keyOfChartId(pair[0]); const k1 = keyOfChartId(pair[1]);
			if((k0 === a && k1 === b) || (k0 === b && k1 === a)){
				bands.push({ band, dignity: it.dignity || it.dignities || [], strong: band === 'normal' });
			}
		});
	});
	return bands.length ? bands : null;
}

// a 是否接纳 b（b 落 a 的尊贵 + 成相位）：supplier=a, beneficiary=b
export function receives(facts, a, b){
	return receptionsOf(facts, b).find((r) => r.supplier === a && r.beneficiary === b) || null;
}

export default receptionsOf;
