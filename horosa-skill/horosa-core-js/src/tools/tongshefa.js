import { buildTongSheFaModel, buildTongSheFaSnapshot } from '../vendor/tongshefa/TongSheFaCore.js';

/**
 * 统摄法（纳甲筮法）九段快照。
 *
 * 此前这支是**自建端口**：本文件自己维护 BAGUA / 64 卦名表 / 关系判定，只产 4 段
 * （本卦 / 六爻 / 潜藏 / 亲和），上游的整个计算分析层（三十二观 / 世应 / 五行关系 / 五友 /
 * 大局与动变）没有搬。现改为调用逐字 vendor 的 `TongSheFaCore.js`（上游 TongSheFaMain.js
 * 的 React 类之前那 1000 余行纯计算层），9 段齐全且以后跟上游只需重跑 revendor。
 *
 * 段头归一：上游写全角 `【段名】`，而 skill 的导出解析器认半角 `[段名]`。实测这 9 个段头都
 * **独占一行**，故只在整行为 `【X】` 时替换，正文里的全角括号一律不动。
 *
 * payload: { taiyin, taiyang, shaoyang, shaoyin }（四轴各取一卦名，缺省走上游默认选择）
 */
const DEFAULT_SELECTION = {
  taiyin: '巽',
  taiyang: '坤',
  shaoyang: '震',
  shaoyin: '震',
};

export function runTongSheFa(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  const selection = {
    taiyin: source.taiyin || DEFAULT_SELECTION.taiyin,
    taiyang: source.taiyang || DEFAULT_SELECTION.taiyang,
    shaoyang: source.shaoyang || DEFAULT_SELECTION.shaoyang,
    shaoyin: source.shaoyin || DEFAULT_SELECTION.shaoyin,
  };
  const model = buildTongSheFaModel(selection);
  const raw = model ? buildTongSheFaSnapshot(model) || '' : '';
  const snapshot_text = raw.replace(/^【([^】]+)】$/gm, '[$1]');
  // 卦名在 vendored model 里是 `hex.gua.name`（嵌套），旧端口是平铺的 `hex.name`。
  // 结构化 data 的形状对下游是公开契约（Python 侧 + 测试都在读），所以平铺一份出来。
  const flat = (hex) => (hex ? { ...hex, name: (hex.gua && hex.gua.name) || '' } : null);
  return {
    tool: 'tongshefa',
    technique: 'tongshefa',
    input_normalized: selection,
    data: {
      selected: model ? model.selected : selection,
      baseLeft: flat(model && model.baseLeft),
      baseRight: flat(model && model.baseRight),
      mutualLeft: flat(model && model.mutualLeft),
      mutualRight: flat(model && model.mutualRight),
      oppositeLeft: flat(model && model.oppositeLeft),
      oppositeRight: flat(model && model.oppositeRight),
      // 卦的五行取**京房本宫**而非上卦（上游 getHexElem 已如此），这几个键沿用旧端口命名。
      left_elem: model ? model.leftElem : null,
      right_elem: model ? model.rightElem : null,
      main_relation: model ? model.mainRelation : null,
      left_house: model ? model.leftHouseLabel : null,
      right_house: model ? model.rightHouseLabel : null,
    },
    snapshot_text,
  };
}

export default runTongSheFa;
