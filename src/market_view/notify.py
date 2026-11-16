"""Notifications: console + log, and Telegram if TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are set."""

from __future__ import annotations

import logging

import requests

from market_view.config import env

log = logging.getLogger("market_view")


def notify(message: str, level: str = "INFO") -> None:
    log.log(getattr(logging, level, logging.INFO), message)
    token, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if token and chat:
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          data={"chat_id": chat, "text": f"[market-view {level}] {message}"[:4000]}, timeout=10)
        except Exception as e:  # notifications must never crash trading logic
            log.warning("telegram failed: %s", e)
