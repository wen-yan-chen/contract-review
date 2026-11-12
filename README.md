# 贷款合同审查助手

面向银行与持牌金融机构的贷款合同智能审查工具：上传合同，逐条比对 40 条审查规则，
输出带**原文定位**、**风险等级**、**可直接采纳的修改建议**的结构化审查意见。

> 「魔擎开发者激励 1 期」课题 #32 参赛作品。智能体基于
> [Nexent](https://atomgit.com/ModelEngine) 平台编排（知识库挂载 + 自定义技能 + 工具调用）。

---

## 快速开始

```bash
git clone https://github.com/wen-yan-chen/contract-review.git
cd contract-review
cp .env.example .env          # 填入 NEXENT_BASE 与 NEXENT_API_KEY
docker compose up -d --build
```

打开 <http://localhost:8000/web/>，点右上角「上传合同」。

> 端口被占用时改 `.env` 里的 `HOST_PORT`。详见 [DEPLOY.md](DEPLOY.md)。

---

## 评测结果

样本：**28 份合同 / 2,789 条条款 / 147 条标注（计分 75 条）**。

| 指标 | 实测 | 验收要求 | 判定 |
|---|---:|---:|---|
| 风险条款检出率 | **100.0%** | ≥ 85% | 达标 |
| 误报率 | **2.6%** | ≤ 15% | 达标 |
| 原文定位准确率 | **100.0%** | = 100% | 达标 |
| 风险等级一致率 | **100.0%** | ≥ 85% | 达标 |
| 修改建议可用性 | **96.0%** | ≥ 85% | 达标 |
| 三次一致性（Jaccard） | **1.000** | ≥ 0.90 | 达标 |

口径与复现步骤见 [docs/TEST_REPORT.md](docs/TEST_REPORT.md)；数据构成见 [docs/数据说明.md](docs/数据说明.md)。

---

## 能做什么

| 能力 | 说明 |
|---|---|
| **上传解析** | docx / pdf / txt / md，按「第X条」切分条款，表格内容一并提取 |
| **逐条审查** | 40 条规则分四类：利率、担保、违约、合规 |
| **原文定位** | 每条风险给出条款号 + 原文片段，点击卡片跳转到原文并高亮 |
| **风险分级** | 高 / 中 / 低三级，附判定理由与对出借人的不利后果 |
| **修改建议** | 给出可直接替换的条款表述，而不是「建议完善」 |
| **授信比对** | 合同要素与授信批复不一致时提示（金额、利率、担保方式、期限、放款条件） |
| **合同管理** | 侧栏列出全部合同，支持重命名、导出、删除 |
| **报告导出** | Word 报告（含免责声明）与独立打印视图 |

---

## 目录结构

```
.
├── api/                    FastAPI 服务层
│   ├── server.py           上传 / 审查 / 增删改 / 导出 / 闸门接入
│   ├── nexent_client.py    Nexent 北向 API 客户端（SSE 流解析）
│   └── report.py           Word / Markdown 报告生成
├── web/                    前端（原生 JS，无构建步骤）
├── agent/                  智能体配置
│   ├── agent.json          导出配置（含 prompt 与 skill_names）
│   ├── prompt.md           系统提示词全文
│   └── skills/             4 个技能包副本
├── skills/                 技能源码与打包产物
│   ├── loan-rule-cards/    知识类：按 rule_id 返回判定条件
│   ├── missing-clause-audit/  流程类：缺失 / 效力不足 / 合规 三态判定
│   ├── risk-selfcheck/     流程类：输出前四问自检
│   ├── suggestion-compiler/  流程类：建议必须可直接替换
│   └── dist/               可直接上传的 zip
├── data/
│   ├── samples/            28 份模拟合同 + 11 组边界样本
│   ├── clauses/            条款切分结果（2,789 条）
│   ├── labels/             人工标注（147 条）
│   ├── rules/              40 条规则 + 合规定式
│   ├── kb/                 知识库文档（rules-full.md）
│   └── predictions/        审查结果（含闸门留痕）
├── tools/                  数据集校验、跑分、闸门、图表生成
│   ├── validate_labels.py  标注校验（引用必须是原文子串）
│   ├── check_coverage.py   40 条规则覆盖检查
│   ├── batch_run.py        批量推理
│   ├── gate.py             确定性闸门（幂等、可审计、支持 --dry-run）
│   ├── evaluate.py         指标计算
│   ├── build_skills.py     技能打包
│   └── deck/               演示稿生成脚本
├── docs/                   文档、演示稿、图表
├── submission/             AgentsHub 提交材料
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## 技术方案要点

**1. 定位不交给模型**
条款切分由正则锚点完成，`clause_id` 与字符偏移由程序计算，模型只回答「这条是否违反规则」。
服务端还会校验模型给出的引用必须是原文子串，否则整条丢弃——定位准确率因此可达 100%。

**2. 判定闸门写在提示词，不写进知识库**
知识库只描述「什么算问题」，「什么不算问题」放在提示词里。
实测：把合规反例写进知识库会**抬高**该规则的检索权重，误报反而上升。

**3. 两级规则分类**
40 条规则中 20 条有客观判据（计分），20 条需主观权衡（仅提示）。
避免用主观标准稀释客观指标。

**4. 确定性环节不交给模型**
闸门、校验、偏移计算都是代码：幂等、可审计、可回滚。

---

## 复现评测

```bash
python tools/check_coverage.py                     # 规则覆盖检查
python tools/validate_labels.py --data-root data   # 标注校验
python tools/batch_run.py                          # 批量推理（需 Nexent 可达）
python tools/gate.py --data-root data              # 过确定性闸门
python tools/evaluate.py --data-root data --out docs/TEST_REPORT.md
```

> 顺序不可交换：`batch_run` 产出的是模型原始输出，必须先过 `gate.py` 再算指标。

---

## 本地开发（不使用容器）

```bash
pip install -r requirements.txt
cp .env.example .env            # NEXENT_BASE 改成 http://localhost:5013
python api/server.py            # 打开 http://127.0.0.1:8000/web/
```

---

## 演示视频

完整业务闭环（上传 → 逐条审查 → 原文定位 → 修改建议 → 导出报告），7 分钟：

**<https://www.bilibili.com/video/BV1j1W96yEQY/>**

> 原始文件 152 MB，不进入 Git 仓库（见 `.gitignore` 中的 `*.mp4`），以 B 站外链形式提供。

---

## 文档索引

| 文档 | 内容 |
|---|---|
| [DEPLOY.md](DEPLOY.md) | 部署与排障 |
| [USAGE.md](USAGE.md) | 操作说明 |
| [DESIGN.md](DESIGN.md) | 设计取舍与已知局限 |
| [docs/TEST_REPORT.md](docs/TEST_REPORT.md) | 指标口径、评测结果、优化记录 |
| [docs/数据说明.md](docs/数据说明.md) | 数据资产与构造约束 |
| [docs/SKILL_PLAN.md](docs/SKILL_PLAN.md) | 四个技能的设计与验证 |
| [docs/nexent-api-notes.md](docs/nexent-api-notes.md) | Nexent 接口实测笔记 |
| [docs/提交PR指南.md](docs/提交PR指南.md) | AgentsHub 提交流程 |
| [docs/演讲逐字稿.md](docs/演讲逐字稿.md) | 演示视频逐字稿（20 页版） |
| [docs/VIDEO_SCRIPT.md](docs/VIDEO_SCRIPT.md) | 分镜脚本 |
| [docs/报名材料.md](docs/报名材料.md) | 报名帖文案 |
| [CHANGELOG.md](CHANGELOG.md) | 变更记录 |

---

## 数据与合规

- 全部合同、企业名称、金额均为虚构，不含真实企业与个人信息
- 界面、导出报告、打印视图三处免责提示
- 法规依据逐条溯源；未取得权威依据的规则如实标注「未检索到权威依据」，不编造条文
- 审查结论定位为辅助建议，最终以法务与审批人员意见为准

---

## 许可证

[MIT](LICENSE)
