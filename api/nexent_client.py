"""Nexent 北向 API 客户端（零第三方依赖，仅标准库）。

实测依据见 docs/nexent-api-notes.md。核心能力：
- list_agents / list_models / health
- chat_events：流式产出 SSE 事件（生成器）
- chat_sync：一次性返回完整回答（内部拼接 final_answer delta）

设计原则：
1. 只用 urllib，避免破坏「干净环境一次部署成功」
2. 401/403 抛明确异常，便于上层做降级
3. 降级开关：Nexent 不可达时，上层捕获 NexentUnavailable 后切本地 LLM
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Iterator


# ---------------------------------------------------------------- 异常


class NexentError(RuntimeError):
    """Nexent 调用基类异常。"""


class NexentAuthError(NexentError):
    """401：Key 无效或过期。"""


class NexentPermissionError(NexentError):
    """403：权限不足（如知识库接口需要资产管理员）。"""


class NexentUnavailable(NexentError):
    """连接失败/超时：上层应走降级路径。"""


# ---------------------------------------------------------------- 配置


@dataclass
class NexentConfig:
    base_url: str = field(default_factory=lambda: os.getenv("NEXENT_BASE", "http://localhost:5013"))
    api_key: str = field(default_factory=lambda: os.getenv("NEXENT_API_KEY", ""))
    timeout: int = 120
    max_retries: int = 2
    retry_backoff: float = 1.5

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        if not self.api_key:
            raise NexentAuthError("NEXENT_API_KEY 未配置")


# ---------------------------------------------------------------- 客户端


class NexentClient:
    def __init__(self, config: NexentConfig | None = None) -> None:
        self.cfg = config or NexentConfig()
        # 显式空 ProxyHandler：避免被系统代理（如 127.0.0.1:7890）劫持
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    # ---------- 底层请求

    def _open(self, path: str, method: str = "GET", body: dict | None = None,
              stream: bool = False, idempotency_key: str | None = None,
              auth: bool = True) -> urllib.response.addinfourl:
        url = f"{self.cfg.base_url}{path}"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Accept", "text/event-stream" if stream else "application/json")
        if body is not None:
            req.add_header("Content-Type", "application/json")
        if auth:
            req.add_header("Authorization", f"Bearer {self.cfg.api_key}")
        if idempotency_key:
            req.add_header("Idempotency-Key", idempotency_key)

        last_exc: Exception | None = None
        for attempt in range(self.cfg.max_retries + 1):
            try:
                return self._opener.open(req, timeout=self.cfg.timeout)
            except urllib.error.HTTPError as e:
                payload = e.read().decode("utf-8", "ignore")[:500]
                if e.code == 401:
                    raise NexentAuthError(f"401 {payload}") from e
                if e.code == 403:
                    raise NexentPermissionError(f"403 {payload}") from e
                if e.code >= 500 and attempt < self.cfg.max_retries:
                    last_exc = e
                    time.sleep(self.cfg.retry_backoff ** attempt)
                    continue
                raise NexentError(f"HTTP {e.code} {payload}") from e
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_exc = e
                if attempt < self.cfg.max_retries:
                    time.sleep(self.cfg.retry_backoff ** attempt)
                    continue
                raise NexentUnavailable(f"{type(e).__name__}: {e}") from e
        raise NexentUnavailable(str(last_exc))

    def _json(self, path: str, method: str = "GET", body: dict | None = None) -> Any:
        with self._open(path, method=method, body=body) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))

    # ---------- 只读接口

    def health(self) -> dict:
        with self._open("/nb/v1/health", auth=False) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))

    def list_agents(self) -> list[dict]:
        return self._json("/nb/v1/agents").get("data", [])

    def list_models(self) -> list[dict]:
        """注意：返回体包含明文模型 api_key，不要落日志、不要进截图。"""
        return self._json("/nb/v1/models").get("data", [])

    def get_agent(self, agent_name: str) -> dict:
        return self._json(f"/nb/v1/agents/{agent_name}")

    # ---------- 核心：跑智能体

    def chat_events(self, agent_name: str, query: str,
                    conversation_id: int | str | None = None,
                    model_id: int | None = None,
                    tool_params: dict | None = None,
                    metadata: dict | None = None,
                    idempotency_key: str | None = None) -> Iterator[dict]:
        """流式产出 SSE 事件字典。每个元素形如 {"type": "...", "content": ...}。"""
        body: dict[str, Any] = {"agent_name": agent_name, "query": query}
        if conversation_id is not None:
            body["conversation_id"] = conversation_id
        if model_id is not None:
            body["model_id"] = model_id
        if tool_params:
            body["tool_params"] = tool_params
        if metadata:
            body["metadata"] = metadata

        with self._open("/nb/v1/chat/run", method="POST", body=body,
                        stream=True, idempotency_key=idempotency_key) as r:
            for raw in r:
                line = raw.decode("utf-8", "ignore").strip()
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload in ("", "[DONE]"):
                    continue
                try:
                    yield json.loads(payload)
                except json.JSONDecodeError:
                    # 非 JSON 的 data 行直接跳过，避免整条流中断
                    continue

    def chat_sync(self, agent_name: str, query: str,
                  conversation_id: int | str | None = None, **kwargs) -> dict:
        """跑一轮并聚合结果。

        返回：
            {
              "answer": str,              # 拼接后的完整回答
              "conversation_id": int|None,
              "steps": int,               # 观察到的 step_count 数量
              "events": int,              # 总事件数
              "raw": [ ... ]              # 事件原文，便于调试/审计
            }
        """
        answer_parts: list[str] = []
        raw_events: list[dict] = []
        conv_id = conversation_id
        steps = 0

        for ev in self.chat_events(agent_name, query, conversation_id=conversation_id, **kwargs):
            raw_events.append(ev)
            etype = ev.get("type")
            content = ev.get("content")

            if etype == "conversation_created":
                c = content if isinstance(content, dict) else {}
                conv_id = c.get("conversation_id", conv_id)
            elif etype == "step_count":
                steps += 1
            elif etype == "final_answer":
                # answer_phase 可能是 delta / final / 缺省；统一按到达顺序拼接，
                # 多段内容交给调用方提取最后一个完整 JSON。
                if isinstance(content, str) and content:
                    answer_parts.append(content)

        return {
            "answer": "".join(answer_parts),
            "conversation_id": conv_id,
            "steps": steps,
            "events": len(raw_events),
            "raw": raw_events,
        }


# ---------------------------------------------------------------- 自检

if __name__ == "__main__":
    client = NexentClient()
    print("health:", client.health())
    agents = client.list_agents()
    print("agents:", [(a["name"], a.get("display_name")) for a in agents])
    if agents:
        name = agents[0]["name"]
        out = client.chat_sync(name, "用一句话介绍你自己")
        print("---")
        print("answer:", out["answer"][:200])
        print("conv_id:", out["conversation_id"], "steps:", out["steps"], "events:", out["events"])
