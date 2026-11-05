# 一步提交 AgentsHub PR

> 目标：把 `submission/贷款合同审查助手/` 三个文件，放进 AgentsHub 的
> `行业智能体/金融/贷款合同审查助手/` 目录，并推送成 PR。

---

## 准备工作（只需一次）

1. **有 GitCode 账号**并已登录：<https://gitcode.com>
2. **Fork 仓库**：打开 <https://gitcode.com/ModelEngine/AgentsHub>，
   点右上角 **Fork**（如果已经 fork 过，跳过）
3. Fork 完成后，你会有一个自己的仓库：
   `https://gitcode.com/<你的用户名>/AgentsHub`

---

## 方案 A：跑脚本（推荐，2 分钟）

在 PowerShell 里执行：

```powershell
cd D:\contest-32
.\submit_agentshub.ps1 -ForkUrl "https://gitcode.com/<你的用户名>/AgentsHub.git"
```

脚本会自动：克隆你的 fork → 复制三个文件 → 提交 → 推送。
**中途会要求登录 GitCode**（输入用户名 + 密码，或私人令牌），这是正常的。

推送成功后，脚本会打印建 PR 的链接，打开它即可。

---

## 方案 B：网页操作（脚本失败时用）

1. 打开你的 fork：`https://gitcode.com/<你的用户名>/AgentsHub`
2. 点 **新建文件**（New file）
3. 文件名处输入完整路径：

   ```
   行业智能体/金融/贷款合同审查助手/README.md
   ```

   （输入 `/` 会自动创建目录）
4. 把 `D:\contest-32\submission\贷款合同审查助手\README.md` 的内容
   全选复制，粘贴进去
5. 下方填提交信息，点 **提交**
6. 重复 2–5 步，上传另外两个文件：
   - `行业智能体/金融/贷款合同审查助手/agent.json`
   - `行业智能体/金融/贷款合同审查助手/prompt.md`
7. 全部提交完后，会在你 fork 的首页看到提示 **"你的分支领先于上游"**，
   点 **发起 Pull Request**（或去 Pull Requests → 新建）

---

## 建 PR 时填什么

| 字段 | 填什么 |
|---|---|
| 源仓库 | `<你的用户名>/AgentsHub`，分支 `main` |
| 目标仓库 | `ModelEngine/AgentsHub`，分支 `main` |
| **标题** | `[new agent] contract_review_agent` （格式是仓库 README 规定的，别改） |
| 描述 | 见下方模板 |

**PR 描述模板**：

```
## 新增智能体：贷款合同审查助手

面向银行与持牌金融机构的贷款合同智能审查智能体。

- 40 条审查规则（利率/担保/违约/合规）
- 原文定位精确到字符、风险三级分级、可直接采纳的修改建议
- 授信批复要素比对

完整项目（含前端、部署包、评测数据集）：
https://github.com/<你的用户名>/contract-review

自测：20 份合同 / 147 条标注，检出率 100%、定位准确率 100%、三次一致性 1.000
```

---

## 常见问题

**Q：输入密码报错？**
GitCode 可能要求使用「私人令牌」而不是密码。在
<https://gitcode.com/setting/token> 生成一个（勾选 `projects` 权限），
推送时密码位置填令牌。

**Q：脚本报 `remote: Permission denied`？**
fork 地址填错了，或者仓库不属于当前登录账号。确认用户名大小写一致。

**Q：`行业智能体` 目录名要一模一样吗？**
要。中文目录名必须完全一致，否则维护者合并后目录结构会乱。

**Q：提交后多久有反馈？**
看维护者审核节奏。如果一周没有动静，可以在 PR 下留言询问。

---

## 检查清单（提交前对照）

- [ ] Fork 已创建
- [ ] `agent.json` 在 `行业智能体/金融/贷款合同审查助手/` 下
- [ ] `prompt.md` 同上
- [ ] `README.md` 同上，且其中的 GitHub 地址已替换
- [ ] PR 标题以 `[new agent] ` 开头
- [ ] PR 描述里贴了完整项目链接
