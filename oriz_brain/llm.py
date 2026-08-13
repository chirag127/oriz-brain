"""Keyless LLM client — mirrors agent-forge provider chain (kilo -> pollinations failover)."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
import structlog

log = structlog.get_logger(__name__)

_KILO_URL = "https://api.kilo.ai/api/gateway/v1/chat/completions"
_POLLINATIONS_URL = "https://text.pollinations.ai/openai"
_REFERER = "https://oriz.in"
_TIMEOUT = 30.0


@dataclass
class LLMMessage:
    role: str
    content: str


@dataclass
class LLMClient:
    timeout: float = _TIMEOUT
    _providers: list = field(default_factory=list, init=False)

    def complete(self, system: str, user: str) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        for name, fn in [("kilo", self._kilo), ("pollinations", self._pollinations)]:
            try:
                result = fn(messages)
                log.debug("llm.ok", provider=name)
                return result
            except Exception as exc:  # noqa: BLE001
                log.warning("llm.failed", provider=name, error=str(exc)[:80])
        return "[LLM unavailable — all providers failed]"

    def _kilo(self, messages: list[dict]) -> str:
        resp = httpx.post(
            _KILO_URL,
            json={"model": "kilo-auto/free", "messages": messages, "max_tokens": 512},
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    def _pollinations(self, messages: list[dict]) -> str:
        resp = httpx.post(
            _POLLINATIONS_URL,
            json={"model": "openai", "messages": messages, "max_tokens": 512},
            headers={"Content-Type": "application/json", "Referer": _REFERER},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
