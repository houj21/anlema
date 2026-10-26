# -*- coding: utf-8 -*-
"""OpenAI Chat Completions 兼容的 AI 客户端（自动尝试多个候选模型）。"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from .config import settings

logger = logging.getLogger("anlema.ai")


class AIError(RuntimeError):
    pass


async def chat_completion(messages: list[dict], max_tokens: int = 8000,
                          temperature: float | None = None, timeout: float | None = None) -> str:
    if not settings.ai_enabled:
        raise AIError("未配置 AI API Key（ANTHROPIC_AUTH_TOKEN）")

    base = settings.ANTHROPIC_BASE_URL.rstrip("/")
    # 兼容两种写法：base 以 /v1 结尾时不再重复拼接
    url = base + "/chat/completions" if base.endswith("/v1") else base + "/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.ANTHROPIC_AUTH_TOKEN}",
        "Content-Type": "application/json",
    }
    temp = settings.AI_TEMPERATURE if temperature is None else temperature
    last_err = "未知错误"

    # 关键：流式读取时 httpx 的 read timeout 只作用于单次 read 调用，整体耗时不限，
    # 实测一个模型能拖 5 分钟才超时。所以这里自己掐表：总预算用完就放弃，交给模板兜底。
    total = timeout or settings.AI_TIMEOUT
    deadline = time.monotonic() + total
    tmo = httpx.Timeout(total, connect=15.0)
    async with httpx.AsyncClient(timeout=tmo) as client:
        for model in settings.model_candidates():
            left = deadline - time.monotonic()
            if left <= 5:
                logger.warning("AI 总预算 %ss 已用完，停止尝试，交给本地模板", total)
                break
            logger.info("调用模型 %s，剩余预算 %ds", model, int(left))
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temp,
                "stream": True,
            }
            sink: list[str] = []
            try:
                content, reasoning, _raw = await _stream_one(
                    client, url, headers, payload, sink, budget=left
                )
                if content and content.strip():
                    logger.info("AI 生成成功，模型=%s，字符数=%d", model, len(content))
                    return content.strip()
                if reasoning:
                    last_err = "只返回了 reasoning_content（推理模型不适合，换个模型）"
                    logger.warning("模型 %s 只返回推理内容，跳过", model)
                else:
                    last_err = "返回内容为空"
            except Exception as e:  # noqa: BLE001
                last_err = f"{type(e).__name__}: {e}"
                logger.warning("模型 %s 请求异常 %s", model, last_err)
                # 流式已拿到大部分内容且结构完整时，直接用，别白等
                partial = "".join(sink)
                if len(partial) > 1200 and "一键安装脚本" in partial:
                    logger.warning("模型 %s 中断，但已收到 %d 字符，采用部分结果", model, len(partial))
                    return partial.strip()
                continue

    raise AIError(f"AI 调用失败：{last_err}")


async def _stream_one(client: httpx.AsyncClient, url: str, headers: dict,
                      payload: dict, sink: list[str],
                      budget: float | None = None) -> tuple[str, str, str]:
    """流式拿一次回复，返回 (正文, 推理内容, 原始文本)。sink 用于中断时取已收到的内容。

    budget 是这次调用最多能花多少秒；超时会抛出 AIError（内容已落在 sink 里）。
    """
    pieces = sink
    reasoning: list[str] = []
    raw_lines: list[str] = []
    started = time.monotonic()
    async with client.stream("POST", url, headers=headers, json=payload) as r:
        if r.status_code >= 400:
            body = (await r.aread()).decode("utf-8", "replace")
            raise AIError(f"{r.status_code}: {body[:300]}")
        async for line in r.aiter_lines():
            if budget is not None and time.monotonic() - started > budget:
                raise AIError(f"模型生成超过 {int(budget)} 秒未完成")
            if not line:
                continue
            raw_lines.append(line)
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data in ("", "[DONE]"):
                continue
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            choice = (obj.get("choices") or [{}])[0] or {}
            delta = choice.get("delta") or choice.get("message") or {}
            if delta.get("content"):
                pieces.append(delta["content"])
            if delta.get("reasoning_content"):
                reasoning.append(delta["reasoning_content"])

    raw = "\n".join(raw_lines)
    if not pieces:
        # 有网关会忽略 stream=True，直接回一整个 JSON
        try:
            obj = json.loads(raw)
            msg = (obj.get("choices") or [{}])[0].get("message") or {}
            if msg.get("content"):
                pieces.append(msg["content"])
            if msg.get("reasoning_content"):
                reasoning.append(msg["reasoning_content"])
        except Exception:  # noqa: BLE001
            pass
    return "".join(pieces), "".join(reasoning), raw


def extract_json(text: str) -> Any:
    """从模型输出里抠出 JSON（容忍 ```json 代码块与前后废话）。"""
    text = text.strip()
    if text.startswith("```"):
        text = re_sub_fence(text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise AIError(f"模型未返回 JSON：{text[:200]}")
    return json.loads(text[start:end + 1])


def re_sub_fence(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines)
