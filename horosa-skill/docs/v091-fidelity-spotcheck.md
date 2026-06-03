# v0.9.x 内容保真抽检（推运 / 卜卦 / 择日 vs 星阙）

本轮（P1-2）不止比对 snapshot 段头，而是把 **星阙 前端的真实 builder** 抽出来、喂同一张盘
（`tests/fixtures/chart_1998_predictive.json`，从 live 抓的真盘），与 skill 的输出**逐字节 diff**。

## 方法

- 把 `星阙 astrostudyui/src/components/astro/AstroPersianDirected.js` 里的纯函数
  （`buildPersianHits` + `buildPersianDirectedSnapshotText` + 常量）抽到独立 node 脚本，配 `moment`
  + AstroConst/AstroText stub，喂上面那张 fixture，再与 skill 的 Python builder 输出 diff。
- yearsystem129 / planetaryages 不含 moment 日期运算（前者读服务端 `predictives.yearsystem129` 的
  现成日期、后者只列年龄带），按构造即保真，核对数据来源即可。
- balbillus / 卜卦 / 择日 是**逐字 vendor 的 星阙 JS**（非手移植），按构造与 星阙 一致。

## 结论

| 技法 | 算法/结构 | 数字 | 备注 |
|---|---|---|---|
| **persiandirected**（波斯向运） | ✅ 字节一致 | ⚠️ **应期日期 ≤1 天偏差**（~40% 行） | 见下 |
| **yearsystem129**（129年系统） | ✅ 保真 | ✅ | 日期来自服务端 `predictives`，逐字输出；只在客户端做名称映射 |
| **planetaryages**（行星年龄） | ✅ 保真 | ✅ | 只列年龄带 + 标当前带，无逐行日期 |
| **balbillus** | ✅ 保真 | ✅ | 逐字 vendor 星阙 `balbillus.js`（progextra），构造即一致 |
| **horary / election** | ✅ 保真 | ✅ | 逐字 vendor 整棵 `divination/`，构造即一致 |

### persiandirected 的 ≤1 天日期偏差（已知、可接受）

diff 结果：**年龄列、相位列、向运星列、本命对象列全部字节一致**（120 行 0 差异），唯独**应期日期列**
有 ~44–55 行差 **正好 1 天**。根因有二：

1. **moment 截断小数日**：星阙 `birth.add(age*365.2421904, 'days')` 走 moment，`Date.setDate(d + N)`
   会把小数日截成整数日（验证：`moment('1998-02-20 20:48').add(522.296,'days')` = `1999-07-27 20:48`，
   丢掉 0.296 日）。skill 的 Python `timedelta(days=age*365.2421904)` 保留完整小数（+7 小时），过午夜
   就 +1 天。
2. **JS↔Python 浮点差**：`arc = (target - pl) % 360` 在两边的浮点尾数有 ~1e-10 级差异——年龄四舍五入到
   2 位显示相同（如 0.32），但全精度不同，经"整日边界"放大成 1 天。

试过把 Python 也改成"截断整日"匹配 moment，差异反而从 44→55（因为根因 2 的浮点差主导，单截断治不了）。

**判断**：波斯向运的"应期"本就是近似时点（"1999 年中前后"），日期 ±1 天**在占断上无意义**，且
算法/相位/向运星/本命对象**完全保真**。故保留 skill 的全精度日期、不为了字节级对齐去把 persiandirected
也改成 vendor JS（那是 balbillus 的做法，对 ≤1 天日期不成比例）。代码里已注释，未来若需绝对字节一致，
可按 balbillus 模式把 persiandirected 也走 `progextra` JS vendor。

## 复现

```
# 1) 抽 星阙 builder 跑同一 fixture：
sed -n '16,102p' "<星阙>/astrostudyui/src/components/astro/AstroPersianDirected.js" > /tmp/xq.js   # 去掉 React class
#    配 moment + progConst stub 后 node 运行，与 tests/fixtures/golden_persiandirected.txt diff
# 2) golden 单测（离线回归守护）：
uv run pytest -q tests/test_progression_builders.py
```
