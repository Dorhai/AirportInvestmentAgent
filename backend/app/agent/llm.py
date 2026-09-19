"""LLM client abstraction for tool-calling and response generation."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
import logging
from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.models.chat import ToolResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain objects
# ---------------------------------------------------------------------------


class ToolCall(BaseModel, frozen=True):
    name: str
    arguments: dict[str, Any]


class TurnContext(BaseModel, frozen=True):
    system_prompt: str
    history: list[dict[str, str]]
    conversation_frame: str
    thread_digest: str = ""
    facts_digest: str
    resolution_hints: list[str]
    injection_note: str
    user_message: str


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMClient(Protocol):
    async def choose_tools(
        self, ctx: TurnContext, available: list[str]
    ) -> list[ToolCall]: ...

    async def respond(
        self, ctx: TurnContext, evidence: list[ToolResult]
    ) -> str: ...

    async def respond_stream(
        self, ctx: TurnContext, evidence: list[ToolResult]
    ) -> AsyncIterator[str]: ...


# ---------------------------------------------------------------------------
# OpenAI implementation
# ---------------------------------------------------------------------------


_API_URL = "https://api.openai.com/v1/chat/completions"


def _build_messages(ctx: TurnContext) -> list[dict[str, str]]:
    msgs: list[dict[str, str]] = [{"role": "system", "content": ctx.system_prompt}]

    if ctx.conversation_frame:
        msgs.append({"role": "system", "content": f"[conversation frame]\n{ctx.conversation_frame}"})

    if ctx.thread_digest:
        msgs.append({"role": "system", "content": f"[conversation thread]\n{ctx.thread_digest}"})

    if ctx.facts_digest:
        msgs.append({"role": "system", "content": f"[facts]\n{ctx.facts_digest}"})

    if ctx.injection_note:
        msgs.append({"role": "system", "content": ctx.injection_note})

    msgs.extend(ctx.history)

    if ctx.resolution_hints:
        hint_block = "\n".join(f"- {h}" for h in ctx.resolution_hints)
        msgs.append(
            {"role": "system", "content": f"[resolution hints]\n{hint_block}"}
        )

    msgs.append({"role": "user", "content": ctx.user_message})
    return msgs


class OpenAILLMClient:
    def __init__(
        self,
        *,
        http: httpx.AsyncClient,
        model: str | None = None,
    ) -> None:
        self._http = http
        self._model = model or settings.LLM_MODEL

    def _headers(self) -> dict[str, str]:
        key = settings.LLM_API_KEY
        if key is None:
            raise RuntimeError("LLM_API_KEY is not configured")
        return {
            "Authorization": f"Bearer {key.get_secret_value()}",
            "Content-Type": "application/json",
        }

    async def choose_tools(
        self, ctx: TurnContext, available: list[str]
    ) -> list[ToolCall]:
        from app.agent.tools import tool_schemas

        schemas = tool_schemas(available)
        if not schemas:
            return []

        body: dict[str, Any] = {
            "model": self._model,
            "messages": _build_messages(ctx),
            "tools": schemas,
            "tool_choice": "auto",
        }

        resp = await self._http.post(
            _API_URL, json=body, headers=self._headers()
        )
        resp.raise_for_status()

        data = resp.json()
        choice = data["choices"][0]
        message = choice.get("message", {})
        raw_calls = message.get("tool_calls", [])

        calls: list[ToolCall] = []
        for rc in raw_calls:
            fn = rc.get("function", {})
            name = fn.get("name", "")
            try:
                arguments = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                logger.warning("Malformed tool arguments from LLM for %s", name)
                arguments = {}
            calls.append(ToolCall(name=name, arguments=arguments))

        return calls

    async def respond_stream(
        self, ctx: TurnContext, evidence: list[ToolResult]
    ) -> AsyncIterator[str]:
        msgs = _build_messages(ctx)

        if evidence:
            evidence_block = "\n\n".join(
                e.model_dump_json(indent=None) for e in evidence
            )
            msgs.append(
                {
                    "role": "system",
                    "content": f"[tool results]\n{evidence_block}",
                }
            )

        body: dict[str, Any] = {
            "model": self._model,
            "messages": msgs,
            "stream": True,
        }

        async with self._http.stream(
            "POST", _API_URL, json=body, headers=self._headers()
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass


# ---------------------------------------------------------------------------
# Scripted client for testing
# ---------------------------------------------------------------------------


class ScriptedLLMClient:
    """Deterministic stand-in that returns pre-loaded sequences."""

    def __init__(
        self,
        tool_calls: Sequence[list[ToolCall]] = (),
        responses: Sequence[str] = (),
    ) -> None:
        self._tool_calls = list(tool_calls)
        self._responses = list(responses)
        self._tool_idx = 0
        self._resp_idx = 0

    async def choose_tools(
        self, ctx: TurnContext, available: list[str]
    ) -> list[ToolCall]:
        if self._tool_idx < len(self._tool_calls):
            result = self._tool_calls[self._tool_idx]
            self._tool_idx += 1
            return result
        return []

    async def respond(
        self, ctx: TurnContext, evidence: list[ToolResult]
    ) -> str:
        if self._resp_idx < len(self._responses):
            result = self._responses[self._resp_idx]
            self._resp_idx += 1
            return result
        return ""

    async def respond_stream(
        self, ctx: TurnContext, evidence: list[ToolResult]
    ) -> AsyncIterator[str]:
        if self._resp_idx < len(self._responses):
            result = self._responses[self._resp_idx]
            self._resp_idx += 1
            # Yield it in chunks to simulate streaming
            for i in range(0, len(result), 5):
                yield result[i:i+5]
        else:
            yield ""
