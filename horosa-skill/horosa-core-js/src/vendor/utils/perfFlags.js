import { safeLocalStorageSet } from '../gua/safeStorage.js';
// perfFlags.js —— 流畅度优化项的独立开关(默认全开,调用时读取)。
//
// 每项优化只动「时机/调度」不动「内容/语义」,但仍各配 kill-switch:现场发现异常时
// 单项关闭立即回到旧行为,无需回滚代码。关闭方法(控制台执行后刷新):
//   safeLocalStorageSet('horosa.perf.lazySnapshot', '0')   // 快照惰性构建
//   safeLocalStorageSet('horosa.perf.ziweiRulesCache', '0')// 紫微 rules 会话缓存
//   safeLocalStorageSet('horosa.perf.chartDrawGuard', '0') // 图面重绘签名守卫
//   safeLocalStorageSet('horosa.perf.chartSCU', '0')       // 盘面重组件 shouldComponentUpdate
//   safeLocalStorageSet('horosa.perf.hookRaf', '0')        // 排盘 hook rAF 化
//   safeLocalStorageSet('horosa.perf.freezeInactiveTabs','0')// 冻结非激活 TabPane 重渲(顶层技法页签)
//   safeLocalStorageSet('horosa.perf.freezeSubTabs','0')   // R4-B1:冻结非激活【子页签】重渲(FreezeSubTab)
//   safeLocalStorageSet('horosa.perf.subTabDeferMount','0')// R4-B1:子页签「从未激活过则延迟首次渲染」
//   safeLocalStorageSet('horosa.perf.requestDedupe', '0')  // 计算请求 去重+短TTL缓存
//   safeLocalStorageSet('horosa.perf.techniqueCache', '0') // L2 技法结果缓存(10min,来回拨参数≈0)
//   safeLocalStorageSet('horosa.perf.idleWarmQueue', '0')  // 就绪后空闲预热队列(chunk/引擎/数据)
//   —— 以下九项为「点时间→出盘极速化」大修(2026-07) ——
//   safeLocalStorageSet('horosa.perf.fieldsFastCommit', '0')      // chartFree 页 fields 先行提交(快车道)
//   safeLocalStorageSet('horosa.perf.prewarmRequests', '0')       // 非快车道页并行预热请求集
//   safeLocalStorageSet('horosa.perf.silentTechniquePanels', '0') // 技法面板请求 silent+keep-stale(关=旧全屏 Spin)
//   safeLocalStorageSet('horosa.perf.ziweiLocalFirst', '0')       // 紫微默认本地引擎(关=旧 Java 默认)
//   safeLocalStorageSet('horosa.perf.leadingDebounce', '0')       // 主盘时间防抖 leading 立发(关=纯 trailing 180ms)
//   safeLocalStorageSet('horosa.perf.sharedNativeModel', '0')     // native 技法 center/aux 共享模型 memo
//   safeLocalStorageSet('horosa.perf.singleTriggerPredictive','0')// PD/ZR hook+didUpdate 同签名去重
//   safeLocalStorageSet('horosa.perf.stepPrefetch', '0')          // 时间步进方向预取
//   safeLocalStorageSet('horosa.perf.stepPrefetchArm', '0')       // R4-B2:选步长/出盘/切页即武装 ±N 步预取(关=只剩步进后预取)
//   safeLocalStorageSet('horosa.perf.stepPrefetchDepth', '2')     // R4-B2:武装深度 ±N(默认 3,合法 0..5,0=等效关)
//   safeLocalStorageSet('horosa.perf.dataWarmTasks', '0')         // R4-B3:排盘后数据层空闲预热(组式)细闸
//   safeLocalStorageSet('horosa.perf.neighborPrefetch', '0')      // R4-B3:分至图年份邻位预取(year±1)
//   safeLocalStorageSet('horosa.perf.speculativePrecompute', '0') // R4-B5:表单编辑期防抖预发同参请求(只暖缓存)
//   safeLocalStorageSet('horosa.perf.optionPrefetch', '0')        // R4-B5:选项 Hamming-1 投机预取(关=零任务)
//   safeLocalStorageSet('horosa.perf.bootChartRestore', '0')      // R4-B8:温启恢复上次的盘(关=启动回空白默认态)
//   safeLocalStorageSet('horosa.perf.chartCloneLite', '0')        // 出盘缓存冻结共享引用(关=每次深拷贝)
//   safeLocalStorageSet('horosa.perf.hoverPrefetch', '0')         // 导航悬停预取 chunk(关=点击才载)
//   safeLocalStorageSet('horosa.perf.netResultCache', '0')        // 请求结果 L3 持久缓存(IndexedDB,跨重启 0 往返)
//   safeLocalStorageSet('horosa.perf.bootGate', '0')              // [B1] early 导航后端探活门(关=请求直发,未起时报错重试)
//   safeLocalStorageSet('horosa.perf.bootGateFastRetry', '0')     // [R5 S2] 就绪门探活重试 50ms(关=回旧 350ms;壳确认事件两档都即时放行)
//   safeLocalStorageSet('horosa.perf.requestPriorityLane', '0')   // [R5 T5] 后台预取请求带 X-Horosa-Priority 头(引擎侧让用户请求先算;关=永不加头)
//   safeLocalStorageSet('horosa.perf.rsaSessionKey', '0')         // [A2] RSA 会话密钥复用(关=每请求重算 2048 位模幂)
//   safeLocalStorageSet('horosa.perf.cryptoV2', '0')              // [R5 T0] 响应改会话钥 AES-GCM + WebCrypto 异步解(关=旧 RSA 信封 + 主线程 JS 解)
//   safeLocalStorageSet('horosa.perf.recordStoreFastWrite', '0')  // [P0-S5] 记录库写路径:逐记录序列化缓存+装饰排序+缓存对象身份保持(关=整库 stringify/parse 旧路径)
//   safeLocalStorageSet('horosa.perf.sourcesCache', '0')          // [P0-S2] AI 分析源列表指纹缓存+引用稳定+单条 O(1) 查找(关=每次全建新数组)
//   safeLocalStorageSet('horosa.perf.agentBatchSelect', '0')      // AI 助手批量建档只在批尾选中末条(关=逐条选中)
//   safeLocalStorageSet('horosa.perf.contextCachePrune', '0')     // [P0-S4] AI 源上下文缓存条数上限裁剪(关=缓存只增不减)
//   safeLocalStorageSet('horosa.perf.usageOrderedPreload', '0')   // [R5 N2] chunk 预载 / 引擎与数据预热按本机技法使用频次排序(关=写死的概率序)
// 恢复:对应 key removeItem 或设 '1'。

export function flagEnabled(key){
	try{
		if(typeof window !== 'undefined' && window.localStorage){
			return window.localStorage.getItem(key) !== '0';
		}
	}catch(e){
		// localStorage 不可用时按默认开
	}
	return true;
}

// [P0-S4] AI 分析源上下文缓存(IndexedDB context_cache)条数上限裁剪:按写计数触发,超过上限时沿
// updatedAt 索引删最旧(命中记录会被触摸续命)。关=不裁剪,回到「缓存只增不减」的旧行为。
export function contextCachePruneEnabled(){
	return flagEnabled('horosa.perf.contextCachePrune');
}

export function lazySnapshotBuildEnabled(){
	return flagEnabled('horosa.perf.lazySnapshot');
}

export function ziweiRulesCacheEnabled(){
	return flagEnabled('horosa.perf.ziweiRulesCache');
}

export function chartDrawGuardEnabled(){
	return flagEnabled('horosa.perf.chartDrawGuard');
}

export function chartSCUEnabled(){
	return flagEnabled('horosa.perf.chartSCU');
}

export function hookRafEnabled(){
	return flagEnabled('horosa.perf.hookRaf');
}

export function freezeInactiveTabsEnabled(){
	return flagEnabled('horosa.perf.freezeInactiveTabs');
}

// horosa_freeze_subtabs_v1(R4-B1):子页签冻结总闸。
// 关掉 → FreezeSubTab 的 sCU 恒真且不再延迟首渲,回到「技法内所有子面板每次父重渲都跟着重渲」的旧行为。
export function freezeSubTabsEnabled(){
	return flagEnabled('horosa.perf.freezeSubTabs');
}

// horosa_freeze_subtabs_v1 细闸:只管「从未激活过的子页签延迟到首次激活才渲染」。
// 关掉 → 子面板一开始就渲一次(冻结仍生效),用于排查「某面板必须挂载才注册副作用」类问题。
export function subTabDeferMountEnabled(){
	return flagEnabled('horosa.perf.subTabDeferMount');
}

export function requestDedupeEnabled(){
	return flagEnabled('horosa.perf.requestDedupe');
}

export function techniqueCacheEnabled(){
	return flagEnabled('horosa.perf.techniqueCache');
}

// [A1] L3 持久结果缓存(IndexedDB):同参跨会话零网络零 RSA。默认开;置 '0' 一键回退到纯内存 L1/L2。
export function netResultCacheEnabled(){
	return flagEnabled('horosa.perf.netResultCache');
}

export function idleWarmQueueEnabled(){
	return flagEnabled('horosa.perf.idleWarmQueue');
}

// —— 「点时间→出盘极速化」大修(2026-07) 九开关 ——
// 与既有开关同则:默认开、只动时机/调度不动内容语义、单项关闭即回旧行为。

export function fieldsFastCommitEnabled(){
	return flagEnabled('horosa.perf.fieldsFastCommit');
}

export function prewarmRequestsEnabled(){
	return flagEnabled('horosa.perf.prewarmRequests');
}

export function silentTechniquePanelsEnabled(){
	return flagEnabled('horosa.perf.silentTechniquePanels');
}

export function ziweiLocalFirstEnabled(){
	// ⚠️ 本开关是【opt-in】(缺省=关),与其余默认开的开关相反。
	//    2026-07-19:24 例网格对拍已【全绿】(Java 兼容档三键 yearBoundary:lunar_1_1 /
	//    ziweiLunarBasis:calendar / lifeMasterBy:year_branch,见 ziweiLocalParity.test)=
	//    排盘核心字节证明达成;但「切默认」还差【全响应形状】装配审计(nongli 文本/bazi 块/
	//    顶层兼容字段的本地组装逐字对拍)——审计过前本开关保持 opt-in 且暂无消费者(荷载待接线)。
	try{
		if(typeof window !== 'undefined' && window.localStorage){
			return window.localStorage.getItem('horosa.perf.ziweiLocalFirst') === '1';
		}
	}catch(e){ /* 默认关 */ }
	return false;
}

export function leadingDebounceEnabled(){
	return flagEnabled('horosa.perf.leadingDebounce');
}

export function bootGateEnabled(){
	// [B1] 桌面壳 early 导航(前后端启动重叠)时,请求层按目标根探活排队;
	// 关=请求直发(后端未起时走既有报错/重试/离线横幅,行为回到旧序)。
	return flagEnabled('horosa.perf.bootGate');
}

// [R5 S2] 就绪门探活重试间隔 50ms(回环拒连探测近零成本;旧 350ms 让首盘平均多等 175ms)。
// 关=回旧 350ms。壳的 horosa:backend-confirmed 事件与之无关:两档都是事件一到立即放行。
export function bootGateFastRetryEnabled(){
	return flagEnabled('horosa.perf.bootGateFastRetry');
}

// [R5 T0] 响应加解密 v2:请求头声明能力(X-Horosa-Crypto: gcm1),服务端用请求里已协商的会话钥做 AES-128-GCM
// (免每响应 RSA 私钥运算),前端用浏览器原生 WebCrypto 异步解、不占主线程。关=服务端回旧 RSA 信封(Encrypted: 1)。
// 依赖会话钥复用(rsaSessionKey 关时本能力自动不声明)与 crypto.subtle 在场。
export function cryptoV2Enabled(){
	return flagEnabled('horosa.perf.cryptoV2');
}

export function rsaSessionKeyEnabled(){
	// [A2] :9999 请求体加密的 AES 钥+RSA 密文会话内复用(每会话一次 2048 位模幂,
	// 旧式=每请求一次、主线程)。关=逐请求随机钥(字节行为回旧)。Java 侧零改动。
	return flagEnabled('horosa.perf.rsaSessionKey');
}

// [P0-S5] 命盘/事盘记录库写路径的纯 CPU 优化(储存字节与旧路径恒等):
//   ① 逐记录序列化缓存(WeakMap<记录对象, JSON 串>):一次写只序列化新建/合并的 1-2 条,其余记录直接拼串;
//   ② 排序装饰-排序-去装饰:每记录 Date.parse 一次(旧比较器每次比较各 parse 两次);
//   ③ 写后缓存对象身份保持:未触碰记录跨写仍是同一对象(读缓存共享引用契约不变)。
// 关=回到整库 JSON.stringify + JSON.parse(text) 全量路径;失败/quota 分支两态同码。
export function recordStoreFastWriteEnabled(){
	return flagEnabled('horosa.perf.recordStoreFastWrite');
}

// [P0-S2] AI 分析「可挂载源」列表(listAnalysisSources)指纹缓存:按记录指纹复用 entry 对象、
// 记录集无变化时返回同一数组引用(setState 同引用免重渲),findAnalysisSourceById 单条经内核 cid 索引 O(1) 查找。
// 关=每次全建新数组/新 entry 对象(旧行为)。
export function sourcesCacheEnabled(){
	return flagEnabled('horosa.perf.sourcesCache');
}

export function aiBodyEncryptEnabled(){
	// [G2] :9999 AI 分析请求体 RSA 会话束封套(与排盘 API 同机制)。关=回明文请求体
	// (后端有明文直通宽容,恒可回退);响应两态皆不加密。
	return flagEnabled('horosa.sec.aiBodyEncrypt');
}

export function sharedNativeModelEnabled(){
	return flagEnabled('horosa.perf.sharedNativeModel');
}

export function singleTriggerPredictiveEnabled(){
	return flagEnabled('horosa.perf.singleTriggerPredictive');
}

export function stepPrefetchEnabled(){
	return flagEnabled('horosa.perf.stepPrefetch');
}

// —— R4-B2(horosa_step_prefetch_arm_v1):「选步长即武装」 ——
// 病根:预取单位只来自上一次步进 hint(无 hint 硬编码 'm'),选完新步长的第一下必 miss
// (owner 原话「第一下卡之后不卡」)。武装 = 不等步进,先按当前档位把 ±1..±depth 预好。
export function stepPrefetchArmEnabled(){
	return flagEnabled('horosa.perf.stepPrefetchArm');
}

// 武装深度 ±N。默认 3(±1 即时命中,±2/±3 吃空闲窗);合法 0..5,0=等效关;
// 非法值一律回默认 —— 现场只需 safeLocalStorageSet('horosa.perf.stepPrefetchDepth','2') 即可调。
export function stepPrefetchDepth(){
	try{
		if(typeof window !== 'undefined' && window.localStorage){
			const raw = window.localStorage.getItem('horosa.perf.stepPrefetchDepth');
			if(raw !== null && raw !== undefined && raw !== ''){
				const n = parseInt(raw, 10);
				if(Number.isFinite(n) && n >= 0 && n <= 5){
					return n;
				}
			}
		}
	}catch(e){
		// localStorage 不可用时走默认
	}
	return 3;
}

// R4-B3:排盘后数据层空闲预热(scheduleDataWarmGroup)的细闸——在总闸 idleWarmQueue
// 之内再单独可关。预热只经各技法自己的缓存入口取数(结果与用户首点逐字节一致,只是提前付),
// 关掉即回到「首点付冷成本」的现状。
export function dataWarmTasksEnabled(){
	return flagEnabled('horosa.perf.dataWarmTasks');
}

// R4-B3:分至图年份邻位预取(year±1)的独立闸。
export function neighborPrefetchEnabled(){
	return flagEnabled('horosa.perf.neighborPrefetch');
}

// R4-B5 预测性预计算(speculativePrecompute):用户在排盘表单里编辑参数时,防抖后提前发出与
// 「提交」完全相同的确定性计算请求 —— 结果只进 services 层缓存(chartMem/在途合并),不落任何
// 状态、不动 UI;点提交时直接命中/加入在途 → 点击→显示≈渲染耗时。严禁随机/取现时类端点。
// 关掉(horosa.perf.speculativePrecompute=0)即回到「点提交才计算」。
export function speculativePrecomputeEnabled(){
	return flagEnabled('horosa.perf.speculativePrecompute');
}

// R4-B5(horosa_option_prefetch_v1):选项空间 Hamming-1 投机预取。
export function optionPrefetchEnabled(){
	return flagEnabled('horosa.perf.optionPrefetch');
}

// R4-B5b(horosa_option_debounce_v1):「选项即发」路径 leading 立发+250ms trailing 并帧
// (与时间轴 debounce 分通道)。关=每次选项变更各发各的旧行为。
export function optionDebounceEnabled(){
	return flagEnabled('horosa.perf.optionDebounce');
}

// R4-B5b(horosa_main_chain_abort_v1):/chart 主链新发先 abort 旧在途(网络层取消;
// 结果层正确性由 fieldsEpoch 代际保证,此闸释放连接与后端算力)。关=旧请求自然完成。
//
// 🔴🔴 **默认改为关**(horosa_main_chain_abort_default_off_v1)——实测它会连「本该活下来的
// 那一个」一起取消,造成 chartObj 永不更新的正确性事故:
//   病象:三式合一已起盘后按时间步进(如四分钟一档),中栏表头与奇门/太乙盘都跟着走,
//        **唯独外圈星度(顶/升/金/日/月)冻在起盘那一刻** —— 它的唯一数据源是 props.chartObj。
//   实测差分(同一时刻 17:21):点「确定」→ chartId 换、ASC 288.5→289.51、顶3→4 升18→19 ✅;
//        按步进 ⊕ → chartId/ASC/外圈**逐字不动** ❌。两者在组件层走同一段代码,差别只在
//        步进会连发两次 fetchByFields(确定只发一次)。
//   机理:两个并发 effect(dva 默认 takeEvery)在 `yield select` 处交错后,
//        「持有活 controller 的」与「持有最大 epoch 的」可能落到不同的 effect 上 ⇒
//        活着的那个被 epoch 判过期丢弃、epoch 最大的那个被 abort ⇒ **两个都不落 store**。
//        实测日志指纹:`start epoch=2 / start epoch=3 / abort epoch=2 / abort epoch=3`
//        —— 两条 abort、零条 SAVE。关掉本闸后同一操作立刻恢复正常(已实测复验)。
//   取舍:本闸的收益只是「提前释放连接与后端算力」,而过期响应本就会被 epoch 层丢弃,
//        正确性不依赖它;代价却是一整类「盘不跟时间走」的静默错值。**正确性优先**。
//   要再开:localStorage['horosa.perf.mainChainAbort']='1'(需先把上述竞态真正解决,
//        判据=连点步进时 chartId 必逐次变化)。
export function mainChainAbortEnabled(){
	try{
		if(typeof window !== 'undefined' && window.localStorage){
			return window.localStorage.getItem('horosa.perf.mainChainAbort') === '1';
		}
	}catch(e){
		// localStorage 不可用时按默认关
	}
	return false;
}

// R4-B8(horosa_boot_chart_restore_v1):温启恢复上次工作现场(owner 拍板默认开)。
export function bootChartRestoreEnabled(){
	return flagEnabled('horosa.perf.bootChartRestore');
}

export function chartCloneLiteEnabled(){
	return flagEnabled('horosa.perf.chartCloneLite');
}

// —— WS-N3(2026-07-16):导航悬停预取 ——
export function hoverPrefetchEnabled(){
	return flagEnabled('horosa.perf.hoverPrefetch');
}

// —— 3D 星盘大修 WS-0(2026-07-16) ——
export function astro3dOnDemandEnabled(){
	// 按需渲染:idle 停 rAF(交互/动画/参数变化时唤醒);关=旧持续 rAF 全速渲染
	return flagEnabled('horosa.perf.astro3dOnDemand');
}

// —— 3D 星盘大修 WS-1(2026-07-16) ——
export function astro3dSpriteLabelsEnabled(){
	// 标签走 canvas sprite(每标签 1 quad,billboard 恒可读);关=旧 TextGeometry 网格观感
	return flagEnabled('horosa.perf.astro3dSpriteLabels');
}

// —— 3D 星盘大修 WS-1b(2026-07-16) ——
export function astro3dMorphEnabled(){
	// 改时间滑移补间:仅 chartObj 变化(坐标语义/显示集合未变)时行星沿最短弧 tween 滑到
	// 新位(~600ms),不走全量重建;关=旧全量 disposeMesh+重建
	return flagEnabled('horosa.perf.astro3dMorph');
}

// —— R3-A3(2026-07-21):kentang(:8899 直连 C 型)统一缓存壳 ——
export function kentangCacheEnabled(){
	// /pan 族请求 L1/L2/L3 缓存+在途去重(键=path+body,同 body 恒同果);
	// 关=逐字节旧行为(裸 fetchChartWithRetry 直通,每次全程 Python 重算)
	return flagEnabled('horosa.perf.kentangCache');
}

// —— R3-A1(2026-07-21):选定步长那一刻的双向预取 ——
export function stepSelectPrefetchEnabled(){
	// 时间组件选步长档即预取 ±1、±2 步(第一下也不冷);关=仅 settle 后预取(旧行为)
	return flagEnabled('horosa.perf.stepSelectPrefetch');
}

// AI 助手批量建档(同一轮 / 同一队列里连续多条 create_chart_record / create_case_record 串行写入):
// 开=各条只登记 cid,批尾对最后一条成功建档 refreshSources+selectSource 一次;
// 关=逐条刷新并选中(分析源焦点随每条建档跳动的旧行为)。单条建档两态同形,不受本开关影响。
export function agentBatchSelectEnabled(){
	return flagEnabled('horosa.perf.agentBatchSelect');
}
