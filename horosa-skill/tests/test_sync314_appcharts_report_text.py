"""上游 v3.14.0 同步 · 报告正文排版里跟着上游改的地方（reports/renderers.py）。

「Word / PDF 里两张紧挨的表格不再被并成一张」：上游 `utils/mdTableParse.js` 新增 `isNextTableStart`，`aiExportDocModel.js` 的
表体扫描遇到「下一行是严格分隔行（每格 ≥ 3 个连字符）且列数相同」就收表。skill 的报告把引擎导出段交给 `_split_markdown_blocks`
切块，是同一个毛病（cn_b 批 2026-11-13 复现后移交）。
"""
from __future__ import annotations

from horosa_skill.reports.renderers import _split_markdown_blocks

# 上游点名的实例形状：印占「星盘信息」宫头表后面紧跟星点表，中间没有空行
TWO_TABLES = "| 宫 | 黄经 |\n| --- | --- |\n| 1 | 10 |\n| 2 | 40 |\n| 星 | 落宫 |\n| --- | --- |\n| 日 | 3 |\n"


def test_two_tables_without_a_blank_line_between_them_stay_two_tables() -> None:
    """期望值按上游 parseBlocks 的规则手推：第一张表到「| 2 | 40 |」为止，「| 星 | 落宫 |」是第二张的表头。
    负向对照：去掉 `_split_markdown_blocks` 里判下一张表的三行 → 只出一张表，rows 里混进 ['星', '落宫'] 与 ['---', '---'] → 红。"""
    blocks = _split_markdown_blocks(TWO_TABLES)
    assert blocks == [
        ("table", {"header": ["宫", "黄经"], "rows": [["1", "10"], ["2", "40"]]}),
        ("table", {"header": ["星", "落宫"], "rows": [["日", "3"]]}),
    ]


def test_a_table_only_ends_where_upstream_ends_it() -> None:
    """上游 isNextTableStart 的两个限定都要守住：分隔行每格至少三个连字符（表体里的「| - | - |」「| -- | -- |」是占位数据，不是分隔行）；
    列数要相同（不同列数的「表头 + 分隔行」不算下一张表，照旧按本表的行补齐 / 截断）。"""
    dashes = _split_markdown_blocks("| a | b |\n| --- | --- |\n| x | y |\n| - | - |\n| -- | -- |\n| 1 | 2 |\n")
    assert dashes == [("table", {"header": ["a", "b"], "rows": [["x", "y"], ["-", "-"], ["--", "--"], ["1", "2"]]})]
    other_width = _split_markdown_blocks("| a | b |\n| --- | --- |\n| 1 | 2 |\n| p | q | r |\n| --- | --- |\n| 3 | 4 |\n")
    assert len(other_width) == 1 and other_width[0][1]["rows"] == [["1", "2"], ["p", "q"], ["---", "---"], ["3", "4"]]
    # 三张连着也各自成表；表后的正文仍是正文
    three = _split_markdown_blocks("| a |b|\n|---|---|\n|1|2|\n| c |d|\n|:---|---:|\n|3|4|\n| e |f|\n|----|----|\n|5|6|\n尾")
    assert [kind for kind, _payload in three] == ["table", "table", "table", "text"]
    assert [payload["header"] for kind, payload in three if kind == "table"] == [["a", "b"], ["c", "d"], ["e", "f"]]
