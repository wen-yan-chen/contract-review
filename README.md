# 贷款合同审查助手

面向银行与持牌金融机构的贷款合同智能审查工具：上传合同，逐条比对 40 条审查规则，
输出带**原文定位**、**风险等级**、**可直接采纳的修改建议**的结构化审查意见。

> 本项目为「魔擎开发者激励 1 期」课题 #32 的参赛作品，后端智能体基于
> [Nexent](https://atomgit.com/ModelEngine) 平台编排（知识库挂载 + 工具调用）。

---

## 快速开始

```bash
git clone <repo-url> contract-review && cd contract-review
cp .env.example .env          # 填入 NEXENT_BASE 与 NEXENT_API_KEY
docker compose up -d --build
```

打开 <http://localhost:8000/web/>，点右上角「上传合同」即可。

三条命令之外不需要任何手动配置。详细步骤见 [DEPLOY.md](DEPLOY.md)。

---

## 能做什么

| 能力 | 说明 |
|---|---|
| **上传解析** | 支持 docx / pdf / txt / md，自动按「第X条」切分条款（含表格内容） |
| **逐条审查** | 40 条规则分四类：利率、担保、违约、合规 |
| **原文定位** | 每条风险指出条款号 + 原文片段，点击卡片可跳转到原文对应位置 |
| **风险分级** | 高 / 中 / 低三级，附判定理由与对出借人的不利后果 |
| **修改建议** | 给出可直接替换的条款表述，而非泛泛而谈 |
| **授信比对** | 合同要素与授信批复不一致时提示（金额、利率、担保方式、期限、放款条件） |
| **合同管理** | 侧栏列出全部合同，支持重命名、导出 Word 报告、删除 |
| **报告导出** | Word 报告（含免责声明）与独立打印视图 |

---

## 目录结构

```
.
├── api/                FastAPI 后端
│   ├── server.py       接口：上传、审查、增删改、导出
│   ├── nexent_client.py  Nexent 北向 API 客户端（SSE 流解析）
│   └── report.py       Word / Markdown 报告生成
├── web/                前端（原生 JS，无构建步骤）
├── data/
│   ├── samples/        20 份模拟合同（docx）+ 11 组边界样本
│   ├── clauses/        条款切分结果
│   ├── labels/         人工标注（评测基准）
│   ├── rules/          40 条规则（rules.yaml）+ 合规范式（compliant.yaml）
│   └── kb/             知识库文档（rules-full.md）
├── agent/              智能体配置（提示词、agent.json）
├── tools/              数据集校验、跑分、覆盖率检查
├── docs/               测试报告、接口笔记
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## 技术方案要点

**1. 定位不交给模型**
条款切分由正则锚点完成，`clause_id` 与字符偏移由程序计算；模型只负责"这条是否违反规则"。
这样"原文定位准确率 100%"才是可保证的，而不是赌模型输出。

**2. 判定闸门写在系统提示词里**
知识库只描述"什么算问题"，"什么不算问题"放在提示词（每次必进上下文）。
实测：把反例写进知识库会**抬高**该规则的检索权重，反而增加误报。

**3. 两级规则分类**
40 条规则标为 `deterministic`（有客观判据，计入指标）与 `discretionary`（需主观权衡，
作为提示性建议）。避免用主观规则拉低客观指标。

**4. 降级路径**
Nexent 不可达时抛 `NexentUnavailable`，上层可切换本地模型，保证演示不中断。

---

## 评测结果

见 [docs/TEST_REPORT.md](docs/TEST_REPORT.md)。核心数据（28 份合同 / 约 2900 条款 / 75 条计分标注）：

| 指标 | 实测 | 要求 |
|---|---:|---:|
| 风险条款检出率 | 100.0% | ≥85% |
| 误报率 | 2.6% | ≤15% |
| 原文定位准确率 | 100% | =100% |
| 风险等级一致率 | 100% | ≥85% |
| 修改建议可用性 | 96.0% | ≥85% |
| 3 次一致性（Jaccard） | 1.000 | ≥0.90 |

已知局限：剩余 2 条误报集中在 C02（标注为 0 条的干净样本），详见测试报告"已知局限"一节。

---

## 本地开发（不使用容器）

```bash
pip install -r requirements.txt
cp .env.example .env            # NEXENT_BASE 改成 http://localhost:5013
python api/server.py            # 打开 http://127.0.0.1:8000/web/
```

数据集工具：

```bash
python tools/validate_labels.py --data-root data    # 标注校验
python tools/evaluate.py --data-root data           # 指标跑分
python tools/check_coverage.py                      # 规则覆盖检查
```

---

## 许可证

[MIT](LICENSE)
