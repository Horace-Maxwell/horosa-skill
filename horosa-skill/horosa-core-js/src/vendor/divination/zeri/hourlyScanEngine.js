// [Z0·择日八技法基建] 逐小时扫描通用外壳 —— 抽自 qimenScanEngine(奇门先例,42731 点 parity
// +qimenZeriStress 46 例背书),供 八字/紫微/太乙/六壬/三式合一(以及奇门自身回改为第一实例)复用。
//
// 技法无关面(全在本文件):墙钟↔UTC 换算(0-99 年 setUTCFullYear 铁律)/逐小时采样+尾段补 t1
// 终点样/「递归转变分解」到分钟/plateKey 行折叠/pick 两端内缩 1 分钟/CHUNK 让出主线程/
// AbortSignal/maxHits·maxSpan 防呆/进度契约 {done,total,hits,partial}。
// 技法注入面(makeHourlyScanEngine 五参+可选掩码):
//   makeScanCtx({cfg,geoParams,options,w0,w1}) → 一次性昂贵准备(节气种子/三家 ctx…)
//   computePanAt(scanCtx, geoParams, options, dateStr, timeStr) → pan|null
//   plateKeyOf(pan, mask?) → string   🔴 必须覆盖全部条件可见判定面,且**排除时间戳类回显字段**
//     (太乙 applyNongliDisplay 的 clockTime/realSunTime 类字段入 key = 逐分钟成行爆炸)
//   keyMaskOf({tree, options}) → mask|null(可选)——依赖感知 key 掩码协议:
//     pass 边界永远由 sameRec 的 pass 位分钟级保证;plateKey 只决定「都 pass 的相邻段是否
//     分行」。掩码=按条件树实际依赖收窄 key(六壬首实装:树不涉贵人 → key 略 diurnal 位 →
//     日出日落不再假劈行;涉 → 保留 → 按昼夜盘分行=语义正确)。null/不提供=全位(现状)。
//     🔴 合同:类的 keyDeps 声明、plateKeyOf 掩码分支、keyMaskOf 收集 三处必须同步;
//     未知叶类型(已删类兜底)一律回退全位。判别网:类级判别测试+deps 完备闸(六壬先例)。
//   evaluateTree(tree, pan, explain) → {pass}|判读树(内部自建各技法惰性 evalCtx)
//   rowExtras(pan, keyMask?) → 行附加列对象(奇门 {juText}、六壬 {keTi}…;并入结果行顶层,勿用保留键)
//     [十四轮合同] 徽章面 ⊆ 掩码后 key 面:徽章只可展示「行内恒定」的值——掩码掉的面
//     (三式未涉家/八字未涉柱)在合并行内会变化,钉行首值=显示误导,必须随 keyMask 过滤。
//     奇门/太乙达标论证:时家盘时辰内全要素恒定=行内零变(徽章任取);跨时辰=全盘真变
//     不合并,无「行内变值」窗;黄历日粒度同理;py 三家按条件区间求交无盘 key 概念。
//
// 🔴 递归转变分解的安全前提(奇门论证的迁移条件,新技法接入前必须逐一自证):
//   该技法的全部翻盘输入在 1 小时窗内单调前进、绝不回退(四柱/农历日月/时辰/积年皆单调)。
//   唯一物理盲区 = 两端状态相同的中间毛刺(A→B→A);六壬「晨昏档」在 |lat|>60° 昼或夜短于
//   1 小时时存在理论反例 —— 该档接入方须强制卯酉档或拒扫(见计划 Z5)。
// 🔴 不做「按四柱/时辰 memo 求值」:同四柱不保证同盘(至界分钟级翻局实抓),每样本直算。
// 🔴 通书等日粒度技法不要硬套本壳(分钟 pick 语义不适用),用独立日粒度小引擎。

const MINUTE_MS = 60e3;

function pad2(n){
	return n < 10 ? `0${n}` : `${n}`;
}
// zone 兼容 fields.zone 的两种历史形态:数值小时(8/8.5/-3)与字符串('+08:00'/'8')。
export function zoneOffsetMinutes(zone){
	if(typeof zone === 'number' && Number.isFinite(zone)){
		return Math.round(zone * 60);
	}
	const text = `${zone === undefined || zone === null ? '' : zone}`.trim();
	if(!text){
		return 480;
	}
	const m = /^([+-]?)(\d{1,2})(?::?(\d{2}))?$/.exec(text);
	if(!m){
		return 480;
	}
	const sign = m[1] === '-' ? -1 : 1;
	return sign * (Number(m[2]) * 60 + Number(m[3] || 0));
}
export function wallToMs(dateStr, timeStr, offsetMin){
	const dp = `${dateStr || ''}`.split('-').map(Number);
	const tp = `${timeStr || '00:00'}`.split(':').map(Number);
	if(dp.length < 3 || dp.some((n)=>!Number.isFinite(n))){
		return NaN;
	}
	// setUTCFullYear 绕开 Date.UTC 对 0-99 年的 1900+ 历史映射(仓内铁律,见 baziLunarLocal)。
	const d = new Date(0);
	d.setUTCFullYear(dp[0], dp[1] - 1, dp[2]);
	d.setUTCHours(tp[0] || 0, tp[1] || 0, tp[2] || 0, 0);
	return d.getTime() - offsetMin * MINUTE_MS;
}
export function msToWall(ms, offsetMin){
	const d = new Date(ms + offsetMin * MINUTE_MS);
	return {
		y: d.getUTCFullYear(), mo: d.getUTCMonth() + 1, dd: d.getUTCDate(),
		hh: d.getUTCHours(), mm: d.getUTCMinutes(),
	};
}
export function wallDateStr(w){
	return `${w.y}-${pad2(w.mo)}-${pad2(w.dd)}`;
}
export function wallTimeStr(w){
	return `${pad2(w.hh)}:${pad2(w.mm)}:00`;
}
export function wallText(w){
	return `${wallDateStr(w)} ${pad2(w.hh)}:${pad2(w.mm)}`;
}

function abortErrorOf(name){
	const err = new Error(`${name || 'zeri'} scan aborted`);
	err.name = 'AbortError';
	return err;
}
function rangeError(code, detail){
	const err = new Error(detail || code);
	err.code = code;
	return err;
}

export function makeHourlyScanEngine({
	name,
	makeScanCtx,
	computePanAt,
	plateKeyOf,
	keyMaskOf,
	evaluateTree,
	rowExtras,
	maxHits = 1000,
	maxSpanDays = 1830,
	stepMs = 3600e3,
	chunkSamples = 96,
	pickInsetMs = 3 * MINUTE_MS,	// [十三轮] 60s→180s:判定链与显示链的口径实现差兜底(EoT 简式 vs swiss 曾差 89s 穿透 60s 内缩=用户实抓两课不同盘;行≥1 时辰,3min 内缩无损「开始时刻」语义)
}){
	if(typeof computePanAt !== 'function' || typeof plateKeyOf !== 'function' || typeof evaluateTree !== 'function'){
		throw new Error('makeHourlyScanEngine: computePanAt/plateKeyOf/evaluateTree 必填');
	}
	const extrasOf = typeof rowExtras === 'function' ? rowExtras : ()=>null;

	// 主入口。cfg: { startDate,startTime,endDate,endTime };geoParams: { zone,lon,lat,gpsLon,gpsLat,ad,gender };
	// options: 技法盘面全参数;tree: 各技法 compile 产物;onProgress({done,total,hits,partial});
	// signal: AbortSignal;limits.maxHits 仅供测试注入,生产恒默认。
	async function scan({ cfg, geoParams, options, tree, onProgress, signal, limits }){
		const offsetMin = zoneOffsetMinutes(geoParams && geoParams.zone);
		const t0 = wallToMs(cfg && cfg.startDate, (cfg && cfg.startTime) || '00:00', offsetMin);
		const t1 = wallToMs(cfg && cfg.endDate, (cfg && cfg.endTime) || '23:59', offsetMin);
		if(!Number.isFinite(t0) || !Number.isFinite(t1) || !(t1 > t0)){
			throw rangeError('invalid_range', '时间范围无效:结束须晚于起始');
		}
		const spanDays = (t1 - t0) / 86400e3;
		if(spanDays > maxSpanDays){
			throw rangeError('span_too_large', `跨度 ${Math.ceil(spanDays)} 天超上限 ${maxSpanDays} 天`);
		}
		const w0 = msToWall(t0, offsetMin);
		const w1 = msToWall(t1, offsetMin);
		const scanCtx = typeof makeScanCtx === 'function' ? makeScanCtx({ cfg, geoParams, options, w0, w1 }) : null;
		// 依赖感知掩码:整棵树算一次(树/参数扫描期不变);异常=null 回退全位(保守)。
		let keyMask = null;
		if(typeof keyMaskOf === 'function'){
			try{ keyMask = keyMaskOf({ tree, options }) || null; }catch(e){ keyMask = null; }
		}
		const effMaxHits = (limits && Number(limits.maxHits) > 0) ? Number(limits.maxHits) : maxHits;
		// 采样点:t0 起逐 step,尾段不足一步时恒补 t1 终点样本(把最后一段也钉到分钟语义)。
		const alignedCount = Math.floor((t1 - t0) / stepMs) + 1;
		const lastAligned = t0 + (alignedCount - 1) * stepMs;
		const total = alignedCount + (lastAligned < t1 ? 1 : 0);
		let evalCount = 0;

		const recAt = (ms)=>{
			const w = msToWall(ms, offsetMin);
			const pan = computePanAt(scanCtx, geoParams, options, wallDateStr(w), wallTimeStr(w));
			evalCount++;
			if(!pan){
				return { pass: false, plateKey: '', extras: null };
			}
			const verdict = evaluateTree(tree, pan, false);
			return { pass: !!(verdict && verdict.pass), plateKey: plateKeyOf(pan, keyMask), extras: extrasOf(pan, keyMask) };
		};
		const sameRec = (a, b)=>a.pass === b.pass && a.plateKey === b.plateKey;
		// 把状态不同的相邻样本 (tA,tB] 递归切成分钟级恒定段边界(升序 push 进 out):
		// 中点与两端都不同 = 第三盘在场(至界翻局+时辰边界同小时),两半各自递归。
		const resolveTransition = (tA, recA, tB, recB, out)=>{
			if(sameRec(recA, recB)){
				return;
			}
			if(tB - tA <= MINUTE_MS){
				out.push({ ms: tB, rec: recB });
				return;
			}
			const mid = tA + Math.floor((tB - tA) / 2 / MINUTE_MS) * MINUTE_MS;
			if(mid <= tA || mid >= tB){
				out.push({ ms: tB, rec: recB });
				return;
			}
			const recM = recAt(mid);
			resolveTransition(tA, recA, mid, recM, out);
			resolveTransition(mid, recM, tB, recB, out);
		};

		const rows = [];
		let truncated = false;
		let cur = null;
		const makeRow = (startMs, endMsRaw, extras)=>{
			const endMs = Math.min(endMsRaw, t1);
			const sw = msToWall(startMs, offsetMin);
			const ew = msToWall(endMs, offsetMin);
			// 起盘安全时刻:两端各向内缩 1 分钟(天星 ε 同理)。边界分钟是本引擎判定的翻转瞬间,
			// 而主盘显示管线的真太阳时实现与本地 EoT 存在亚分钟差 —— 恰在边界分钟起盘可能落
			// 界外侧出上一时辰盘(奇门真机实抓:03:09 边界 pick 被显示管线判成 02:59 丑时)。
			const pickMs = Math.min(startMs + pickInsetMs, Math.max(startMs, endMs - pickInsetMs));
			const pickW = msToWall(pickMs, offsetMin);
			// 下限=pickMs 防倒挂:2 分钟行曾算出 pickEnd(=start) < pick(=start+1min)
			const pickEndMs = Math.max(endMs - 2 * pickInsetMs, pickMs);
			const pw = msToWall(pickEndMs, offsetMin);
			return {
				start: wallText(sw),
				end: wallText(ew),
				pick: `${wallDateStr(pickW)} ${wallTimeStr(pickW)}`,
				pickEnd: `${wallDateStr(pw)} ${wallTimeStr(pw)}`,
				startMs,
				endMs,
				durationMin: Math.round((endMs - startMs) / MINUTE_MS),
				...(extras && typeof extras === 'object' ? extras : null),
			};
		};
		const closeAt = (ms)=>{
			if(!cur){
				return;
			}
			if(ms > cur.startMs){
				rows.push(makeRow(cur.startMs, ms, cur.extras));
			}
			cur = null;
		};
		// 流式喂入分钟级状态段:同盘连续命中并行,变盘/失配即在边界分钟切行。
		const feed = (ms, rec)=>{
			if(rec.pass){
				if(!cur || cur.plateKey !== rec.plateKey){
					closeAt(ms);
					cur = { startMs: ms, plateKey: rec.plateKey, extras: rec.extras };
				}
			}else{
				closeAt(ms);
			}
		};

		let done = 0;
		const report = ()=>{
			if(typeof onProgress === 'function'){
				try{
					onProgress({ done, total, hits: rows.length, partial: rows.slice() });
				}catch(e){
					// 进度回调异常不阻断扫描
				}
			}
		};
		let prevMs = null;
		let prevRec = null;
		for(let i = 0; i < total; i++){
			if(signal && signal.aborted){
				throw abortErrorOf(name);
			}
			const ms = i < alignedCount ? t0 + i * stepMs : t1;
			const rec = recAt(ms);
			if(!prevRec){
				feed(ms, rec);
			}else if(!sameRec(prevRec, rec)){
				const boundaries = [];
				resolveTransition(prevMs, prevRec, ms, rec, boundaries);
				for(let b = 0; b < boundaries.length; b++){
					feed(boundaries[b].ms, boundaries[b].rec);
				}
			}
			prevMs = ms;
			prevRec = rec;
			if(rows.length >= effMaxHits){
				truncated = true;
				cur = null;
				break;
			}
			done = i + 1;
			if((i + 1) % chunkSamples === 0){
				report();
				// 让出主线程,保持 UI 可交互/可取消
				await new Promise((resolve)=>setTimeout(resolve, 0));
			}
		}
		closeAt(t1);
		if(rows.length > effMaxHits){
			rows.length = effMaxHits;
			truncated = true;
		}
		done = total;
		report();
		return {
			intervals: rows,
			truncated,
			stats: { samples: total, evalCount, spanDays: Math.round(spanDays * 100) / 100 },
		};
	}

	// 单时刻判读(工作台结果行「详情」):t = 'YYYY-MM-DD HH:mm(:ss)' 墙钟文本。
	// scanCtx 可由调用方传入(复用已建种子),缺省按该时刻年份现建。
	function explainAt({ geoParams, options, tree, t, scanCtx }){
		const text = `${t || ''}`.trim().replace('T', ' ');
		const m = /^(\d{1,4})-(\d{2})-(\d{2})[ ](\d{2}):(\d{2})/.exec(text);
		if(!m){
			return { t: text, tree: null, err: 'invalid_time' };
		}
		const dateStr = `${m[1]}-${m[2]}-${m[3]}`;
		const timeStr = `${m[4]}:${m[5]}:00`;
		const wAt = { y: Number(m[1]), mo: Number(m[2]), dd: Number(m[3]), hh: Number(m[4]), mm: Number(m[5]) };
		const ctx = scanCtx !== undefined && scanCtx !== null
			? scanCtx
			: (typeof makeScanCtx === 'function' ? makeScanCtx({ cfg: null, geoParams, options, w0: wAt, w1: wAt }) : null);
		const pan = computePanAt(ctx, geoParams, options, dateStr, timeStr);
		if(!pan){
			return { t: text, tree: null, err: 'no_pan' };
		}
		const extras = extrasOf(pan);
		return { t: text, tree: evaluateTree(tree, pan, true), ...(extras && typeof extras === 'object' ? extras : null) };
	}

	return { scan, explainAt };
}
