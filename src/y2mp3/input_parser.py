"""Strict HTTP URL input without shell interpretation."""

import re
from urllib.parse import urlsplit


def validate_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme.lower() in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not any(ord(c) < 33 for c in value)
        )
        _ = parsed.port
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Enter a valid public http:// or https:// URL without credentials.")
    return value


def parse_urls(text: str) -> list[str]:
    urls = [token for token in re.split(r"[,\s]+", text.strip()) if token]
    if not urls:
        raise ValueError("Enter at least one URL.")
    return [validate_url(url) for url in urls]
