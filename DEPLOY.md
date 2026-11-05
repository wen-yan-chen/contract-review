# 部署说明

## 一、前置条件

| 项 | 要求 |
|---|---|
| Docker | Docker Desktop 4.x 以上（含 compose v2） |
| Nexent | 已部署并可访问，版本 ≥ 2.8.0 |
| 端口 | 8000（可用 `PORT` 修改） |
| 内存 | 建议 ≥ 4 GB 可用 |

Nexent 的部署见其官方文档。本服务通过**北向 API**（默认 5013 端口）调用智能体，
不依赖 Nexent 的内部数据库或容器网络。

## 二、三步部署

```bash
# 1. 准备配置
cp .env.example .env

# 2. 填写 .env（见下表）
# 3. 启动
docker compose up -d --build
```

`.env` 需要填的两项：

| 变量 | 说明 | 示例 |
|---|---|---|
| `NEXENT_BASE` | Nexent 北向 API 地址 | `http://host.docker.internal:5013` |
| `NEXENT_API_KEY` | Nexent API Key，控制台 → 头像 → 个人设置 → 生成 API Key | `nexent-xxxxxxxx` |
| `HOST_PORT` | 可选，宿主机映射端口（默认 8000） | `8080` |

> **为什么用 `host.docker.internal`**：容器内的 `127.0.0.1` 指容器自己。
> 本服务已配置 `extra_hosts: host.docker.internal:host-gateway`，
> 因此容器可以访问宿主机上运行的 Nexent。
> 若 Nexent 在其他机器，直接填其 IP，例如 `http://192.168.1.20:5013`。

## 三、验证部署

```bash
# 1. 容器状态（应显示 healthy）
docker compose ps

# 2. 健康检查
curl http://localhost:8000/api/health
# {"status":"ok"}

# 3. 合同列表（应有 20 份样例）
curl http://localhost:8000/api/contracts

# 4. 页面
# 浏览器打开 http://localhost:8000/web/
```

最后一步做一次**端到端验证**：页面上传 `data/samples/` 里的任意 docx，
应看到「解析 → 审查 → 结果」全流程，耗时约 30–60 秒。

## 四、常见问题

### 1. 启动报 `NEXENT_API_KEY` 未设置
`.env` 没创建或没填。`docker compose` 会读取同目录的 `.env`，
也可以用 `docker compose --env-file .env up -d` 显式指定。

### 2. 页面能打开，但上传后报「智能体调用失败」
依次检查：

```bash
# 容器能否访问 Nexent
docker compose exec contract-review python -c \
  "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:5013/nb/v1/health', timeout=5).read())"

# Key 是否有效
docker compose exec contract-review python -c \
  "import os,urllib.request; req=urllib.request.Request('http://host.docker.internal:5013/nb/v1/agents'); req.add_header('Authorization','Bearer '+os.environ['NEXENT_API_KEY']); print(urllib.request.urlopen(req, timeout=5).status)"
```

- 第一条失败 → `NEXENT_BASE` 地址不对，或 Nexent 未启动
- 第二条返回 401 → Key 失效，重新生成
- 两条都成功但页面仍报错 → 查看 `docker compose logs -f` 的具体异常

### 3. 智能体返回「未检索到权威依据」
说明知识库没有挂载或未生效。在 Nexent 控制台确认：
- 知识库 `contract-rules` 已上传 `data/kb/rules-full.md`
- 智能体的「知识库管理」里已添加该知识库
- 修改后需**重新发布**智能体

### 4. 端口 8000 被占用
典型场景：本机同时跑了 Nexent，它的 `supabase-kong` 容器会占用 8000。
在 `.env` 里设置 `HOST_PORT=8080`，重启即可（容器内始终监听 8000）。

```bash
# 或直接改端口映射
ports: ["8080:8000"]
```

### 5. 构建时 pip 下载极慢
国内网络在容器内拉 PyPI 可能只有 10 KB/s。用镜像源重建：

```bash
docker compose build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
docker compose up -d
```

Dockerfile 里 `PIP_INDEX_URL` 默认是官方源，可放心提交。

### 6. 改了 `web/` 但页面没变化
前端是**打包进镜像**的，不是挂载。修改后需要重建：

```bash
docker compose up -d --build
```

只改 `data/` 下的内容不用重建（该目录已挂载）。

### 7. 上传的合同重启后消失
`data/` 已挂载为卷（`./data:/app/data`），不会丢。
若仍丢失，检查 compose 里的 volumes 是否被注释。

## 五、不使用容器的部署

```bash
pip install -r requirements.txt
cp .env.example .env          # NEXENT_BASE 改为 http://localhost:5013
python api/server.py          # 默认 127.0.0.1:8000
```

可用环境变量覆盖：`HOST`、`PORT`、`NEXENT_BASE`、`NEXENT_API_KEY`。

## 六、目录与数据持久化

| 容器路径 | 宿主机 | 内容 |
|---|---|---|
| `/app/data` | `./data` | 合同、条款、审查结果、规则库、样例 |

重建镜像（`docker compose up -d --build`）不会影响 `./data` 下的数据。
