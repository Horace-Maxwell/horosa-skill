// 演禽「演法」流派/互锁开关的共享状态(模块级可观察单例,localStorage 持久跨重载)。
// 左输入栏 YanQinControls 写、右侧 YanQinBranchPanel 读,二者解耦、变更即双向刷新。
import { applyPreset, setOption, DEFAULT_YANQIN_SETTINGS } from './yanqinSchools.js';
import { safeJsonParseFromStorage, safeJsonStringifyToStorage } from '../gua/safeStorage.js';

const STORE_KEY = 'horosa-yanqin-yanfa-settings';
function load() {
	const v = safeJsonParseFromStorage(STORE_KEY);
	if (v && typeof v === 'object' && v.school) {
		// 合并默认(补齐可能新增的开关键),防旧存档缺键
		return { ...DEFAULT_YANQIN_SETTINGS, ...v };
	}
	return applyPreset('chibenli');
}

let _settings = load();
const _subs = new Set();

function persist() { safeJsonStringifyToStorage(STORE_KEY, _settings); }
function emit() { persist(); _subs.forEach((fn) => { try { fn(); } catch (e) { /* ignore */ } }); }

export function getYanqinSettings() { return _settings; }
export function setYanqinSchool(school) { _settings = applyPreset(school); emit(); }
export function setYanqinSwitch(key, value) { _settings = setOption(_settings, key, value); emit(); }
export function subscribeYanqin(fn) { _subs.add(fn); return () => { _subs.delete(fn); }; }
