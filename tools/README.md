# tools/ 说明

| 脚本 | 作用 | 什么时候跑 |
|---|---|---|
| `gate.py` | 确定性闸门：R16 合规定式否决、R38 缺陷定式补报（服务端落盘前也会调用） | 模型输出变化后，跑分之前 |
| `evaluate.py` | 算验收指标（检出率/误报率/定位准确率/等级一致率/建议可用性） | 系统能输出结果后，每次调优都跑 |
| `build_skills.py` | 从 `rules.yaml`/`compliant.yaml` 生成 4 个 Nexent 技能包并打 zip | 规则库改动后 |
| `validate_labels.py` | 校验标注数据（quote 能否唯一定位、偏移是否正确、字段是否合法） | **每次生成/修改标注后立刻跑** |

## 环境

```powershell
# 只用标准库 + PyYAML（规则库交叉校验用）
D:\python\python3.13.5\python.exe -m pip install pyyaml
```

## 目录约定

```
data/
├── clauses/{cid}.json        条款表（切分结果，evaluate 用它把 clause_no 映射成 clause_id）
├── labels/{cid}.json         人工标注（ground truth）
├── predictions/{cid}.json    系统输出（模型原始 JSON）
├── rules/rules.yaml          规则库（可选，提供 suggestion_keywords 后判定更准）
└── labels/type_map.yaml      风险类型归一化映射（可选）
```

## 常用命令

```powershell
$py = "D:\python\python3.13.5\python.exe"

# 数据自检（有错退出码 2）
& $py D:\contest-32\tools\validate_labels.py --data-root D:\contest-32\data

# 更严格：legal_basis 仍为 pending 也算错，提交前用这个
& $py D:\contest-32\tools\validate_labels.py --data-root D:\contest-32\data --strict

# 跑分并生成测试报告
& $py D:\contest-32\tools\gate.py --data-root D:\contest-32\data
& $py D:\contest-32\tools\evaluate.py --data-root D:\contest-32\data `
      --out D:\contest-32\docs\TEST_REPORT.md

# 三次一致性（predictions/run1,run2,run3 各存一份）
& $py D:\contest-32\tools\evaluate.py --data-root D:\contest-32\data --runs run1,run2,run3

# 不依赖真实数据的自检
& $py D:\contest-32\tools\validate_labels.py --demo
& $py D:\contest-32\tools\evaluate.py --demo
```

## 指标算法（与官方验收口径一致）

| 指标 | 算法 |
|---|---|
| 匹配键 | `(clause_id, risk_type)`；`risk_type` 先经 `type_map.yaml` 归一化 |
| 检出率 | `TP / (TP + FN)`，阈值 ≥85% |
| 误报率 | `FP / (FP + TP)`，阈值 ≤15% |
| 定位准确率 | TP 中，`quote` 必须是条款正文子串 **且** 与标注 quote 相似度 ≥0.90，阈值 **=100%** |
| 等级一致率 | TP 中等级相同比例，阈值 ≥85% |
| 建议可用性 | 命中规则库 `suggestion_keywords`，或无关键词时长度≥10 且非照抄标注，阈值 ≥85% |
| 一致性 | 多次运行风险集合两两 Jaccard 最小值 ≥0.90 |

## 注意

- `predictions/` 里放**模型原始输出**，不要手工修改——跑分要反映真实水平
- 模型输出的 `clause_no` 会由 `clauses/{cid}.json` 映射成 `clause_id`，所以**条款表必须先存在**
- `validate_labels.py` 报错时退出码为 2，可以直接接入 CI
