# 技能接入补丁（上传 4 个技能之后照做）

> 顺序：先传技能 → 再改 agent → 再改规则库 → 再跑数据。
> 每一步都给了"怎么验证做对了"。

---

## 1. 登记技能（二选一）

**方式 A（界面，推荐）**

智能体开发 → `contract_review` → 选择工具 → **Skills** 页签 → 依次勾选：

- `loan-rule-cards`
- `missing-clause-audit`
- `risk-selfcheck`
- `suggestion-compiler`

保存。

**方式 B（改文件再导入）**

`agent/agent.json` 第 75 行：

```jsonc
"skill_names": ["loan-rule-cards", "missing-clause-audit", "risk-selfcheck", "suggestion-compiler"],
```

导入后仍需在控制台确认四个技能都在列表里（导入不会自动安装技能）。

**验证**：智能体详情里 `skill_names` 有 4 项，且技能页签显示已安装。

---

## 2. 系统提示词追加一段

位置：紧跟现有「# 执行步骤」之后（不要删改原有闸门）。整段粘贴：

```
# 执行步骤（技能）
1. 判任何一条规则前，先按条款类别取 loan-rule-cards 的规则卡（利率/担保/违约/合规，
   只取一类）。取不到规则卡时不得判定，也不得凭记忆发明判定条件。
2. 规则卡里的「已知误报形态」优先级高于你的直觉：命中即不报，不再讨论。
3. 规则表述含「未约定 / 缺失 / 不明 / 不足」时，改用 missing-clause-audit 的三态判定：
   缺失 / 形式具备但效力不足 / 合规。条款存在不等于合规。
4. 输出 JSON 前，把 risks 交给 risk-selfcheck 逐条自检，按返回的 drop 清单删除。
   未完成自检就输出，视为无效输出，必须重做。
5. suggestion 必须满足 suggestion-compiler 的硬约束：无占位符、继承合同要素、
   结构完整（主体+条件+数值+后果+救济）。
```

**验证**：随便问一句"你有哪些技能"，回答里能列出四个；跑一份合同，SSE 里能看到技能调用步骤。

---

## 3. 修 R38 规则表述（必须做，否则漏检照旧）

`data/rules/rules.yaml`：

```diff
-  title: 电子签名/电子合同效力条款缺失
+  title: 电子签名/电子合同效力约定缺失或效力不足
```

理由：现在的标题写"缺失"，模型只判"有没有"；条款写了"电子签名的效力以出借人系统记录为准"，
存在但效力不利，被整批漏掉（C03-083 / C21-092 / C25-091 三条漏检同一根因）。

改完后重新生成知识库并上传：

```powershell
python tools/export_kb.py
```

在控制台把 `contract-rules` 知识库的 `rules-full.md` 替换为新版本。

**验证**：问"R38 的判定条件是什么"，回答里应出现"效力不足"而不只是"缺失"。

---

## 4. 跑数据

```powershell
# 4.1 先只跑出错过的 6 份（约 5 分钟），确认改动方向对不对
python _scratch\batch_run.py --ids C02,C03,C09,C12,C21,C25

# 4.2 指标
python tools\evaluate.py --data-root data

# 4.3 方向对了再跑全量（28 份，约 20–25 分钟）
python _scratch\batch_run.py

# 4.4 生成正式报告
python tools\evaluate.py --data-root data --out docs\TEST_REPORT.md

# 4.5 三次一致性（约 2–3 分钟）
python _scratch\consistency_test.py C13
```

**判读标准**

| 结果 | 含义 | 下一步 |
|---|---|---|
| 6 份里误报从 5 → ≤1、漏检从 3 → ≤1 | 技能生效 | 跑全量 |
| 误报没降、漏检也没降 | 技能没被激活 | 检查提示词第 2 节；把 `# 执行步骤（技能）` 提到提示词更靠前的位置 |
| 误报降了但漏检涨了 | 规则卡里的「已知误报形态」过度抑制 | 只保留 R16/R23/R33/R34/R40 五条，其余删掉 |
| 一致性掉到 0.9 以下 | 技能激活抖动 | 把 risk-selfcheck 改为每份合同固定调用一次（写死步骤号） |

---

## 5. 别忘了服务端兜底

技能是"过程可见"，不保证每次都被调用。这一步已经在 `tools/gate.py` 实现，
并在 `api/server.py` 落盘前调用：

```python
# api/server.py，拿到 agent 输出之后
from tools.gate import apply_gates
pred, gate_log = apply_gates(pred, clauses)
```

这样即使技能没激活，指标也不会掉回 96% / 6.5%。

---

## 回滚

技能导致的任何退化，按这个顺序退：

1. 先取消勾选 `risk-selfcheck`（影响面最大）；
2. 再取消 `loan-rule-cards`（可能抑制过度）；
3. 提示词里的 `# 执行步骤（技能）` 整段删除；
4. 规则标题改回原样并重传知识库。

