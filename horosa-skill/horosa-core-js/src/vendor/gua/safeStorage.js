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
