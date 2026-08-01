// Headless no-op shim for 星阙 utils/safeStorage.js. The upstream wrapper guards localStorage against
// WKWebView QuotaExceededError; in the headless Node runtime there is no localStorage and the skill never
// persists 六爻 settings (they are passed explicitly per call), so get returns null and set is a no-op.
export function safeLocalStorageGet() {
  return null;
}
export function safeLocalStorageSet() {
  return false;
}
export function safeLocalStorageRemove() {
  return false;
}
export function isQuotaError() {
  return false;
}
export function clearRecoverableCaches() {
  return 0;
}

// 演禽 yanqinStore 用的 JSON 变体（上游 v50 新增）。headless 无 localStorage、也不该有跨调用的隐式
// 偏好——设置一律由每次调用显式传入，所以读恒为 null（调用方回退到 DEFAULT_*），写为 no-op。
export function safeJsonParseFromStorage() {
  return null;
}
export function safeJsonStringifyToStorage() {
  return false;
}
