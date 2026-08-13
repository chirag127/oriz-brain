"""Notifier package."""

from oriz_brain.notify.base import Notifier
from oriz_brain.notify.console import ConsoleNotifier
from oriz_brain.notify.telegram import TelegramNotifier

__all__ = ["Notifier", "ConsoleNotifier", "TelegramNotifier", "default_notifier"]


def default_notifier() -> Notifier:
    """Return console notifier (always works); Telegram is opt-in via env."""
    return ConsoleNotifier()
