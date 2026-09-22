"""可选云端决策层（TypeSafe Jev，System One 决策模型）。

本包是 skill **唯一**会把用户文本送出本机的路径，所以规则写在最前面：

1. `HOROSA_JEV` 缺省 `off` = 零字节变化：不 import 网络客户端、不读 key、响应体逐字节等于今天。
2. 代码持有权限，模型只供证据：确定性路由 / 澄清门 / 忠实性 / 合参契约不变；决策层只能在无解处兜底、
   把「原话明说」变成「已提供」、或追加只读意见。
3. 失败一律关闭式降级回确定性路径，并经 `_degrade` 进 `envelope.warnings`（禁静默）。
4. 每次真调用都自陈：`data.technique_card.decisions[]` / `DispatchEnvelope.decision_layer`。
5. 一档数据（`meta`）只送本地脱敏后的问题文本；二档（`snapshot`）才允许导出快照文本。

模块：`policy`（旗标→策略）· `questions`（三原语 + 校验）· `jev_http`（传输 + 重试）· `redact`（脱敏）·
`ledger`（本地账本）· `layer`（编排：缓存/熔断/账本/provenance）· `fake`（离线桩）· `surfaces/*`（每面的问题构造点）。
"""

from horosa_skill.decisions.layer import DecisionLayer, Outcome, decision_records, note_decision
from horosa_skill.decisions.policy import Policy, load_policy

__all__ = ["DecisionLayer", "Outcome", "Policy", "decision_records", "load_policy", "note_decision"]
