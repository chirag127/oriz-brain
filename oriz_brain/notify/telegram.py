"""Telegram notifier stub — wire TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID env vars.

Fleet already runs oriz127_bot; this adapter reuses the same token/chat.
Degrades silently if env vars absent.
"""

from __future__ import annotations

import os

import httpx
import structlog

from oriz_brain.decision_log import Decision

log = structlog.get_logger(__name__)

_API = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotifier:
    def __init__(self) -> None:
        self._token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._chat = os.environ.get("TELEGRAM_CHAT_ID", "")

    def send(self, decision: Decision) -> None:
        if not self._token or not self._chat:
            log.debug("telegram.skip", reason="env vars not set")
            return
        text = (
            f"*ChiragOS* [{decision.source}]\n"
            f"*Obs:* {decision.observation}\n"
            f"*Action:* {decision.action}"
        )
        try:
            resp = httpx.post(
                _API.format(token=self._token),
                json={"chat_id": self._chat, "text": text, "parse_mode": "Markdown"},
                timeout=10.0,
            )
            resp.raise_for_status()
            log.debug("telegram.sent")
        except Exception as exc:  # noqa: BLE001
            log.warning("telegram.failed", error=str(exc)[:80])
