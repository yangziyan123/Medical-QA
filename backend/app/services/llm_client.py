from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import AsyncIterator

import httpx

from app.core.config import get_settings


@dataclass(frozen=True)
class LLMResult:
    text: str


class LLMClient:
    async def generate(self, *, question: str, context: str | None = None) -> LLMResult:
        raise NotImplementedError

    async def stream(self, *, question: str, context: str | None = None) -> AsyncIterator[str]:
        result = await self.generate(question=question, context=context)
        yield result.text


class StubLLMClient(LLMClient):
    async def generate(self, *, question: str, context: str | None = None) -> LLMResult:
        context_hint = ""
        if context:
            context_hint = "\n\n（已检索到参考资料，见下方引用编号 CIT-1..）"
        answer = (
            "（开发占位回答）\n"
            "你问的是："
            f"{question}\n"
            f"{context_hint}\n\n"
            "建议：补充症状持续时间、伴随症状、既往史和用药史；如出现胸痛、呼吸困难、意识障碍等紧急情况，请立即就医。\n\n"
            "免责声明：仅供参考，不能替代专业医疗建议。"
        )
        return LLMResult(text=answer)

    async def stream(self, *, question: str, context: str | None = None) -> AsyncIterator[str]:
        result = await self.generate(question=question, context=context)
        text = result.text
        chunk_size = 24
        for i in range(0, len(text), chunk_size):
            # Make streaming observable in development (otherwise it may appear "instant").
            await asyncio.sleep(0.03)
            yield text[i : i + chunk_size]


class OpenAICompatibleLLMClient(LLMClient):
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_sec: int = 60,
        max_tokens: int = 800,
        temperature: float = 0.2,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout_sec = timeout_sec
        self._max_tokens = max_tokens
        self._temperature = temperature

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _messages(self, *, question: str, context: str | None) -> list[dict[str, str]]:
        system = (
            "你是医疗问答助手。回答需谨慎、避免诊断与处方，必要时建议就医。"
            "如果问题涉及紧急症状（如呼吸困难、胸痛、意识障碍等），请明确提示立即就医。"
        )
        if context:
            user = f"用户问题：{question}\n\n参考资料（可引用 CIT-1..）：\n{context}\n"
        else:
            user = question
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    async def generate(self, *, question: str, context: str | None = None) -> LLMResult:
        if not self._model:
            raise RuntimeError("LLM model is empty; set LLM_MODEL")

        payload = {
            "model": self._model,
            "messages": self._messages(question=question, context=context),
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "stream": False,
        }

        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout_sec) as client:
            resp = await client.post("/chat/completions", headers=self._headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()

        text = (
            (((data.get("choices") or [])[0] or {}).get("message") or {}).get("content")
            if isinstance(data, dict)
            else None
        )
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("LLM returned empty content")

        return LLMResult(text=text)

    async def stream(self, *, question: str, context: str | None = None) -> AsyncIterator[str]:
        if not self._model:
            raise RuntimeError("LLM model is empty; set LLM_MODEL")

        payload = {
            "model": self._model,
            "messages": self._messages(question=question, context=context),
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "stream": True,
        }

        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout_sec) as client:
            async with client.stream("POST", "/chat/completions", headers=self._headers(), json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith(":"):
                        continue
                    if not line.startswith("data:"):
                        continue
                    chunk = line[len("data:") :].strip()
                    if not chunk or chunk == "[DONE]":
                        if chunk == "[DONE]":
                            break
                        continue
                    try:
                        evt = json.loads(chunk)
                    except Exception:
                        continue
                    choices = evt.get("choices") if isinstance(evt, dict) else None
                    if not choices:
                        continue
                    delta = (choices[0].get("delta") or {}).get("content")
                    if isinstance(delta, str) and delta:
                        yield delta


def get_llm_client() -> LLMClient:
    settings = get_settings()
    provider = (settings.llm_provider or "stub").lower()
    if provider in {"stub", "dev"}:
        return StubLLMClient()

    if provider in {"openai_compat", "openai-compatible", "volcengine", "ark"}:
        return OpenAICompatibleLLMClient(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_sec=settings.llm_timeout_sec,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
        )

    raise RuntimeError(f"Unsupported LLM provider: {settings.llm_provider}")
