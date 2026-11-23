// 测试用入口：上游 v3.15.0 把 GuaZhanMain.js 拆成壳 + main/*（以时起卦在 main/gua.js、整份快照在 main/snapshot.js），
// skill 不再 vendor 壳。对拍脚本照旧 `import(GUAZHAN)` 后调 buildTimeGua / buildGuaSnapshotText —— 由这里把两个子模块并起来。
export * from '../../../horosa-core-js/src/vendor/guazhan/main/gua.js';
export * from '../../../horosa-core-js/src/vendor/guazhan/main/snapshot.js';
