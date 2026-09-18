"""Keep upstream diagnostics out of the normal UI and redact URL credentials."""

import logging
import re

LOG = logging.getLogger("y2mp3")


def redact(value: object) -> str:
    text = re.sub(r"https?://\S+", "[URL]", str(value))
    text = re.sub(
        r"(?i)(authorization|cookie|token|password|secret)[=: ]+\S+", r"\1=[redacted]", text
    )
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)


class EngineLogger:
    def debug(self, message: str) -> None:
        LOG.debug("engine: %s", redact(message))

    def warning(self, message: str) -> None:
        LOG.debug("engine warning: %s", redact(message))

    def error(self, message: str) -> None:
        LOG.debug("engine error: %s", redact(message))


def failure_message(exc: Exception) -> str:
    message = str(exc).lower()
    if any(
        word in message for word in ("sign in", "login", "private", "authentication", "cookies")
    ):
        return "Unavailable or login required. v0.1 supports public media only."
    if any(word in message for word in ("format is not available", "no video", "no usable")):
        return "No usable stream is available at the selected quality."
    if "space" in message:
        return "Not enough storage space."
    return "This item could not be processed. Retry or use --verbose for diagnostics."
